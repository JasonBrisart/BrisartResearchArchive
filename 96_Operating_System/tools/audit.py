r"""
File: tools/audit.py

Purpose
-------
Inspect the BrisartOS source tree for path, header, import-layer and
README-coverage violations and return a sorted JSON-compatible report.

Public interface:
- audit() -- Run every check and return the report: status, file count, errors
  and import roots.
- main() -- Print the report as JSON and return 0 on PASS or 1 on FAIL.

Design notes:

The audit reads syntax trees rather than importing inspected modules. Product
restrictions apply within brisartos except its test folders. README checks use
filename substring presence, and generated-header checks delegate to
headers.refresh(write=False). Markdown link and executable-example checks
belong to the project tests, not this audit.

tools/tests/test_tools.py runs this program on temporary project copies, and
tests/test_project.py checks its exit result. Neither relationship is measured
by the static-import coverage line.

Communication / relationships
-----------------------------
Depends on (project modules):
- headers (tools/headers.py)
Standard library: ast, json, sys.
Imported by:
- run.py
Covered by tests: none directly.

Settings / parameters
---------------------
- ROOT = headers.ROOT
- ALLOWED_SUFFIXES = {'.py', '.md'}
- HOST_FOLDER = 'host'
- LAYERS -- Maps each folder under brisartos/ to its layer number; a folder may
  import its own folder and strictly lower layers only.
- FORBIDDEN_CALLS = {'open', 'eval', 'exec', 'compile', '__import__'}

Edge cases
----------
Each problem becomes one line in errors, starting with the file path, and the
report is sorted. A new folder under brisartos/ fails until it is added to
LAYERS.

- _check_header() catches ValueError -- A header without the six ordered
  sections is reported as an error instead of crashing the audit.
- audit() catches SyntaxError -- A file that does not parse is reported and
  skipped so the other files are still checked.

Known limitations
-----------------
- Static checks only: it cannot see dynamic imports or prove behavior, security
  or bootability.
- It requires header prose to exist and be non-trivial but cannot judge whether
  it is true.

Examples
--------
Run from the repository root.

::

    python -B run.py audit
"""

import ast
import json
import sys

import headers

ROOT = headers.ROOT
ALLOWED_SUFFIXES = {'.py', '.md'}
HOST_FOLDER = 'host'
LAYERS = {'common': 0, 'storage': 0, 'events': 1, 'host': 1, 'language': 1, 'services': 1, 'extensions': 2,
          'machine': 2, 'kernel': 3, 'shell': 4}
FORBIDDEN_CALLS = {'open', 'eval', 'exec', 'compile', '__import__'}


def _delivered_files():
    for path in sorted(ROOT.rglob('*')):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and parts[0] not in headers.SKIP and '__pycache__' not in parts:
            yield path


def _check_paths(errors):
    for path in _delivered_files():
        relative = path.relative_to(ROOT)
        if any('__' in part for part in relative.parts):
            errors.append(relative.as_posix() + ': double underscores are not allowed in paths')
        if path.suffix not in ALLOWED_SUFFIXES and not (path.name == 'manifest.txt' and len(relative.parts) == 3 and relative.parts[0] == 'modules'):
            errors.append(relative.as_posix() + ': unexpected file type')


def _check_header(relative, tree, errors):
    doc = ast.get_docstring(tree) or ''
    if 'File: ' + relative not in doc.splitlines():
        errors.append(relative + ': header File line does not match the path')
    try:
        parts = headers.split_header(doc)
    except ValueError as error:
        errors.append(relative + ': ' + str(error))
        return
    test = headers.is_test_file(relative)
    summary = (headers.paragraphs(parts['Purpose'].splitlines()) or [''])[0]
    if len(summary) < 30:
        errors.append(relative + ': Purpose needs a written summary')
    if not test and 'Design notes:' not in parts['Purpose']:
        errors.append(relative + ': Purpose needs Design notes')
    relationships = parts['Communication / relationships']
    if 'Standard library:' not in relationships:
        errors.append(relative + ': relationships need a Standard library line')
    if test:
        if 'Discovered and run by' not in relationships:
            errors.append(relative + ': a test header must say how it is run')
    elif 'Imported by' not in relationships or 'Covered by tests:' not in relationships:
        errors.append(relative + ': relationships need Imported by and Covered by tests')
    for name in ('Settings / parameters', 'Edge cases'):
        if len(parts[name]) < 15:
            errors.append(relative + ': section needs content: ' + name)
    if '- ' not in parts['Known limitations']:
        errors.append(relative + ': Known limitations needs at least one bullet')
    if '::' not in parts['Examples']:
        errors.append(relative + ': Examples needs a :: block')


def _relative_folders(node, parts):
    package = list(parts[:-1])
    base = package[:len(package) - (node.level - 1)]
    if not base or base[0] != 'brisartos':
        return None
    targets = [base + node.module.split('.')] if node.module else [base + [alias.name] for alias in node.names]
    return [target[1] if len(target) > 1 else '' for target in targets]


def _check_imports(path, tree, errors, local):
    parts = path.relative_to(ROOT).parts
    relative = '/'.join(parts)
    product = parts[0] == 'brisartos' and 'tests' not in parts
    folder = parts[1] if product and len(parts) > 2 else ''
    siblings = {item.stem for item in path.parent.glob('*.py')}
    if product and len(parts) == 2:
        errors.append(relative + ': files belong inside a brisartos/<folder>/, not loose in brisartos/')
    if product and folder and folder not in LAYERS:
        errors.append(relative + ': folder ' + folder + ' is not in the layer map (tools/audit.py LAYERS)')
    strict = product and folder != HOST_FOLDER
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name.split('.')[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module.split('.')[0]]
        else:
            names = []
        for name in names:
            if not (name in sys.stdlib_module_names or name in local or name in siblings):
                errors.append(relative + ': not standard library or local: ' + name)
            if product and name != 'version' and (strict or name == 'brisartos'):
                errors.append(relative + ': only brisartos/host/ may import ' + name)
        if product and isinstance(node, ast.ImportFrom) and node.level and folder in LAYERS:
            for target in _relative_folders(node, parts) or []:
                if target and target != folder and LAYERS.get(target, 99) >= LAYERS[folder]:
                    errors.append(relative + ': layer violation: ' + folder + ' (layer ' + str(LAYERS[folder])
                                  + ') may not import ' + target + ' (layer ' + str(LAYERS.get(target, '?')) + ')')
        if strict:
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                errors.append(relative + ': only brisartos/host/ may call ' + node.func.id)
            if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
                errors.append(relative + ': bytes literal outside brisartos/host/')


def _python_directories():
    found = {ROOT}
    for path in headers.python_files():
        found.update(ROOT / parent for parent in path.relative_to(ROOT).parents if parent.parts)
    return sorted(found)


def _check_readmes(errors):
    directories = _python_directories()
    for folder in directories:
        is_tests = folder.name == 'tests' and folder.parent != ROOT
        owner = folder.parent if is_tests else folder
        label = owner.relative_to(ROOT).as_posix() or '.'
        readme = owner / 'README.md'
        if not readme.is_file():
            errors.append(label + ': README.md is required in every folder that contains Python')
            continue
        text = readme.read_text(encoding='utf-8')
        direct = [item.name for item in sorted(folder.glob('*.py'))]
        children = [item.name + '/' for item in sorted(folder.iterdir()) if item in directories]
        for name in direct + (['tests/'] if is_tests else children):
            if name not in text:
                errors.append(label + '/README.md does not mention ' + name)


def audit():
    errors = []
    local = {path.stem for path in ROOT.glob('*.py')} | {'brisartos'}
    roots = set()
    _check_paths(errors)
    for path in headers.python_files():
        relative = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except SyntaxError as error:
            errors.append(relative + ': syntax error: ' + str(error))
            continue
        _check_header(relative, tree, errors)
        _check_imports(path, tree, errors, local)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                roots.add(node.module.split('.')[0])
    _check_readmes(errors)
    stale, problems = headers.refresh(write=False)
    errors += [item + ': generated header parts are out of date (run: python -B run.py headers)' for item in stale]
    errors += problems
    return {'status': 'FAIL' if errors else 'PASS',
            'python_files': len(headers.python_files()),
            'errors': sorted(set(errors)), 'import_roots': sorted(roots),
            'note': 'Static checks only: not a security review, a dependency proof, or hardware validation.'}


def main():
    report = audit()
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
