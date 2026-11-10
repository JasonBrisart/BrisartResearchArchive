"""
File: tests/test_export.py

Purpose
-------
Verify the export engine end to end and the settings rules it depends on: outputs and
  manifest, ZIP hashes matching the manifest, identical results with 1 or 8 threads, auto and
  clamped worker counts, single-read capture, Markdown-only redaction, completeness stops,
  cancellation and failure cleanup, unique and flat output folders, output-folder safety,
  pruning, symlinks, embedded fences, settings validation and loading, Git branch names, CPU
  core detection, and that export/ loads without storage, the GUI, tkinter, or urllib.request.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT, IsolatedStateMixin), export/events.py,
  export/git_state.py, export/pipeline.py, export/render.py, and export/settings.py. Run by
  unittest discovery; nothing imports it.

Settings / parameters
---------------------
Each engine test gets a temporary project and points PCH_STATE_DIR at a temporary folder.
  Core counts are patched (export.settings.detect_cpu_cores) where a result depends on them,
  so outcomes do not depend on the test machine.

Edge cases
----------
The symlink test is skipped where unprivileged symlinks are not allowed (common on Windows
  without Developer Mode).

Known limitations
-----------------
Fixture projects are small; behavior on very large projects, network drives, and every
  platform is not covered.

Examples
--------
From the directory containing run.py:

    python -m unittest discover -s tests -p test_export.py -v
"""

from pathlib import Path
from threading import Event
from unittest import mock
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile

from support import APP_ROOT, IsolatedStateMixin

from export.events import BuildCancelled
from export.git_state import build_git_state
from export.pipeline import create_context, validate_root
from export.render import safe_read, source_fence
from export.settings import (
    ScanSettings,
    detect_cpu_cores,
    normalize_extension,
    resolve_workers,
    settings_for_profile,
    validate_settings,
    worker_limit,
)


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
        self.assertEqual(manifest["source_completeness"]["status"], "PASS")
        self.assertEqual(manifest["settings"]["workers"], "auto")
        self.assertGreaterEqual(manifest["summary"]["capture_workers"], 1)
        self.assertEqual(manifest["author"], "Jason Brisart")
        self.assertEqual(manifest["affiliation"], "Brisart Research Archive")
        self.assertNotIn("repository_url", manifest)
        for path in (result.context_path, result.manifest_path, result.summary_path):
            self.assertNotIn("github", path.read_text(encoding="utf-8").lower(), path)
        self.assertIn("Affiliation: **Brisart Research Archive**", result.context_path.read_text(encoding="utf-8"))
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
        one = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.settings.workers = 8
        with mock.patch("export.settings.detect_cpu_cores", return_value=8):
            eight = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(eight["summary"]["capture_workers"], 8)
        self.assertEqual(one["included_files"], eight["included_files"])

    def test_auto_workers_use_every_detected_core(self):
        with mock.patch("export.settings.detect_cpu_cores", return_value=6):
            result = self.build()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["settings"]["workers"], "auto")
        self.assertEqual(manifest["summary"]["capture_workers"], 6)
        self.assertIn("Capture workers: **6 (auto)**", result.context_path.read_text(encoding="utf-8"))
        self.assertIn("Capture workers: 6 (auto)", result.summary_path.read_text(encoding="utf-8"))

    def test_explicit_workers_are_limited_to_detected_cores(self):
        self.settings.workers = 16
        with mock.patch("export.settings.detect_cpu_cores", return_value=4):
            result = self.build()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["settings"]["workers"], 16)
        self.assertEqual(manifest["summary"]["capture_workers"], 4)
        self.assertIn("4 (requested 16, limited to available CPU cores)", result.context_path.read_text(encoding="utf-8"))

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
        with mock.patch("export.pipeline.build_manifest", side_effect=OSError("fixture failure")):
            with self.assertRaises(OSError):
                self.build()
        self.assertEqual(list(self.exports().iterdir()), [])

    def test_same_second_builds_get_unique_folders(self):
        with mock.patch("export.pipeline.timestamp_slug", return_value="20260101_000000"):
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
        for workers in (0, 33, True, "fast", "4", 2.0):
            self.settings.workers = workers
            with self.assertRaises(ValueError, msg=repr(workers)):
                validate_settings(self.settings)
        for workers in ("auto", 1, 32):
            self.settings.workers = workers
            self.assertEqual(validate_settings(self.settings).workers, workers)
        self.settings.workers = 4
        copy = validate_settings(self.settings)
        copy.include_extensions.add(".new")
        self.assertNotIn(".new", self.settings.include_extensions)

    def test_settings_parsing_fixes(self):
        self.assertEqual(ScanSettings.from_jsonable({"max_file_bytes": "--5"}).max_file_bytes, 350000)
        legacy = settings_for_profile("archive").to_jsonable()
        legacy.pop("workers")
        self.assertEqual(ScanSettings.from_jsonable(legacy).workers, "auto")
        self.assertEqual(ScanSettings.from_jsonable({"workers": True}).workers, "auto")
        self.assertEqual(ScanSettings.from_jsonable({"workers": [4]}).workers, "auto")
        self.assertEqual(ScanSettings.from_jsonable({"workers": " AUTO "}).workers, "auto")
        self.assertEqual(ScanSettings.from_jsonable({"workers": 4}).workers, 4)
        self.assertEqual(ScanSettings.from_jsonable({"workers": "6"}).workers, 6)

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

    def test_engine_does_not_load_app_state_gui_or_network(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r});"
            "import export.pipeline;"
            "loaded = [m for m in sys.modules if m.split('.')[0] in ('storage', 'gui', 'tkinter') or m == 'urllib.request'];"
            "assert not loaded, loaded"
        )
        self.assertEqual(subprocess.run([sys.executable, "-c", code], capture_output=True).returncode, 0)


class ExportHelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_extension_normalization_handles_whitespace_and_case(self):
        self.assertEqual(normalize_extension(' PY '), '.py')
        self.assertEqual(normalize_extension(' .JSON '), '.json')
        self.assertEqual(normalize_extension(' '), '')

    def test_redaction_removes_secret_lines_but_preserves_other_lines(self):
        path = self.root / 'settings.txt'
        path.write_text('name = sample\napi_key = private-value\nmode = local', encoding='utf-8')
        result = safe_read(path)
        self.assertNotIn('private-value', result)
        self.assertIn('[[REDACTED POSSIBLE SECRET LINE]]', result)
        self.assertIn('name = sample', result)
        self.assertIn('mode = local', result)

    def test_explicit_unredacted_read_preserves_original(self):
        path = self.root / 'settings.txt'
        value = 'token = fixture-only\n'
        path.write_text(value, encoding='utf-8')
        self.assertEqual(safe_read(path, False), value)

    def test_valid_root_is_resolved(self):
        self.assertEqual(validate_root(self.root), self.root.resolve())

    def test_missing_root_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            validate_root(self.root / 'missing')

    def test_file_instead_of_root_is_rejected(self):
        path = self.root / 'file.txt'
        path.write_text('fixture', encoding='utf-8')
        with self.assertRaises(NotADirectoryError):
            validate_root(path)

    def test_cpu_core_detection_never_reports_zero(self):
        self.assertGreaterEqual(detect_cpu_cores(), 1)
        with mock.patch("export.settings.os.process_cpu_count", create=True, return_value=None):
            self.assertEqual(detect_cpu_cores(), 1)

    def test_worker_resolution(self):
        self.assertEqual(resolve_workers("auto", cores=8), 8)
        self.assertEqual(resolve_workers(3, cores=8), 3)
        self.assertEqual(resolve_workers(16, cores=4), 4)
        self.assertEqual(resolve_workers("auto", cores=64), 32)
        self.assertEqual(worker_limit(1), 1)


if __name__ == "__main__":
    unittest.main()
