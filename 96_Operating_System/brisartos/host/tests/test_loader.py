r"""
File: brisartos/host/tests/test_loader.py

Purpose
-------
Build temporary module folders to check discovery order, ignored entries,
execution results, fresh module objects and propagated load errors.

Verifies: brisartos/host/loader.py.

Contains 5 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.host.loader (brisartos/host/loader.py)
Standard library: pathlib, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/host/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Fixture helpers in this file: LoaderTests: setUp, make.

Edge cases
----------
Modules are written into temporary folders; the shipped hello_lab is exercised
in brisartos/modules/tests/.

LoaderTests:
- Missing folder has no modules.
- Only folders with a module file count and order is alphabetical.
- Load module runs the file and returns its namespace.
- Load module does not share state between loads.
- Errors in the module reach the caller.

Known limitations
-----------------
- Loading executes real Python files; there is nothing to check about untrusted
  code because none is isolated.
- Passing proves only the 5 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/host/tests -p test_loader.py
"""

import tempfile
import unittest
from pathlib import Path

from brisartos.host import loader


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def make(self, name, text='VALUE = 1\n'):
        (self.root / name).mkdir()
        (self.root / name / 'module.py').write_text(text)

    def test_missing_folder_has_no_modules(self):
        self.assertEqual(loader.module_files(self.root / 'nope'), [])

    def test_only_folders_with_a_module_file_count_and_order_is_alphabetical(self):
        self.make('beta')
        self.make('alpha')
        (self.root / 'empty').mkdir()
        (self.root / 'stray.py').write_text('x = 1\n')
        names = [path.parent.name for path in loader.module_files(self.root)]
        self.assertEqual(names, ['alpha', 'beta'])

    def test_load_module_runs_the_file_and_returns_its_namespace(self):
        self.make('demo', 'VALUE = 41 + 1\n')
        module = loader.load_module(self.root / 'demo' / 'module.py')
        self.assertEqual(module.VALUE, 42)

    def test_load_module_does_not_share_state_between_loads(self):
        self.make('demo', 'ITEMS = []\nITEMS.append(1)\n')
        first = loader.load_module(self.root / 'demo' / 'module.py')
        second = loader.load_module(self.root / 'demo' / 'module.py')
        self.assertIsNot(first, second)
        self.assertEqual(second.ITEMS, [1])

    def test_errors_in_the_module_reach_the_caller(self):
        self.make('broken', 'raise RuntimeError("fails on import")\n')
        with self.assertRaises(RuntimeError):
            loader.load_module(self.root / 'broken' / 'module.py')


if __name__ == '__main__':
    unittest.main()
