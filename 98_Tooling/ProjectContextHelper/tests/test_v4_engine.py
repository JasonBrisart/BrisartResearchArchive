"""
File: tests/test_v4_engine.py

Purpose
-------
Regression tests for the v4.0.0 export engine, persistence, and CLI changes: single-read
  capture, parallel/sequential parity, staging cleanup, cancellation, output-path safety,
  pruning, symlink policy, adaptive fences, settings fixes, locked persistence, and full Git
  State.

Implemented responsibilities:
- EngineTests: Build fixture projects in temporary folders and assert export, manifest, ZIP,
  and skip-record behavior through core.builder.create_context.
- StorageTests: Exercise services.storage locking, corrupt-file protection, preference parsing,
  and temp-file cleanup.
- CliTests: Run run.py in subprocesses to confirm tkinter-free exports and flag handling.
- JobRunnerTests: Confirm the GUI worker controller reports results, errors, and overlap.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.builder: create_context, validate_settings.
- core.constants: settings_for_profile.
- core.events: BuildCancelled.
- core.exporters: source_fence.
- core.git_state: build_git_state.
- core.models: ScanSettings.
- services: storage.
- gui.jobs: JobRunner.

Consumers in the supplied source:
No application module imports this file; it is run by unittest discovery.

Settings / parameters
---------------------
Every test points PCH_STATE_DIR at its own temporary folder, so the real state files beside
  run.py are never read or written.

Function signatures (nested callbacks are scoped to their enclosing function):
Standard unittest setUp/test_* methods; see the class bodies.

Edge cases
----------
The symlink test is skipped on systems where unprivileged symlink creation is not allowed
  (common on Windows without Developer Mode).

Known limitations
-----------------
Fixture-based tests do not prove behavior on every platform, filesystem, or project size, and
  do not exercise the network updater or a real Tk display.

Examples
--------
Usage from the directory containing run.py:

    python -m unittest discover -s tests -v
    python -m unittest discover -s tests -p test_v4_engine.py -v
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest import mock
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from core.builder import create_context, validate_settings
from core.constants import settings_for_profile
from core.events import BuildCancelled
from core.exporters import source_fence
from core.git_state import build_git_state
from core.models import ScanSettings
from services import storage
from gui.jobs import JobRunner


class IsolatedStateMixin:
    def isolate(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.state_dir = self.base / "state"
        patcher = mock.patch.dict(os.environ, {"PCH_STATE_DIR": str(self.state_dir)})
        patcher.start()
        self.addCleanup(patcher.stop)


class EngineTests(IsolatedStateMixin, unittest.TestCase):
    def setUp(self):
        self.isolate()
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "sample.py").write_text("print('hello')\n", encoding="utf-8")
        self.settings = settings_for_profile("archive")

    def build(self, **kwargs):
        return create_context(self.project, self.settings, **kwargs)

    def exports(self):
        return self.project / "PROJECT_CONTEXT_EXPORTS"

    def assert_no_staging(self):
        if self.exports().exists():
            self.assertEqual([p.name for p in self.exports().iterdir() if p.name.startswith(".pch-")], [])

    def test_archive_export_outputs_and_manifest(self):
        result = self.build()
        for path in (result.context_path, result.manifest_path, result.summary_path, result.settings_path, result.snapshot_path):
            self.assertTrue(path.is_file(), path)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "4.0.0")
        self.assertEqual(manifest["source_completeness"]["status"], "PASS")
        self.assertEqual(manifest["settings"]["workers"], 4)
        self.assertEqual(len(storage.load_history()), 1)
        self.assert_no_staging()

    def test_zip_hashes_match_manifest(self):
        result = self.build()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(result.snapshot_path) as archive:
            for record in manifest["included_files"]:
                data = archive.read("project_files/" + Path(record["relative_path"]).as_posix())
                self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])

    def test_sequential_and_parallel_capture_match(self):
        for index in range(25):
            (self.project / f"file_{index:02}.txt").write_text(f"line {index}\n" * index, encoding="utf-8")
        self.settings.workers = 1
        one = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))["included_files"]
        self.settings.workers = 8
        eight = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))["included_files"]
        self.assertEqual(one, eight)

    def test_source_changed_after_capture_does_not_change_outputs(self):
        def progress(event):
            if event.phase == "rendering":
                (self.project / "sample.py").write_text("changed = True\n", encoding="utf-8")
        result = self.build(progress=progress)
        self.assertIn("print('hello')", result.context_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(result.snapshot_path) as archive:
            self.assertEqual(archive.read("project_files/sample.py"), b"print('hello')\n")

    def test_redaction_is_markdown_only(self):
        (self.project / "config.txt").write_text("api_key = fixture-only\n", encoding="utf-8")
        result = self.build()
        self.assertNotIn("fixture-only", result.context_path.read_text(encoding="utf-8"))
        with zipfile.ZipFile(result.snapshot_path) as archive:
            self.assertIn(b"fixture-only", archive.read("project_files/config.txt"))

    def test_completeness_failure_leaves_no_staging(self):
        self.settings.max_file_bytes = 3
        with self.assertRaises(ValueError):
            self.build()
        self.assert_no_staging()

    def test_standard_profile_reports_failures_without_stopping(self):
        self.settings = settings_for_profile("standard")
        self.settings.max_file_bytes = 3
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_completeness"]["status"], "FAIL")

    def test_cancel_before_start(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(BuildCancelled):
            self.build(cancel=cancel)
        self.assertFalse(self.exports().exists())

    def test_cancel_during_render_cleans_staging(self):
        cancel = Event()
        with self.assertRaises(BuildCancelled):
            self.build(cancel=cancel, progress=lambda e: cancel.set() if e.phase == "rendering" else None)
        self.assertEqual(list(self.exports().iterdir()), [])

    def test_render_failure_cleans_staging(self):
        with mock.patch("core.builder.build_manifest", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                self.build()
        self.assertEqual(list(self.exports().iterdir()), [])

    def test_same_second_builds_get_unique_folders(self):
        with mock.patch("core.builder.timestamp_slug", return_value="20260101_000000"):
            first = self.build().export_dir
            second = self.build().export_dir
        self.assertNotEqual(first, second)
        self.assertEqual(second.name, "project_context_20260101_000000_2")

    def test_flat_output_overwrites_like_v3(self):
        self.settings.timestamped_export_folder = False
        first = self.build()
        second = self.build()
        self.assertEqual(first.export_dir, self.exports())
        self.assertTrue(second.context_path.is_file())
        self.assert_no_staging()

    def test_custom_output_folder_is_excluded_from_scan_and_tree(self):
        self.settings.output_dir_name = "my_exports"
        self.build()
        result = self.build()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual([r["relative_path"] for r in manifest["included_files"]], ["sample.py"])
        self.assertNotIn("my_exports", result.context_path.read_text(encoding="utf-8").split("## Folder Tree")[1].split("##")[0])

    def test_output_folder_must_stay_inside_project(self):
        for name in ("../outside", str(self.base / "absolute"), "C:\\outside", "a/../../b", "."):
            self.settings.output_dir_name = name
            with self.assertRaises(ValueError, msg=name):
                self.build()

    def test_excluded_directory_is_pruned_to_one_record(self):
        modules = self.project / "Node_Modules"
        modules.mkdir()
        for index in range(5):
            (modules / f"m{index}.js").write_text("x", encoding="utf-8")
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        reasons = [r["reason"] for r in manifest["skipped_files"]]
        self.assertEqual(reasons.count("excluded_directory:Node_Modules"), 1)

    def test_symlinks_are_skipped(self):
        try:
            (self.project / "link.py").symlink_to(self.project / "sample.py")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertIn("symlink_not_followed", [r["reason"] for r in manifest["skipped_files"]])
        self.assertEqual(manifest["summary"]["included_count"], 1)

    def test_internal_files_are_skipped(self):
        (self.project / ".pch-custom_profiles.json.abc.tmp").write_text("{}", encoding="utf-8")
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertIn("internal_tool_file", [r["reason"] for r in manifest["skipped_files"]])

    def test_compound_extension_still_matches(self):
        (self.project / "config.env.example").write_text("MODE=local\n", encoding="utf-8")
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertIn("config.env.example", [r["relative_path"] for r in manifest["included_files"]])

    def test_embedded_fences_do_not_break_markdown(self):
        (self.project / "notes.md").write_text("```python\nx = 1\n```\n", encoding="utf-8")
        text = self.build().context_path.read_text(encoding="utf-8")
        self.assertIn("````markdown\n```python", text)
        self.assertEqual(source_fence("a ``````` b"), "````````")

    def test_default_settings_use_archive_preset(self):
        result = create_context(self.project)
        self.assertEqual(json.loads(result.settings_path.read_text(encoding="utf-8"))["profile"], "archive")

    def test_settings_validation(self):
        for workers in (0, 33, True):
            self.settings.workers = workers
            with self.assertRaises(ValueError):
                validate_settings(self.settings)
        self.settings.workers = 4
        copy = validate_settings(self.settings)
        copy.include_extensions.add(".new")
        self.assertNotIn(".new", self.settings.include_extensions)

    def test_settings_parsing_fixes(self):
        self.assertEqual(ScanSettings.from_jsonable({"max_file_bytes": "--5"}).max_file_bytes, 350000)
        legacy = settings_for_profile("archive").to_jsonable()
        legacy.pop("workers")
        self.assertEqual(ScanSettings.from_jsonable(legacy).workers, 4)
        self.assertEqual(ScanSettings.from_jsonable({"workers": True}).workers, 4)

    def test_git_state_slash_branch_and_output_exclusion(self):
        git = self.project / ".git"
        (git / "refs" / "heads" / "feature").mkdir(parents=True)
        (git / "HEAD").write_text("ref: refs/heads/feature/test\n", encoding="utf-8")
        (git / "refs" / "heads" / "feature" / "test").write_text("a" * 40, encoding="utf-8")
        state = build_git_state(self.project)
        self.assertEqual(state.branch, "feature/test")
        self.settings.include_git_state = True
        manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["git_state"]["branch"], "feature/test")


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
            "from services import storage; from core.constants import settings_for_profile;"
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
        path.write_text('{"open_after_build": "false", "check_updates_startup": true}', encoding="utf-8")
        prefs = storage.load_preferences()
        self.assertFalse(prefs.open_after_build)
        self.assertTrue(prefs.check_updates_startup)
        path.write_text("[]", encoding="utf-8")
        self.assertEqual(storage.load_preferences(), storage.AppPreferences())

    def test_failed_atomic_write_leaves_no_temp_file(self):
        with mock.patch("services.storage.os.replace", side_effect=OSError("fixture")):
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

    def test_cli_does_not_import_tkinter(self):
        code = f"import sys; sys.path.insert(0, {str(APP_ROOT)!r}); import cli.cli; assert 'tkinter' not in sys.modules"
        self.assertEqual(subprocess.run([sys.executable, "-c", code]).returncode, 0)

    def test_cli_export_with_workers_and_progress(self):
        completed = self.run_cli(str(self.project), "--workers", "2", "--progress", "--no-zip")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("Build completed", completed.stdout)
        self.assertIn("[capturing]", completed.stderr)

    def test_cli_rejects_bad_workers_and_outside_output(self):
        self.assertEqual(self.run_cli(str(self.project), "--workers", "0").returncode, 1)
        self.assertEqual(self.run_cli(str(self.project), "--output-dir", "../escape").returncode, 1)
        self.assertFalse((self.base / "escape").exists())


class JobRunnerTests(unittest.TestCase):
    def test_result_error_and_overlap(self):
        runner = JobRunner()
        runner.start(lambda cancel, emit: 42)
        runner.thread.join(10)
        self.assertEqual(list(runner.drain()), [("done", 42)])

        def fail(cancel, emit):
            raise ValueError("fixture")
        runner.start(fail)
        runner.thread.join(10)
        kind, payload = list(runner.drain())[0]
        self.assertEqual(kind, "error")
        self.assertIsInstance(payload, ValueError)

        gate = Event()
        runner.start(lambda cancel, emit: gate.wait(10))
        try:
            with self.assertRaises(RuntimeError):
                runner.start(lambda cancel, emit: None)
        finally:
            gate.set()
            runner.thread.join(10)


if __name__ == "__main__":
    unittest.main()
