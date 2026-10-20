r"""
File: tools/headers.py

Purpose
-------
Refresh the syntax-derived portions of Python file headers while retaining
their authored descriptions, rationale, limitations and examples.

Public interface:
- python_files(root=None) -- Return every Python file below the project root,
  sorted, skipping caches and data/.
- is_test_file(relative) -- Return True for a test_*.py file inside a tests
  folder.
- paragraphs(lines) -- Group lines into blank-line separated paragraphs.
- split_header(doc) -- Split a header docstring into its six sections; raise
  ValueError when they are missing or out of order.
- refresh(write, root=None) -- Rewrite (or, with write False, only compare)
  every header and return the stale files and the problems found.
- main(argv=None) -- Command-line entry point; --check reports without writing
  and exits 1 when anything is out of date.

Design notes:

The tool parses all selected source files and builds an import graph, then
combines current code facts with existing header prose. Public descriptions are
matched by name. Missing descriptions prevent that file from being rewritten.
Static imports and router string references inform relationships; dynamic
loading and subprocess execution are not complete test-coverage evidence.

tools/tests/test_tools.py exercises refresh and check modes through child
processes on temporary project copies, outside the static-import graph.

Communication / relationships
-----------------------------
Standard library: ast, importlib, pathlib, re, sys, textwrap.
Imported by:
- run.py
- tools/audit.py
Covered by tests: none directly.

Settings / parameters
---------------------
- ROOT = Path(__file__).resolve().parents[1]
- SECTIONS -- The six header sections, in order.
- SKIP = {'data'}
- WIDTH = 79
- STRING_LIMIT = 60
- GENERATED_EDGE = re.compile('^\\S.*\\(\\) (raises|catches|re-raises)\\b') --
  Matches the Edge cases lines this tool generates, so hand-written lines are
  kept apart from them.
- TEST_PASSING = '- Passing proves only'

Edge cases
----------
A file without a header docstring, without the six ordered sections, or whose
header would contain a triple quote is reported as a problem and left
unchanged.

- split_header() raises ValueError: "six ordered section headings required"
- _imports() catches ImportError -- A relative import that climbs above the
  package is skipped instead of stopping the run.
- refresh() catches ValueError -- A header whose sections are missing is
  reported as a problem for that file and the run continues.

Known limitations
-----------------
- It derives facts, not meaning: it cannot tell whether the written prose is
  still true, only that every public name has some description.
- Dependencies are found from import statements, so a module loaded by path,
  such as hello_lab, has no static importer.
- Private names (leading underscore) are not listed in Public interface.

Examples
--------
Run from the repository root.

::

    python -B run.py headers
    python -B tools/headers.py --check
"""

import ast
import importlib.util
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ('Purpose', 'Communication / relationships', 'Settings / parameters',
            'Edge cases', 'Known limitations', 'Examples')
SKIP = {'data'}
WIDTH = 79
STRING_LIMIT = 60
GENERATED_EDGE = re.compile(r'^\S.*\(\) (raises|catches|re-raises)\b')
TEST_PASSING = '- Passing proves only'


def python_files(root=None):
    root = ROOT if root is None else root
    return sorted(path for path in root.rglob('*.py')
                  if '__pycache__' not in path.parts and path.relative_to(root).parts[0] not in SKIP)


def _module_name(path, root=None):
    return '.'.join(path.relative_to(ROOT if root is None else root).with_suffix('').parts)


def is_test_file(relative):
    return relative.rsplit('/', 1)[-1].startswith('test_') and ('/tests/' in relative or relative.startswith('tests/'))


def _scope(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            yield from _scope(child)


def _functions(tree):
    def walk(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield prefix + node.name, node
                yield from walk(node.body, prefix + node.name + '.')
            elif isinstance(node, ast.ClassDef):
                yield from walk(node.body, prefix + node.name + '.')
    yield from walk(tree.body, '')


def _wrap(text, first='', rest=''):
    return textwrap.fill(text, WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def _fill(block):
    lines = block.splitlines()
    if any(line.startswith((' ', '\t', '- ')) or line.endswith('::') for line in lines):
        return block
    return _wrap(' '.join(line.strip() for line in lines))


def _fill_all(text):
    return '\n\n'.join(_fill(block) for block in paragraphs(text.splitlines()))


def _split_item(text):
    head, _, description = text.partition(' -- ')
    return head.strip(), description.strip()


def _item_key(head):
    return head.split('(', 1)[0].strip()


def _parse_items(text):
    """Split a block into bullet items and the other lines around them."""
    items, other, current = [], [], None
    for line in text.splitlines():
        if line.startswith('- '):
            current = [line[2:].strip()]
            items.append(current)
        elif current is not None and line.startswith('  ') and line.strip():
            current.append(line.strip())
        else:
            current = None
            other.append(line)
    return [' '.join(item) for item in items], other


def paragraphs(lines):
    result, block = [], []
    for line in lines:
        if line.strip():
            block.append(line)
        elif block:
            result.append('\n'.join(block))
            block = []
    if block:
        result.append('\n'.join(block))
    return result


def _descriptions(text):
    found = {}
    for item in _parse_items(text)[0]:
        head, description = _split_item(item)
        found[_item_key(head)] = description
    return found


def _bullet(head, description=''):
    return _wrap(head + (' -- ' + description if description else ''), '- ', '  ')


# ---------------------------------------------------------------- code facts

def _arguments(node):
    text = ast.unparse(node.args)
    for prefix in ('self, ', 'cls, '):
        if text.startswith(prefix):
            return text[len(prefix):]
    return '' if text in ('self', 'cls') else text


def _decorated(node, name):
    for item in node.decorator_list:
        target = item.func if isinstance(item, ast.Call) else item
        if (isinstance(target, ast.Name) and target.id == name) or (isinstance(target, ast.Attribute) and target.attr == name):
            return True
    return False


def _public_heads(tree):
    heads = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_') and not _decorated(node, 'command'):
            heads.append(node.name + '(' + _arguments(node) + ')')
        elif isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
            bases = ', '.join(ast.unparse(base) for base in node.bases)
            heads.append('class ' + node.name + ('(' + bases + ')' if bases else ''))
            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name == '__init__':
                    if _arguments(member):
                        heads.append(node.name + '(' + _arguments(member) + ')')
                elif not member.name.startswith('_'):
                    if _decorated(member, 'property'):
                        heads.append(node.name + '.' + member.name)
                    else:
                        heads.append(node.name + '.' + member.name + '(' + _arguments(member) + ')')
    return heads


def _module_constants(tree):
    found = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and (target.id.isupper() or
                                                     (target.id.startswith('__') and target.id.endswith('__'))):
                    value = ast.unparse(node.value)
                    shown = value if len(value) <= STRING_LIMIT and '\n' not in value else None
                    found.append((target.id, shown))
    return found


def _message_text(call, constants=None):
    if not (isinstance(call, ast.Call) and call.args):
        return None
    parts = []

    def flatten(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            flatten(node.left)
            flatten(node.right)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
        elif isinstance(node, ast.Name) and constants and node.id in constants:
            parts.append(constants[node.id])
        elif isinstance(node, ast.JoinedStr):
            parts.append(''.join(item.value if isinstance(item, ast.Constant) else '{...}' for item in node.values))
        else:
            parts.append('{...}')
    flatten(call.args[0])
    text = ''.join(parts)
    return re.sub(r'(\{\.\.\.\})+', '{...}', text)


def _string_constants(tree):
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = node.value.value
    return found


def _edge_heads(tree):
    raises, catches = [], []
    constants = _string_constants(tree)
    for name, node in _functions(tree):
        for item in _scope(node):
            if isinstance(item, ast.Raise):
                if item.exc is None:
                    raises.append(name + '() re-raises the active exception')
                    continue
                kind = ast.unparse(item.exc.func if isinstance(item.exc, ast.Call) else item.exc)
                message = _message_text(item.exc, constants)
                raises.append(name + '() raises ' + kind + (': "' + message + '"' if message else ''))
            elif isinstance(item, ast.ExceptHandler):
                catches.append(name + '() catches ' + (ast.unparse(item.type) if item.type else 'every exception'))
    return list(dict.fromkeys(raises)), list(dict.fromkeys(catches))


def _test_classes(tree):
    result = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names = [member.name for member in node.body
                     if isinstance(member, ast.FunctionDef) and member.name.startswith('test_')]
            if names:
                result.append((node.name, names))
    return result


def _case_counts(tree):
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}

    def own(name):
        return [item.name for item in classes[name].body
                if isinstance(item, ast.FunctionDef) and item.name.startswith('test_')]

    def inherited(name):
        found = own(name)
        for base in classes[name].bases:
            if isinstance(base, ast.Name) and base.id in classes:
                found += inherited(base.id)
        return found

    def is_case(name):
        return any(ast.unparse(base) in ('unittest.TestCase', 'TestCase') or
                   (isinstance(base, ast.Name) and base.id in classes and is_case(base.id))
                   for base in classes[name].bases)

    cases = [name for name in classes if is_case(name)]
    return sum(len(set(inherited(name))) for name in cases), len(cases)


def _humanize(name):
    text = name[len('test_'):].replace('_', ' ')
    return text[:1].upper() + text[1:] + '.'


# ----------------------------------------------------------- import analysis

def _imports(path, tree, root=None):
    parts = path.relative_to(ROOT if root is None else root).with_suffix('').parts
    package = '.'.join(parts[:-1])
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(([alias.name], ast.unparse(node)))
        elif isinstance(node, ast.ImportFrom):
            base = '.' * node.level + (node.module or '')
            try:
                target = importlib.util.resolve_name(base, package) if node.level else base
            except ImportError:
                continue
            found.append(([target] + [target + '.' + alias.name for alias in node.names], ast.unparse(node)))
    return found


def _project_graph(paths, trees, root=None):
    root = ROOT if root is None else root
    modules = {_module_name(path, root): path for path in paths}
    for path in paths:
        if path.parent.name in ('tests', 'tools'):
            modules.setdefault(path.stem, path)
    edges = {path: set() for path in paths}
    for path in paths:
        for names, _ in _imports(path, trees[path], root):
            for name in names:
                if name in modules and modules[name] != path:
                    edges[modules[name]].add(path)
    router = root / 'run.py'
    if router in trees:
        for node in ast.walk(trees[router]):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                target = modules.get(node.value)
                if target is None and node.value.endswith('.py'):
                    target = root / node.value
                if target in edges:
                    edges[target].add(router)
    return modules, edges


def _dependencies(path, tree, modules, root):
    project, standard = {}, set()
    for names, _ in _imports(path, tree, root):
        matched = [name for name in names if name in modules and modules[name] != path]
        if matched:
            for name in matched:
                project[name] = modules[name].relative_to(root).as_posix()
        elif names[0].split('.')[0] in sys.stdlib_module_names:
            standard.add(names[0].split('.')[0])
    return project, sorted(standard)


# ------------------------------------------------------------ header sections

def split_header(doc):
    lines = doc.splitlines()
    marks = []
    for index, line in enumerate(lines[:-1]):
        if line in SECTIONS and lines[index + 1] == '-' * len(line):
            marks.append((line, index))
    if [name for name, _ in marks] != list(SECTIONS):
        raise ValueError('six ordered section headings required')
    parts = {}
    for position, (name, index) in enumerate(marks):
        end = marks[position + 1][1] if position + 1 < len(marks) else len(lines)
        parts[name] = '\n'.join(lines[index + 2:end]).strip()
    return parts


def _split_purpose(text):
    lines = text.splitlines()
    interface = next((i for i, line in enumerate(lines) if line == 'Public interface:'), None)
    design = next((i for i, line in enumerate(lines) if line == 'Design notes:'), None)
    first = min(index for index in (interface, design, len(lines)) if index is not None)
    summary = [_fill(block) for block in paragraphs(lines[:first])
               if not block.startswith(('Verifies:', 'Contains '))]
    block = []
    if interface is not None:
        block = lines[interface + 1:design if design is not None and design > interface else len(lines)]
    notes = _fill_all('\n'.join(lines[design + 1:])) if design is not None else ''
    return summary, '\n'.join(block), notes


def _build_purpose(relative, tree, old, project, problems):
    summary, interface, notes = _split_purpose(old)
    out = list(summary)
    if is_test_file(relative):
        sources = sorted(path for path in project.values() if not is_test_file(path))
        if sources:
            out.append(_wrap('Verifies: ' + ', '.join(sources) + '.'))
        count, classes = _case_counts(tree)
        out.append('Contains ' + str(count) + ' test case(s) across ' + str(classes) + ' TestCase class(es).')
        return '\n\n'.join(out)
    known = _descriptions(interface)
    items = []
    for head in _public_heads(tree):
        description = known.get(_item_key(head), '')
        if len(description) < 8:
            problems.append(relative + ': no description for ' + _item_key(head) + ' in Public interface')
        items.append(_bullet(head, description))
    if items:
        out.append('Public interface:\n' + '\n'.join(items))
    if notes:
        out.append('Design notes:\n\n' + notes)
    else:
        problems.append(relative + ': Design notes are required')
    return '\n\n'.join(out)


def _build_communication(relative, tree, old, project, standard, users):
    known = _descriptions(old)
    lines = []
    if project:
        lines.append('Depends on (project modules):')
        for name, where in sorted(project.items()):
            lines.append(_bullet(name + ' (' + where + ')', known.get(name, '')))
    lines.append(_wrap('Standard library: ' + (', '.join(standard) if standard else 'none') + '.'))
    if is_test_file(relative):
        folder = relative.rsplit('/', 1)[0]
        lines.append(_wrap('Discovered and run by run.py test (and by python -m unittest discover -s '
                          + folder + '); nothing imports it.'))
        return '\n'.join(lines)
    others = [item for item in users if not is_test_file(item)]
    tests = [item for item in users if is_test_file(item)]
    if others:
        lines.append('Imported by:')
        lines += [_bullet(item, known.get(item, '')) for item in others]
    else:
        lines.append('Imported by: no other module in this tree imports it directly.')
    lines.append(_wrap('Covered by tests: ' + (', '.join(tests) if tests else 'none directly') + '.'))
    return '\n'.join(lines)


def _build_settings(tree, old, relative, problems):
    items, other = _parse_items(old)
    known = {}
    for item in items:
        head, description = _split_item(item)
        known[head.split(' = ', 1)[0].strip()] = description
    prose = _fill_all('\n'.join(other)) if other else ''
    if is_test_file(relative):
        return prose
    bullets = []
    for name, shown in _module_constants(tree):
        description = known.get(name, '')
        if shown is None and len(description) < 8:
            problems.append(relative + ': no description for the long value of ' + name + ' in Settings')
        head = name + ' = ' + shown if shown is not None else name
        bullets.append(_bullet(head, description))
    return '\n\n'.join(part for part in (prose, '\n'.join(bullets)) if part)


def _build_edges(tree, old, relative, problems):
    classes = _test_classes(tree)
    if classes:
        positions = [old.find(name + ':\n') for name, _ in classes if old.find(name + ':\n') >= 0]
        old = old[:min(positions)] if positions else old
    items, other = _parse_items(old)
    known, hand = {}, []
    for item in items:
        head, description = _split_item(item)
        if GENERATED_EDGE.match(head):
            known[head] = description
        else:
            hand.append(item)
    prose = '\n'.join(other)
    parts = [_fill_all(prose)] if prose.strip() else []
    if hand:
        parts.append('\n'.join(_wrap(item, '- ', '  ') for item in hand))
    if classes:
        blocks = []
        for name, names in classes:
            blocks.append(name + ':\n' + '\n'.join('- ' + _humanize(item) for item in names))
        parts.append('\n'.join(blocks))
        return '\n\n'.join(part for part in parts if part)
    raises, catches = _edge_heads(tree)
    generated = []
    for head in raises:
        generated.append(_bullet(head, known.get(head, '')))
    for head in catches:
        description = known.get(head, '')
        if len(description) < 8:
            problems.append(relative + ': no description for "' + head + '" in Edge cases')
        generated.append(_bullet(head, description))
    if generated:
        parts.append('\n'.join(generated))
    return '\n\n'.join(part for part in parts if part)


def _build_limitations(tree, old, relative):
    items, _ = _parse_items(old)
    kept = [item for item in items if not item.startswith(TEST_PASSING[2:])]
    lines = [_wrap(item, '- ', '  ') for item in kept]
    if is_test_file(relative):
        count = sum(len(names) for _, names in _test_classes(tree))
        lines.append(_wrap('Passing proves only the ' + str(count) + ' scenario(s) listed under Edge cases; '
                          'behaviour outside them is not asserted here.', '- ', '  '))
    return '\n'.join(lines)


def _render(relative, parts):
    out = ['File: ' + relative, '']
    for name in SECTIONS:
        out += [name, '-' * len(name), parts[name].strip(), '']
    return '\n'.join(out).rstrip() + '\n'


def refresh(write, root=None):
    root = ROOT if root is None else root
    paths = python_files(root)
    trees = {path: ast.parse(path.read_text(encoding='utf-8')) for path in paths}
    modules, edges = _project_graph(paths, trees, root)
    stale, problems = [], []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding='utf-8')
        tree = trees[path]
        first = tree.body[0] if tree.body else None
        if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            problems.append(relative + ': missing header docstring')
            continue
        try:
            old = split_header(first.value.value)
        except ValueError as error:
            problems.append(relative + ': ' + str(error))
            continue
        project, standard = _dependencies(path, tree, modules, root)
        users = sorted(item.relative_to(root).as_posix() for item in edges[path])
        before = len(problems)
        parts = {
            'Purpose': _build_purpose(relative, tree, old['Purpose'], project, problems),
            'Communication / relationships': _build_communication(relative, tree, old['Communication / relationships'],
                                                                project, standard, users),
            'Settings / parameters': _build_settings(tree, old['Settings / parameters'], relative, problems),
            'Edge cases': _build_edges(tree, old['Edge cases'], relative, problems),
            'Known limitations': _build_limitations(tree, old['Known limitations'], relative),
            'Examples': old['Examples'],
        }
        header = _render(relative, parts)
        if '"""' in header:
            problems.append(relative + ': header may not contain triple quotes')
            continue
        updated = 'r"""\n' + header + '"""\n' + '\n'.join(source.splitlines()[first.end_lineno:]) + '\n'
        if updated != source and len(problems) == before:
            stale.append(relative)
            if write:
                path.write_text(updated, encoding='utf-8')
    return stale, problems


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check = argv == ['--check']
    stale, problems = refresh(write=not check)
    for item in problems:
        print('problem: ' + item)
    for item in stale:
        print(('out of date: ' if check else 'refreshed: ') + item)
    if not stale and not problems:
        print('all headers current')
    return 1 if problems or (check and stale) else 0


if __name__ == '__main__':
    raise SystemExit(main())
