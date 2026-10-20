r"""
File: tests/test_project.py

Purpose
-------
Check repository layout, release-version ownership, documentation links and
structure, and executable Python examples across the delivered tree.

Verifies: version.py.

Contains 15 test case(s) across 3 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: ast, json, pathlib, re, subprocess, sys, textwrap, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT, RETIRED, HISTORY.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
Header and Markdown examples run in one child process, each in a fresh
namespace, from the project root. An example that starts with python is a shell
command and is only displayed.

LayoutTests:
- No double underscore paths.
- The package root holds only folders.
- Every domain folder has a readme and a tests folder.
- Docs holds only the architecture and the changelog.
- Audit passes.
VersionOwnershipTests:
- Version module defines only the version.
- Release identifier has one owner.
- No version literals in product code.
- The changelog records the current release first.
DocumentationTests:
- Markdown links resolve.
- Every markdown code fence is closed.
- Every readme opens with a title and a one line summary.
- Architecture page covers every folder in the layer map.
- Header python examples run.
- Python code blocks in markdown run.

Known limitations
-----------------
- Whether prose is true is still a human review task; these tests check
  structure and rules.
- Passing proves only the 15 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s tests -p test_project.py
"""

import ast
import json
import re
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from version import __version__

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ('python-only-source', '0.26.0', '0' + '.2.0', 'hosted/')
HISTORY = ROOT / 'docs' / 'CHANGELOG.md'


def delivered(*suffixes):
    return sorted(path for path in ROOT.rglob('*')
                  if path.is_file() and path.suffix in suffixes
                  and path.relative_to(ROOT).parts[0] != 'data' and '__pycache__' not in path.parts)


class LayoutTests(unittest.TestCase):
    def test_no_double_underscore_paths(self):
        for path in delivered('.py', '.md'):
            self.assertFalse(any('__' in part for part in path.relative_to(ROOT).parts), str(path))

    def test_the_package_root_holds_only_folders(self):
        loose = sorted(item.name for item in (ROOT / 'brisartos').iterdir()
                       if item.is_file() and item.name != 'README.md')
        self.assertEqual(loose, [])

    def test_every_domain_folder_has_a_readme_and_a_tests_folder(self):
        for folder in sorted(item for item in (ROOT / 'brisartos').iterdir() if item.is_dir()):
            self.assertTrue((folder / 'README.md').is_file(), str(folder))
            self.assertTrue(list((folder / 'tests').glob('test_*.py')), str(folder))

    def test_docs_holds_only_the_architecture_and_the_changelog(self):
        self.assertEqual(sorted(item.name for item in (ROOT / 'docs').iterdir()),
                         ['ARCHITECTURE.md', 'CHANGELOG.md'])

    def test_audit_passes(self):
        result = subprocess.run([sys.executable, '-B', '-S', str(ROOT / 'tools' / 'audit.py')],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout)


class VersionOwnershipTests(unittest.TestCase):
    def test_version_module_defines_only_the_version(self):
        tree = ast.parse((ROOT / 'version.py').read_text(encoding='utf-8'))
        statements = tree.body[1:]
        self.assertEqual(len(statements), 1, 'version.py must define only __version__')
        self.assertEqual(statements[0].targets[0].id, '__version__')
        self.assertIsInstance(statements[0].value.value, str)

    def test_release_identifier_has_one_owner(self):
        for path in delivered('.py', '.md'):
            if path in (ROOT / 'version.py', Path(__file__).resolve(), HISTORY):
                continue
            text = path.read_text(encoding='utf-8')
            self.assertNotIn(__version__, text, str(path))
            for old in RETIRED:
                self.assertNotIn(old, text, str(path))

    def test_no_version_literals_in_product_code(self):
        for path in delivered('.py'):
            if path.relative_to(ROOT).parts[0] == 'tests' or '/tests/' in path.as_posix() or path == ROOT / 'version.py':
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    for target in node.targets:
                        name = target.id if isinstance(target, ast.Name) else getattr(target, 'attr', '')
                        self.assertNotIn('version', name.lower(), str(path) + ':' + str(node.lineno))

    def test_the_changelog_records_the_current_release_first(self):
        headings = re.findall(r'^## (.+)$', HISTORY.read_text(encoding='utf-8'), re.M)
        self.assertTrue(headings, 'the changelog has no entries')
        self.assertIn(__version__, headings[0])


class DocumentationTests(unittest.TestCase):
    def test_markdown_links_resolve(self):
        for path in delivered('.md'):
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                self.assertTrue((path.parent / target.split('#')[0]).exists(), str(path) + ': ' + target)

    def test_every_markdown_code_fence_is_closed(self):
        for path in delivered('.md'):
            fences = re.findall(r'^```', path.read_text(encoding='utf-8'), re.M)
            self.assertEqual(len(fences) % 2, 0, str(path))

    def test_every_readme_opens_with_a_title_and_a_one_line_summary(self):
        for path in delivered('.md'):
            if path.name != 'README.md':
                continue
            lines = path.read_text(encoding='utf-8').splitlines()
            self.assertTrue(lines[0].startswith('# '), str(path))
            self.assertEqual(lines[1], '', str(path))
            self.assertTrue(lines[2].strip() and not lines[2].startswith('#'), str(path))

    def test_architecture_page_covers_every_folder_in_the_layer_map(self):
        tree = ast.parse((ROOT / 'tools' / 'audit.py').read_text(encoding='utf-8'))
        layers = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'LAYERS':
                layers = ast.literal_eval(node.value)
        self.assertIsNotNone(layers)
        text = (ROOT / 'docs' / 'ARCHITECTURE.md').read_text(encoding='utf-8')
        folders = sorted(item.name for item in (ROOT / 'brisartos').iterdir() if item.is_dir())
        self.assertEqual(folders, sorted(layers))
        for folder in folders:
            self.assertIn('`' + folder + '/`', text, folder)

    def run_examples(self, examples):
        runner = ('import json, sys\n'
                  'failed = []\n'
                  'for name, code in json.loads(sys.stdin.read()).items():\n'
                  '    try:\n'
                  '        exec(compile(code, name, "exec"), {"__name__": "example"})\n'
                  '    except BaseException as error:\n'
                  '        failed.append(name + ": " + type(error).__name__ + ": " + str(error))\n'
                  'print(json.dumps(failed))\n')
        result = subprocess.run([sys.executable, '-B', '-S', '-c', runner], input=json.dumps(examples),
                                cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), [])

    def test_header_python_examples_run(self):
        examples = {}
        for path in delivered('.py'):
            doc = ast.get_docstring(ast.parse(path.read_text(encoding='utf-8'))) or ''
            block = doc.split('Examples\n--------\n', 1)[-1]
            if '::\n\n' not in block:
                continue
            code = textwrap.dedent(block.split('::\n\n', 1)[1]).strip()
            if not code.startswith('python '):
                examples[path.relative_to(ROOT).as_posix()] = code
        self.assertGreaterEqual(len(examples), 20)
        self.run_examples(examples)

    def test_python_code_blocks_in_markdown_run(self):
        examples = {}
        for path in delivered('.md'):
            text = path.read_text(encoding='utf-8')
            for number, block in enumerate(re.findall(r'^```python\n(.*?)^```', text, re.M | re.S), 1):
                if not block.lstrip().startswith('# not run'):
                    examples[path.relative_to(ROOT).as_posix() + ' block ' + str(number)] = block
        self.assertGreaterEqual(len(examples), 4)
        self.run_examples(examples)


if __name__ == '__main__':
    unittest.main()
