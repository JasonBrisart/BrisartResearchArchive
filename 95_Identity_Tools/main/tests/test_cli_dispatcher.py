"""
File: tests/test_cli_dispatcher.py

Purpose
-------
Tests for cli.py's dispatcher (the fast paths that do not import a tool).

Verifies: cli.py, version.py, and that the gui command reaches app.py.
Contains 10 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- cli (cli.py)
- version (version.py)
- app (app.py) -- imported only by the gui test, with main() patched out
- biometrics.app, vault.app, packages.main -- imported by the exit-status
  tests, with main() patched out
Standard library: contextlib, io, unittest, unittest.mock (tkinter is probed,
not required).
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
- Version prints the ecosystem version.
- Help returns zero.
- Help flags are aliases.
- No arguments returns two.
- Unknown tool returns two.
- Every documented tool is dispatchable.
- The gui command resolves to the root-level app.py and calls its main().
- The biometrics command returns the tool's own exit status.
- The vault command returns the tool's own exit status.
- The package command returns the tool's own exit status.

Known limitations
-----------------
- Passing proves only the 10 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.
- The gui test is skipped when tkinter is not installed. It never opens a
  window, so it does not need a display.

Examples
--------
::

    python -m unittest tests.test_cli_dispatcher -v
    python tests/run_tests.py
"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

try:
    import tkinter  # noqa: F401 -- probe only; app.py needs it at import time
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False

import cli
from version import __version__


class CliDispatcherTests(unittest.TestCase):
    def test_version_prints_the_ecosystem_version(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = cli.main(["version"])
        self.assertEqual(code, 0)
        self.assertIn(__version__, buffer.getvalue())

    def test_help_returns_zero(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["help"]), 0)

    def test_help_flags_are_aliases(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--help"]), 0)
            self.assertEqual(cli.main(["-h"]), 0)

    def test_no_arguments_returns_two(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main([]), 2)

    def test_unknown_tool_returns_two(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["not-a-real-tool"]), 2)

    def test_every_documented_tool_is_dispatchable(self):
        for tool in ("biometrics", "vault", "package", "gui", "version", "help"):
            self.assertIn(tool, cli._DISPATCH)

    @unittest.skipUnless(_HAS_TKINTER, "tkinter not installed")
    def test_gui_command_launches_root_app_shell(self):
        import app as gui_shell
        with mock.patch.object(gui_shell, "main") as fake_main:
            self.assertEqual(cli.main(["gui"]), 0)
        fake_main.assert_called_once_with()

    def _assert_exit_status_passes_through(self, tool, module):
        for status in (0, 1, 2):
            with mock.patch.object(module, "main", return_value=status):
                self.assertEqual(cli.main([tool]), status)

    def test_biometrics_exit_status_passes_through(self):
        from biometrics import app as biometrics_app
        self._assert_exit_status_passes_through("biometrics", biometrics_app)

    def test_vault_exit_status_passes_through(self):
        from vault import app as vault_app
        self._assert_exit_status_passes_through("vault", vault_app)

    def test_package_exit_status_passes_through(self):
        from packages import main as package_main
        self._assert_exit_status_passes_through("package", package_main)


if __name__ == "__main__":
    unittest.main()




