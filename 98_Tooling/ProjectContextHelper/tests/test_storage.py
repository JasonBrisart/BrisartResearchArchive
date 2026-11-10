"""
File: tests/test_storage.py

Purpose
-------
Verify remembered state: simultaneous profile saves from threads and processes all survive,
  a corrupted custom_profiles.json is never overwritten, preferences accept only real
  booleans, failed writes leave no temp file, a stale lock is recovered, malformed history is
  ignored, record_export adds history and never raises, a v4.0.x saved worker count loads
  unchanged, and importing storage does not load the scanner, renderer, or pipeline.

Communication / relationships
-----------------------------
Imports tests/support.py, storage, export/pipeline.py, and export/settings.py. Run by
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
import unittest

from support import APP_ROOT, IsolatedStateMixin

from export.pipeline import create_context
from export.settings import settings_for_profile
import storage


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
            "import storage; from export.settings import settings_for_profile;"
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

    def test_failed_atomic_write_leaves_no_temp_file(self):
        with mock.patch("storage.os.replace", side_effect=OSError("fixture")):
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
        with mock.patch("storage.append_history_entry", side_effect=TimeoutError("busy")):
            storage.record_export(result, settings)

    def test_storage_does_not_load_the_export_pipeline(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r}); import storage;"
            "loaded = [m for m in ('export.pipeline', 'export.scan', 'export.render') if m in sys.modules];"
            "assert not loaded, loaded"
        )
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 0)

    def test_saved_v40_settings_keep_explicit_workers(self):
        self.state_dir.mkdir(parents=True)
        legacy = settings_for_profile("archive").to_jsonable()
        legacy["workers"] = 4
        (self.state_dir / "last_export_settings.json").write_text(json.dumps(legacy), encoding="utf-8")
        self.assertEqual(storage.load_last_settings().workers, 4)


if __name__ == "__main__":
    unittest.main()
