r"""
File: tools/tests/test_tools.py

Purpose
-------
Mutate temporary project copies to check audit failures and header refresh
behavior without editing the source tree under test.

Contains 23 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Standard library: json, pathlib, shutil, subprocess, sys, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
tools/tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT.

Fixture helpers in this file: AuditTests: setUp.

Edge cases
----------
Every failure scenario edits a fresh copy, so scenarios cannot affect each
other or the real tree.

AuditTests:
- The shipped tree passes.
- Standard library imports are only allowed in host.
- Forbidden calls are only allowed in host.
- Upward imports break the layer rule.
- Sideways imports between equal layers break the layer rule.
- Absolute brisartos imports are refused in product code.
- Loose files in the package root are refused.
- Unknown folders need a place in the layer map.
- Double underscore paths are refused.
- A readme must mention every file in its folder.
- A readme must mention every test file.
- A folder without a readme is refused.
- A stale header is reported and the tool repairs it.
- A new public function needs a description.
- A new exception handler needs a description.
- A header with a missing section is refused.
- A header with the wrong file line is refused.
- A header without design notes is refused.
- Unexpected file types are refused.
HeaderToolTests:
- Check mode reports without changing anything.
- Refresh keeps the written prose and descriptions.
- Relationships are regenerated from the imports.
- Clean tree reports current.

Known limitations
-----------------
- Each scenario starts a child interpreter, so this is the slowest test folder.
- Passing proves only the 23 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s tools/tests -p test_tools.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ProjectCopy:
    def __init__(self, test):
        self.folder = tempfile.TemporaryDirectory()
        test.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / 'BrisartOS'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns('data', '__pycache__'))

    def tool(self, name, *options):
        return subprocess.run([sys.executable, '-B', '-S', str(self.root / 'tools' / name), *options],
                              capture_output=True, text=True, cwd=self.root, timeout=120)

    def audit(self):
        result = self.tool('audit.py')
        return result.returncode, json.loads(result.stdout)['errors']

    def read(self, relative):
        return (self.root / relative).read_text(encoding='utf-8')

    def edit(self, relative, old, new, which='last'):
        path = self.root / relative
        text = path.read_text(encoding='utf-8')
        assert old in text, old
        if which == 'all':
            text = text.replace(old, new)
        elif which == 'first':
            text = text.replace(old, new, 1)
        else:
            head, _, tail = text.rpartition(old)
            text = head + new + tail
        path.write_text(text, encoding='utf-8')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.project = ProjectCopy(self)

    def assertAuditFails(self, expected):
        code, errors = self.project.audit()
        self.assertEqual(code, 1)
        self.assertTrue(any(expected in item for item in errors), expected + ' not in ' + repr(errors))

    def test_the_shipped_tree_passes(self):
        self.assertEqual(self.project.audit(), (0, []))

    def test_standard_library_imports_are_only_allowed_in_host(self):
        self.project.edit('brisartos/kernel/scheduler.py', 'class Scheduler:', 'import os\n\n\nclass Scheduler:')
        self.assertAuditFails('only brisartos/host/ may import os')

    def test_forbidden_calls_are_only_allowed_in_host(self):
        self.project.edit('brisartos/kernel/scheduler.py', 'class Scheduler:', 'HANDLE = open("x")\n\n\nclass Scheduler:')
        self.assertAuditFails('only brisartos/host/ may call open')

    def test_upward_imports_break_the_layer_rule(self):
        self.project.edit('brisartos/extensions/api.py', 'from ..host import system',
                          'from ..host import system\nfrom ..kernel.platform import Platform')
        self.assertAuditFails('layer violation: extensions (layer 2) may not import kernel (layer 3)')

    def test_sideways_imports_between_equal_layers_break_the_layer_rule(self):
        self.project.edit('brisartos/services/archive.py', 'from version import __version__',
                          'from version import __version__\nfrom ..language.lexer import LanguageError')
        self.assertAuditFails('layer violation: services')

    def test_absolute_brisartos_imports_are_refused_in_product_code(self):
        self.project.edit('brisartos/kernel/kernel.py', 'from .devices import', 'from brisartos.kernel.devices import DeviceRegistry as Unused\nfrom .devices import')
        self.assertAuditFails('only brisartos/host/ may import brisartos')

    def test_loose_files_in_the_package_root_are_refused(self):
        (self.project.root / 'brisartos' / 'stray.py').write_text('x = 1\n')
        self.assertAuditFails('not loose in brisartos/')

    def test_unknown_folders_need_a_place_in_the_layer_map(self):
        (self.project.root / 'brisartos' / 'extras').mkdir()
        (self.project.root / 'brisartos' / 'extras' / 'thing.py').write_text('x = 1\n')
        self.assertAuditFails('not in the layer map')

    def test_double_underscore_paths_are_refused(self):
        (self.project.root / 'brisartos' / 'kernel' / '__init__.py').write_text('')
        self.assertAuditFails('double underscores are not allowed')

    def test_a_readme_must_mention_every_file_in_its_folder(self):
        self.project.edit('brisartos/kernel/README.md', 'scheduler.py', 'the scheduler', which='all')
        self.assertAuditFails('brisartos/kernel/README.md does not mention scheduler.py')

    def test_a_readme_must_mention_every_test_file(self):
        self.project.edit('brisartos/kernel/README.md', 'test_components.py', 'the component tests', which='all')
        self.assertAuditFails('does not mention test_components.py')

    def test_a_folder_without_a_readme_is_refused(self):
        (self.project.root / 'brisartos' / 'kernel' / 'README.md').unlink()
        self.assertAuditFails('brisartos/kernel: README.md is required')

    def test_a_stale_header_is_reported_and_the_tool_repairs_it(self):
        self.project.edit('brisartos/kernel/scheduler.py', 'def status(self):', 'def status(self, verbose=False):')
        self.assertAuditFails('generated header parts are out of date')
        self.assertEqual(self.project.tool('headers.py').returncode, 0)
        self.assertEqual(self.project.audit(), (0, []))
        self.assertIn('Scheduler.status(verbose=False) --', self.project.read('brisartos/kernel/scheduler.py'))

    def test_a_new_public_function_needs_a_description(self):
        self.project.edit('brisartos/common/names.py', 'def require_name(',
                          'def shout(name):\n    return name.upper()\n\n\ndef require_name(')
        result = self.project.tool('headers.py')
        self.assertEqual(result.returncode, 1)
        self.assertIn('no description for shout', result.stdout)
        self.assertAuditFails('no description for shout')

    def test_a_new_exception_handler_needs_a_description(self):
        self.project.edit('brisartos/host/system.py', 'def new_id():',
                          'def safe_now():\n    try:\n        return now_utc()\n    except OSError:\n        return None\n\n\ndef new_id():')
        self.assertAuditFails('no description for "safe_now() catches OSError"')

    def test_a_header_with_a_missing_section_is_refused(self):
        self.project.edit('brisartos/common/names.py', 'Known limitations\n-----------------\n', 'Limits\n------\n', which='first')
        self.assertAuditFails('six ordered section headings required')

    def test_a_header_with_the_wrong_file_line_is_refused(self):
        self.project.edit('brisartos/common/names.py', 'File: brisartos/common/names.py', 'File: brisartos/names.py', which='first')
        self.assertAuditFails('header File line does not match the path')

    def test_a_header_without_design_notes_is_refused(self):
        self.project.edit('brisartos/common/names.py', 'Design notes:', 'Notes:', which='first')
        result = self.project.tool('headers.py', '--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Design notes are required', result.stdout)

    def test_unexpected_file_types_are_refused(self):
        (self.project.root / 'notes.txt').write_text('x')
        self.assertAuditFails('unexpected file type')


class HeaderToolTests(unittest.TestCase):
    def test_check_mode_reports_without_changing_anything(self):
        project = ProjectCopy(self)
        project.edit('brisartos/kernel/scheduler.py', 'def status(self):', 'def status(self, verbose=False):')
        before = project.read('brisartos/kernel/scheduler.py')
        result = project.tool('headers.py', '--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('out of date: brisartos/kernel/scheduler.py', result.stdout)
        self.assertEqual(project.read('brisartos/kernel/scheduler.py'), before)

    def test_refresh_keeps_the_written_prose_and_descriptions(self):
        project = ProjectCopy(self)
        before = project.read('brisartos/kernel/scheduler.py')
        summary = before.split('Purpose\n-------\n')[1].split('\n\n')[0]
        design = before.split('Design notes:\n\n')[1].split('\n\nCommunication')[0]
        project.edit('brisartos/kernel/scheduler.py', 'def status(self):', 'def status(self, verbose=False):')
        project.tool('headers.py')
        after = project.read('brisartos/kernel/scheduler.py')
        self.assertIn(summary, after)
        self.assertIn(design, after)
        self.assertIn('Scheduler.spawn(name, iterator) --', after)

    def test_relationships_are_regenerated_from_the_imports(self):
        project = ProjectCopy(self)
        project.edit('brisartos/kernel/scheduler.py', 'class Scheduler:',
                     'from ..common.names import require_name\n\n\nclass Scheduler:')
        project.tool('headers.py')
        self.assertIn('brisartos.common.names (brisartos/common/names.py)', project.read('brisartos/kernel/scheduler.py'))
        self.assertIn('brisartos/kernel/scheduler.py', project.read('brisartos/common/names.py'))

    def test_clean_tree_reports_current(self):
        project = ProjectCopy(self)
        result = project.tool('headers.py', '--check')
        self.assertEqual(result.returncode, 0)
        self.assertIn('all headers current', result.stdout)


if __name__ == '__main__':
    unittest.main()
