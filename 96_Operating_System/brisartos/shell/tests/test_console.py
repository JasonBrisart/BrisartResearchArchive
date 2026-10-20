r"""
File: brisartos/shell/tests/test_console.py

Purpose
-------
Drive child console processes to check error recovery, option handling, EOF
cleanup, storage modes and module failure reporting.

Verifies: brisartos/shell/commands.py.

Contains 8 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.shell.commands (brisartos/shell/commands.py)
Standard library: os, pathlib, subprocess, sys, tempfile, unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/shell/tests); nothing imports it.

Settings / parameters
---------------------
Module fixtures: ROOT.

Fixture helpers in this file: ConsoleThroughRouterTests: console.
ConsoleStorageTests: session.

Edge cases
----------
Each child process has a 120 second timeout. A module that raises SystemExit(3)
must end the process with status 3 after the kernel has been stopped.

ConsoleThroughRouterTests:
- Errors do not end the session.
- A failing module does not end the session.
- Bad option.
- End of input stops cleanly.
ConsoleStorageTests:
- Default mode keeps files between sessions.
- Memory mode leaves nothing behind.
- A module that exits still leaves a clean log.
- Modules that fail to load are reported at start.

Known limitations
-----------------
- Terminal features such as Ctrl+C at the prompt are not exercised.
- Passing proves only the 8 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/shell/tests -p test_console.py
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from brisartos.shell.commands import version_text

ROOT = Path(__file__).resolve().parents[3]


class ConsoleThroughRouterTests(unittest.TestCase):
    def console(self, text, *options):
        return subprocess.run([sys.executable, '-B', '-S', str(ROOT / 'run.py'), 'start', *options],
                              input=text, capture_output=True, text=True, timeout=120)

    def test_errors_do_not_end_the_session(self):
        result = self.console('write /z.py print(1/0)\npython /z.py\nread /missing\nversion\nexit\n', '--memory')
        self.assertEqual(result.returncode, 0)
        self.assertIn('error: ZeroDivisionError', result.stdout)
        self.assertIn('error: FileNotFoundError', result.stdout)
        self.assertIn(version_text(), result.stdout)
        self.assertNotIn('Traceback', result.stdout + result.stderr)

    def test_a_failing_module_does_not_end_the_session(self):
        result = self.console('run missing\nversion\nexit\n', '--memory')
        self.assertIn('error: KeyError', result.stdout)
        self.assertIn(version_text(), result.stdout)

    def test_bad_option(self):
        result = self.console('', '--bogus')
        self.assertEqual(result.returncode, 2)
        self.assertIn('usage', result.stdout)

    def test_end_of_input_stops_cleanly(self):
        result = self.console('', '--memory')
        self.assertEqual(result.returncode, 0)


class ConsoleStorageTests(unittest.TestCase):
    def session(self, folder, text, *options):
        environment = dict(os.environ, PYTHONPATH=str(ROOT))
        return subprocess.run([sys.executable, '-B', '-S', '-m', 'brisartos.shell.console', *options],
                              input=text, capture_output=True, text=True, cwd=folder,
                              env=environment, timeout=120)

    def test_default_mode_keeps_files_between_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            self.session(folder, 'write /note.txt kept\nexit\n')
            second = self.session(folder, 'read /note.txt\nread /logs/kernel.log\nexit\n')
            self.assertIn('kept', second.stdout)
            self.assertIn('kernel: stopped', second.stdout)
            self.assertTrue((Path(folder) / 'data' / 'note.txt').is_file())

    def test_memory_mode_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as folder:
            self.session(folder, 'write /note.txt gone\nexit\n', '--memory')
            self.assertFalse((Path(folder) / 'data').exists())

    def test_a_module_that_exits_still_leaves_a_clean_log(self):
        with tempfile.TemporaryDirectory() as folder:
            quitter = Path(folder) / 'modules' / 'quitter'
            quitter.mkdir(parents=True)
            (quitter / 'module.py').write_text(
                'MODULE_NAME = "quitter"\nMODULE_DISPLAY_NAME = "q"\nMODULE_VERSION = "1"\n'
                'MODULE_AUTHOR = "x"\nMODULE_DESCRIPTION = "x"\nMODULE_ABI = "brisartos.module.v1"\n'
                'MODULE_PERMISSIONS = ()\n\ndef run(api):\n    raise SystemExit(3)\n')
            result = self.session(folder, 'run quitter\nversion\n')
            self.assertEqual(result.returncode, 3)
            kernel_log = (Path(folder) / 'data' / 'logs' / 'kernel.log').read_text()
            self.assertTrue(kernel_log.rstrip().endswith('kernel: stopped'))
            self.assertIn('module failed: SystemExit: 3', (Path(folder) / 'data' / 'logs' / 'quitter.log').read_text())

    def test_modules_that_fail_to_load_are_reported_at_start(self):
        with tempfile.TemporaryDirectory() as folder:
            broken = Path(folder) / 'modules' / 'broken'
            broken.mkdir(parents=True)
            (broken / 'module.py').write_text('raise RuntimeError("boom")\n')
            result = self.session(folder, 'exit\n', '--memory')
            self.assertIn('module broken not loaded: RuntimeError: boom', result.stdout)


if __name__ == '__main__':
    unittest.main()
