"""
File: tests/support.py

Purpose
-------
Hold the setup every test file shares: APP_ROOT (the folder containing run.py), putting it on
  sys.path so application modules import, and IsolatedStateMixin, which gives a test its own
  temporary folder and points PCH_STATE_DIR at it.

Communication / relationships
-----------------------------
Imports nothing from the application. Imported by tests/test_export.py, tests/test_storage.py,
  tests/test_cli.py (APP_ROOT, IsolatedStateMixin), and tests/test_gui.py (APP_ROOT).
  unittest discovery puts tests/ on sys.path, which is how the test files find it.

Settings / parameters
---------------------
IsolatedStateMixin.isolate() sets self.base (a fresh temporary folder, removed after the test)
  and self.state_dir (base/state, not created until something writes to it), and patches
  PCH_STATE_DIR for the rest of the test.

Edge cases
----------
The PCH_STATE_DIR patch covers subprocesses only when the test passes os.environ to them, as
  the CLI and storage process tests do.

Known limitations
-----------------
Real state files beside run.py are protected only for tests that call isolate() or set
  PCH_STATE_DIR themselves (the GUI scenarios set it per process).

Examples
--------
From a test file in tests/:

    import unittest
    from support import IsolatedStateMixin

    class ExampleTests(IsolatedStateMixin, unittest.TestCase):
        def setUp(self):
            self.isolate()
"""

from pathlib import Path
from unittest import mock
import os
import sys
import tempfile

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


class IsolatedStateMixin:
    def isolate(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state_dir = self.base / "state"
        patcher = mock.patch.dict(os.environ, {"PCH_STATE_DIR": str(self.state_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)
