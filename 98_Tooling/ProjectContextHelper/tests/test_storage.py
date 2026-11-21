"""
File: tests/test_storage.py

Purpose
-------
Verify remembered state (application/storage.py): the window half of a custom profile (saved,
  restored, kept when the command line overwrites only the settings, tolerant of wrong types,
  ignored by settings-only readers, absent from v4.2.0 profiles), the per-user folder on each platform,
  one-time migration from beside run.py (every file moved once, nothing overwritten, a failed
  copy keeps the original, four processes released at the same instant move each file exactly once),
  simultaneous profile saves from threads and processes all survive,
  a corrupted custom_profiles.json is never overwritten, preferences accept only real
  booleans and a list of hidden section names, failed writes leave no temp file, a stale lock is recovered, malformed history is
  ignored, record_export adds history and never raises, a v4.0.x saved worker count loads
  unchanged, and importing storage does not load the scanner, renderer, or pipeline.

Communication / relationships
-----------------------------
Imports tests/support.py, application/storage.py, export/pipeline.py, and export/settings.py. Run by
  unittest discovery.

Settings / parameters
---------------------
Every test points PCH_STATE_DIR at its own temporary folder, so real state files beside
  run.py are never read or written. The process test starts four Python
  processes; the pipeline-boundary test starts one.

Edge cases
----------
The process-concurrency test relies on the O_EXCL lock file behaving the same on the test
  filesystem as on the user's.

Known limitations
-----------------
Locking on network filesystems is not tested.

Examples
--------
From the directory containing run.py:

    python -m unittest discover -s tests -p test_storage.py -v
"""

from concurrent.futures import ThreadPoolExecutor
from unittest import mock
import json
import os
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

from support import APP_ROOT, IsolatedStateMixin

from export.pipeline import create_context
from export.settings import ScanSettings, settings_for_profile
from application import storage
from application.identity import STATE_FILENAMES


class StorageTests(IsolatedStateMixin, unittest.TestCase):
    def setUp(self):
        self.isolate()

    def test_concurrent_thread_profile_saves(self):
        settings = settings_for_profile("archive")
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: storage.save_profile(f"p{i}", settings), range(24)))
        self.assertEqual(len(storage.list_profiles()), 24)

    def test_concurrent_process_profile_saves(self):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "from application import storage; from export.settings import settings_for_profile;"
            "storage.save_profile(sys.argv[2], settings_for_profile('archive'))"
        )
        processes = [
            subprocess.Popen([sys.executable, "-c", code, str(APP_ROOT), f"proc{i}"], env=os.environ.copy())
            for i in range(4)
        ]
        for process in processes:
            self.assertEqual(process.wait(timeout=120), 0)
        self.assertEqual(len(storage.list_profiles()), 4)

    def test_corrupt_profiles_file_is_not_overwritten(self):
        self.state_dir.mkdir(parents=True)
        path = self.state_dir / "custom_profiles.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            storage.save_profile("Review", settings_for_profile("archive"))
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")

    def test_preferences_require_real_booleans(self):
        self.state_dir.mkdir(parents=True)
        path = self.state_dir / "app_settings.json"
        path.write_text('{"open_after_build": "false"}', encoding="utf-8")
        self.assertFalse(storage.load_preferences().open_after_build)
        path.write_text('{"open_after_build": true, "check_updates_startup": true}', encoding="utf-8")
        self.assertTrue(storage.load_preferences().open_after_build)
        path.write_text("[]", encoding="utf-8")
        self.assertEqual(storage.load_preferences(), storage.AppPreferences())

    def test_hidden_sections_preference(self):
        self.state_dir.mkdir(parents=True)
        path = self.state_dir / "app_settings.json"
        path.write_text('{"hidden_sections": ["extras_git", 3, null, "options_help"]}', encoding="utf-8")
        self.assertEqual(storage.load_preferences().hidden_sections, ("extras_git", "options_help"))
        path.write_text('{"hidden_sections": "extras_git"}', encoding="utf-8")
        self.assertEqual(storage.load_preferences().hidden_sections, ())
        storage.save_preferences(storage.AppPreferences(hidden_sections=("b", "a", "b")))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["hidden_sections"], ["a", "b"])

    def test_profile_window_half_round_trips_and_survives_settings_only_saves(self):
        settings = settings_for_profile("archive")
        window = storage.ProfileWindow(storage.AppPreferences(True, ("options_help", "extras_git", "options_help")), "/labs/alice")
        storage.save_profile("Alice", settings, window=window)
        loaded = storage.load_profile_window("Alice")
        self.assertEqual(loaded, storage.ProfileWindow(storage.AppPreferences(True, ("extras_git", "options_help")), "/labs/alice"))
        self.assertEqual(storage.load_profile("Alice"), settings)
        changed = settings_for_profile("standard")
        storage.save_profile("Alice", changed)
        self.assertEqual(storage.load_profile("Alice"), changed)
        self.assertEqual(storage.load_profile_window("Alice"), loaded)
        storage.save_profile("Alice", changed, window=storage.ProfileWindow(storage.AppPreferences(), ""))
        self.assertEqual(storage.load_profile_window("Alice"), storage.ProfileWindow(storage.AppPreferences(False, ()), ""))
        storage.save_profile("Plain", settings)
        self.assertIsNone(storage.load_profile_window("Plain"))
        self.assertIsNone(storage.load_profile_window("Missing"))

    def test_profile_window_parsing_ignores_wrong_types(self):
        entry = settings_for_profile("archive").to_jsonable()
        entry["window"] = {"open_after_build": "yes", "hidden_sections": ["a", 3, None], "project_folder": 7}
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "custom_profiles.json").write_text(json.dumps({"profiles": {"Odd": entry, "NotADict": {**entry, "window": [1]}}}), encoding="utf-8")
        self.assertEqual(storage.load_profile_window("Odd"), storage.ProfileWindow(storage.AppPreferences(False, ("a",)), ""))
        self.assertIsNone(storage.load_profile_window("NotADict"))

    def test_settings_readers_ignore_the_window_half_and_v420_profiles_still_load(self):
        settings = settings_for_profile("archive")
        entry = {**settings.to_jsonable(), "window": {"open_after_build": True, "hidden_sections": ["x"], "project_folder": "/p"}}
        self.assertEqual(ScanSettings.from_jsonable(entry), settings)
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "custom_profiles.json").write_text(json.dumps({"profiles": {"Old": settings.to_jsonable()}}), encoding="utf-8")
        self.assertEqual(storage.load_profile("Old"), settings)
        self.assertIsNone(storage.load_profile_window("Old"))

    def test_failed_atomic_write_leaves_no_temp_file(self):
        with mock.patch("application.storage.os.replace", side_effect=OSError("fixture")):
            with self.assertRaises(OSError):
                storage.save_profile("Review", settings_for_profile("archive"))
        self.assertEqual([p.name for p in self.state_dir.iterdir()], [])

    def test_stale_lock_is_recovered(self):
        self.state_dir.mkdir(parents=True)
        lock = self.state_dir / storage.LOCK_FILENAME
        lock.write_text("999999", encoding="utf-8")
        old = lock.stat().st_mtime - 120
        os.utime(lock, (old, old))
        storage.save_profile("Review", settings_for_profile("archive"))
        self.assertEqual(storage.list_profiles(), ["Review"])

    def test_history_ignores_bad_shapes(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "build_history.json").write_text('{"not": "a list"}', encoding="utf-8")
        self.assertEqual(storage.load_history(), [])
        (self.state_dir / "build_history.json").write_text('[1, "x", null]', encoding="utf-8")
        self.assertEqual(storage.load_history(), [])

    def test_record_export_adds_history_and_never_raises(self):
        project = self.base / "project"
        project.mkdir()
        (project / "a.py").write_text("x = 1\n", encoding="utf-8")
        settings = settings_for_profile("standard")
        result = create_context(project, settings)
        storage.record_export(result, settings)
        entry = storage.load_history()[0]
        self.assertEqual((entry.profile, entry.included_count, entry.export_dir), ("standard", 1, str(result.export_dir)))
        with mock.patch("application.storage.append_history_entry", side_effect=TimeoutError("busy")):
            storage.record_export(result, settings)

    def test_storage_does_not_load_the_export_pipeline(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r}); import application.storage;"
            "loaded = [m for m in ('export.pipeline', 'export.scan', 'export.render') if m in sys.modules];"
            "assert not loaded, loaded"
        )
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 0)

    def test_per_user_state_folder_by_platform(self):
        home = Path("/home/jason")
        expected = lambda root: Path(root) / "Brisart Research Archive" / "Project Context Helper"
        self.assertEqual(storage.per_user_state_dir("nt", "win32", {"APPDATA": "/u/AppData/Roaming"}, home), expected("/u/AppData/Roaming"))
        self.assertEqual(storage.per_user_state_dir("nt", "win32", {}, home), expected(home / "AppData" / "Roaming"))
        self.assertEqual(storage.per_user_state_dir("posix", "darwin", {}, home), expected(home / "Library" / "Application Support"))
        self.assertEqual(storage.per_user_state_dir("posix", "linux", {"XDG_CONFIG_HOME": "/cfg"}, home), expected("/cfg"))
        self.assertEqual(storage.per_user_state_dir("posix", "linux", {}, home), expected(home / ".config"))

    def test_default_state_folder_is_per_user_not_beside_run_py(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("PCH_STATE_DIR", None)
            self.assertEqual(storage.application_dir(), storage.per_user_state_dir())
            self.assertNotEqual(storage.application_dir(), APP_ROOT)
            self.assertEqual(storage.legacy_state_dir(), APP_ROOT)
            self.assertTrue((APP_ROOT / "run.py").is_file())

    def migration_fixture(self):
        legacy, target = self.base / "legacy", self.base / "AppData" / "Brisart Research Archive" / "Project Context Helper"
        legacy.mkdir()
        contents = {name: f'{{"name": "{name}"}}\n'.encode("utf-8") for name in STATE_FILENAMES}
        for name, data in contents.items():
            (legacy / name).write_bytes(data)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("PCH_STATE_DIR", None)
        patch = mock.patch.object(storage, "per_user_state_dir", return_value=target)
        patch.start()
        self.addCleanup(patch.stop)
        return legacy, target, contents

    def test_migration_moves_every_state_file_once(self):
        legacy, target, contents = self.migration_fixture()
        self.assertEqual(storage.migrate_legacy_state(legacy), list(STATE_FILENAMES))
        for name, data in contents.items():
            self.assertEqual((target / name).read_bytes(), data)
            self.assertFalse((legacy / name).exists())
        self.assertEqual(storage.migrate_legacy_state(legacy), [])
        self.assertEqual(sorted(p.name for p in target.iterdir()), sorted(STATE_FILENAMES))

    def test_migration_never_overwrites_newer_state(self):
        legacy, target, contents = self.migration_fixture()
        target.mkdir(parents=True)
        (target / "custom_profiles.json").write_text('{"newer": true}', encoding="utf-8")
        moved = storage.migrate_legacy_state(legacy)
        self.assertNotIn("custom_profiles.json", moved)
        self.assertEqual(json.loads((target / "custom_profiles.json").read_text(encoding="utf-8")), {"newer": True})
        self.assertTrue((legacy / "custom_profiles.json").exists())

    def test_migration_is_skipped_for_explicit_folder_and_same_folder(self):
        legacy, target, contents = self.migration_fixture()
        with mock.patch.dict(os.environ, {"PCH_STATE_DIR": str(self.base / "chosen")}):
            self.assertEqual(storage.migrate_legacy_state(legacy), [])
        self.assertTrue(all((legacy / name).exists() for name in STATE_FILENAMES))
        self.assertFalse((self.base / "chosen").exists() or target.exists())
        with mock.patch.object(storage, "per_user_state_dir", return_value=legacy):
            self.assertEqual(storage.migrate_legacy_state(legacy), [])

    def test_failed_copy_keeps_the_original(self):
        legacy, target, contents = self.migration_fixture()
        with mock.patch.object(storage, "_atomic_copy", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                storage.migrate_legacy_state(legacy)
        self.assertTrue(all((legacy / name).read_bytes() == contents[name] for name in STATE_FILENAMES))
        self.assertFalse(any((target / name).exists() for name in STATE_FILENAMES))

    def test_simultaneous_processes_move_each_file_exactly_once(self):
        legacy, target, contents = self.migration_fixture()
        # Copying a tiny file takes microseconds, so without help the processes would finish one
        # after another even without the lock. Each one therefore pauses inside the copy, and
        # all four wait at a gate until every one has started, so they overlap unless the lock
        # really serializes them.
        gate = self.base / "gate"
        gate.mkdir()
        code = textwrap.dedent("""
            import json, os, sys, time
            sys.path.insert(0, sys.argv[1])
            from pathlib import Path
            from application import storage
            real_copy = storage._atomic_copy
            storage._atomic_copy = lambda source, destination: (time.sleep(0.15), real_copy(source, destination))[1]
            gate = Path(sys.argv[3])
            (gate / f"ready{os.getpid()}").touch()
            while not (gate / "go").exists():
                time.sleep(0.05)
            print(json.dumps(storage.migrate_legacy_state(Path(sys.argv[2]))))
        """)
        env = {k: v for k, v in os.environ.items() if k != "PCH_STATE_DIR"}
        home = str(self.base / "home")
        env.update(APPDATA=home, XDG_CONFIG_HOME=home, HOME=home, USERPROFILE=home)
        processes = [
            subprocess.Popen([sys.executable, "-c", code, str(APP_ROOT), str(legacy), str(gate)], env=env, stdout=subprocess.PIPE, text=True)
            for _ in range(4)
        ]
        deadline = time.monotonic() + 60
        while len(list(gate.glob("ready*"))) < 4 and time.monotonic() < deadline:
            time.sleep(0.05)
        (gate / "go").touch()
        moved = [name for p in processes for name in json.loads(p.communicate()[0] or "[]")]
        self.assertTrue(all(p.returncode == 0 for p in processes))
        self.assertEqual(sorted(moved), sorted(STATE_FILENAMES))
        final = Path(home) / "Brisart Research Archive" / "Project Context Helper"
        self.assertEqual({p.name: p.read_bytes() for p in final.iterdir() if not p.name.startswith(".pch-")}, contents)
        self.assertFalse(any((legacy / name).exists() for name in STATE_FILENAMES))

    def test_saved_v40_settings_keep_explicit_workers(self):
        self.state_dir.mkdir(parents=True)
        legacy = settings_for_profile("archive").to_jsonable()
        legacy["workers"] = 4
        (self.state_dir / "last_export_settings.json").write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(storage.load_last_settings().workers, 4)


if __name__ == "__main__":
    unittest.main()
