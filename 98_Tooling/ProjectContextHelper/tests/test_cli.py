"""
File: tests/test_cli.py

Purpose
-------
Verify the command line through real run.py processes: an export works with --workers and
  --progress, prints the worker count, and is added to history; --workers AUTO is saved as
  auto; bad worker values and output folders outside the project exit 1 without writing
  outside; the removed update flags are rejected; and importing run.py (and with it cli.py)
  loads no tkinter and
  no network module, which keeps command-line use safe for air-gapped machines.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT, IsolatedStateMixin) and starts run.py, which hands off
  to cli.py, with the current Python. Run by unittest discovery.

Settings / parameters
---------------------
PCH_STATE_DIR points at a temporary folder and is passed to every subprocess.

Edge cases
----------
Each test starts at least one Python process, so these are the slower tests.

Known limitations
-----------------
The network check covers what run.py and cli.py import, not what the operating system or Python
  itself might load later.

Examples
--------
From the directory containing run.py:

    python -m unittest discover -s tests -p test_cli.py -v
"""

import json
import os
import subprocess
import sys
import unittest

from support import APP_ROOT, IsolatedStateMixin


class CliTests(IsolatedStateMixin, unittest.TestCase):
    def setUp(self):
        self.isolate()
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "sample.py").write_text("x = 1\n", encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(APP_ROOT / "run.py"), *args], capture_output=True, text=True,
            env=os.environ.copy(), timeout=120,
        )

    def test_cli_loads_no_gui_or_network_code(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r}); import run;"
            "loaded = [m for m in ('tkinter', 'urllib.request', 'http.client', 'webbrowser') if m in sys.modules];"
            "assert not loaded, loaded"
        )
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 0)

    def test_update_flags_are_gone(self):
        self.assertEqual(self.run_cli("--check-updates").returncode, 2)

    def test_cli_export_with_workers_and_progress(self):
        completed = self.run_cli(str(self.project), "--workers", "2", "--progress", "--no-zip")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Build completed", completed.stdout)
        self.assertIn("[capturing]", completed.stderr)
        self.assertIn("Capture Workers: ", completed.stdout)
        history = json.loads((self.state_dir / "build_history.json").read_text(encoding="utf-8"))
        self.assertEqual(len(history), 1)

    def test_cli_accepts_auto_workers(self):
        completed = self.run_cli(str(self.project), "--workers", "AUTO", "--no-zip")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        export = next((self.project / "PROJECT_CONTEXT_EXPORTS").iterdir())
        settings = json.loads((export / "PROJECT_CONTEXT_SETTINGS.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["workers"], "auto")

    def test_cli_rejects_bad_workers_and_outside_output(self):
        self.assertEqual(self.run_cli(str(self.project), "--workers", "0").returncode, 1)
        bad = self.run_cli(str(self.project), "--workers", "fast")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("--workers must be 'auto'", bad.stdout)
        self.assertEqual(self.run_cli(str(self.project), "--output-dir", "../escape").returncode, 1)
        self.assertFalse((self.base / "escape").exists())


if __name__ == "__main__":
    unittest.main()
