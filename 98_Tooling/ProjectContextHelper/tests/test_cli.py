"""
File: tests/test_cli.py

Purpose
-------
Verify the command line through real run.py processes: an export works with --workers and
  --progress, prints the worker count, and is added to history; --workers AUTO is saved as
  auto; bad worker values and output folders outside the project exit 1 without writing
  outside; a profile saved by the window (settings plus window half) loads from the command
  line and a command-line save keeps the window half; settings that would silently do nothing
  (an empty extension list, a path as a folder or file exclusion) fail with a clear message;
  no module other than run.py can start the program; the removed update flags are rejected; the first run after upgrading from
  v4.2.0 moves settings saved beside run.py into the per-user folder (and warns, keeping the
  originals, when it cannot); and importing run.py (and with it cli.py)
  loads no tkinter and
  no network module, which keeps command-line use safe for air-gapped machines.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT, IsolatedStateMixin) and export/settings.py, and starts run.py, which hands off
  to cli.py, with the current Python. Run by unittest discovery.

Settings / parameters
---------------------
PCH_STATE_DIR points at a temporary folder and is passed to every subprocess, except the
  upgrade tests: they copy the application, remove PCH_STATE_DIR, and point APPDATA,
  XDG_CONFIG_HOME, HOME, and USERPROFILE at a temporary home so no real state is touched.

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
import shutil
import subprocess
import sys
import unittest

from support import APP_ROOT, IsolatedStateMixin

from application import storage
from export.settings import settings_for_profile


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

    def upgraded_install(self):
        """A copy of the app with v4.2.0-style state beside run.py, and a clean per-user home."""
        install = self.base / "install"
        shutil.copytree(APP_ROOT, install, ignore=shutil.ignore_patterns("tests", "docs", "__pycache__", "*.json"))
        # Written by the real storage code (as v4.2.0 did) so the fixture cannot drift from the format.
        storage.save_profile("Review", settings_for_profile("archive"), install)
        storage.save_preferences(storage.AppPreferences(open_after_build=True), install)
        home = self.base / "home"
        env = {k: v for k, v in os.environ.items() if k != "PCH_STATE_DIR"}
        env.update(APPDATA=str(home), XDG_CONFIG_HOME=str(home), HOME=str(home), USERPROFILE=str(home))
        return install, home / "Brisart Research Archive" / "Project Context Helper", env

    def run_install(self, install, env, *args):
        return subprocess.run([sys.executable, str(install / "run.py"), *args], capture_output=True, text=True, env=env, timeout=120)

    def test_first_run_after_upgrade_moves_saved_settings_and_keeps_working(self):
        install, state, env = self.upgraded_install()
        first = self.run_install(install, env, "--list-profiles")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Review", first.stdout)
        self.assertIn("Moved saved settings", first.stderr)
        self.assertTrue((state / "custom_profiles.json").exists() and (state / "app_settings.json").exists())
        self.assertTrue(storage.load_preferences(state).open_after_build)
        self.assertEqual(list(install.glob("*.json")), [])
        second = self.run_install(install, env, "--list-profiles")
        self.assertIn("Review", second.stdout)
        self.assertNotIn("Moved", second.stderr)
        export = self.run_install(install, env, str(self.project), "--no-zip", "--remember-settings")
        self.assertEqual(export.returncode, 0, export.stderr)
        self.assertTrue((state / "last_export_settings.json").exists())
        self.assertEqual(list(install.glob("*.json")), [])

    def test_failed_migration_warns_and_keeps_originals(self):
        install, state, env = self.upgraded_install()
        state.parent.mkdir(parents=True)
        state.write_text("this is a file, so the settings folder cannot be created", encoding="utf-8")
        result = self.run_install(install, env, "--list-profiles")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Warning: could not move saved settings", result.stderr)
        self.assertIn(str(install), result.stderr)
        self.assertTrue((install / "custom_profiles.json").exists() and (install / "app_settings.json").exists())

    def test_profile_saved_by_the_window_works_from_the_command_line(self):
        wanted = settings_for_profile("archive")
        wanted.exclude_dirs.add("skipme")
        wanted.include_snapshot_zip = False
        storage.save_profile(
            "Lab", wanted,
            window=storage.ProfileWindow(storage.AppPreferences(True, ("options_help",)), "/some/other/computer"),
        )
        (self.project / "skipme").mkdir()
        (self.project / "skipme" / "hidden.py").write_text("y = 2\n", encoding="utf-8")
        completed = self.run_cli(str(self.project), "--load-profile", "Lab")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        export = next((self.project / "PROJECT_CONTEXT_EXPORTS").iterdir())
        manifest = json.loads((export / "PROJECT_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertIn("excluded_directory:skipme", [r["reason"] for r in manifest["skipped_files"]])
        self.assertFalse((export / "PROJECT_SNAPSHOT.zip").exists())
        saved = self.run_cli(str(self.project), "--load-profile", "Lab", "--no-contents", "--save-profile", "Lab")
        self.assertEqual(saved.returncode, 0, saved.stdout + saved.stderr)
        self.assertEqual(storage.load_profile_window("Lab").project_folder, "/some/other/computer")
        self.assertFalse(storage.load_profile("Lab").include_file_contents)

    def test_settings_that_would_do_nothing_fail_clearly(self):
        for args, text in (
            (("--extensions", ","), "include_extensions is empty"),
            (("--exclude-dir", "a/b"), "single name"),
            (("--exclude-file", "a\\b"), "single name"),
        ):
            completed = self.run_cli(str(self.project), "--no-zip", *args)
            self.assertEqual(completed.returncode, 1, args)
            self.assertIn(text, completed.stdout, args)
        self.assertFalse((self.project / "PROJECT_CONTEXT_EXPORTS").exists())

    def test_only_run_py_starts_the_program(self):
        # Every launch must pass through cli.main, which moves settings saved by older releases
        # before anything reads them; a module with its own __main__ guard would skip that.
        for folder in ("application", "export", "gui"):
            for path in (APP_ROOT / folder).glob("*.py"):
                self.assertNotIn('__name__ == "__main__"', path.read_text(encoding="utf-8"), path)
        self.assertNotIn("__main__", (APP_ROOT / "cli.py").read_text(encoding="utf-8"))

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
