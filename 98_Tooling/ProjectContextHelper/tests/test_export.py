"""
File: tests/test_export.py

Purpose
-------
Verify the export engine end to end and the settings rules it depends on: outputs and
  manifest, ZIP hashes matching the manifest, the parallel ZIP writer (valid, ordered, block
  boundaries, forced ZIP64 records, members keeping each file's real modification time and a
  time the operating system cannot convert becoming 1980), compound-suffix and case-insensitive
  extension rules, settings that would silently do nothing being rejected, a file that cannot be
  staged being reported instead of aborting, Brisart Custom Code (.bcc) sources exported by both
  profiles with a bcc fence hint while compiled .bccbin artifacts stay out, the fast line
  count and redaction matching their
  reference rules exactly, Git State pruning excluded folders, identical results with 1 or 8 threads, auto and
  clamped worker counts, single-read capture, Markdown-only redaction, completeness stops,
  cancellation and failure cleanup, unique and flat output folders, output-folder safety,
  pruning, symlinks, embedded fences, settings validation and loading, Git branch names, CPU
  core detection, that export/ loads without application/storage.py, the GUI, tkinter, or
  urllib.request, and that application/identity.py imports nothing else.

Communication / relationships
-----------------------------
Imports tests/support.py (APP_ROOT, IsolatedStateMixin), export/events.py,
  export/git_state.py, export/pipeline.py, export/render.py, export/scan.py,
  export/snapshot.py, and export/settings.py. Run by
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
import os
import random
import time
import zlib
import subprocess
import sys
import tempfile
import unittest
import zipfile

from support import APP_ROOT, IsolatedStateMixin

from export.events import BuildCancelled
from export.git_state import build_git_state
from export.pipeline import create_context, validate_root
from export.render import _SECRET_PATTERN, safe_read, source_fence
from export.scan import count_lines
import export.snapshot as snapshot
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

    def test_zip_members_keep_the_original_modification_time(self):
        kept = time.mktime((2020, 1, 2, 3, 4, 6, 0, 0, -1))
        ancient = time.mktime((1975, 6, 7, 8, 9, 10, 0, 0, -1))
        (self.project / "old.py").write_text("z = 3\n", encoding="utf-8")
        os.utime(self.project / "sample.py", (kept, kept))
        os.utime(self.project / "old.py", (ancient, ancient))
        with zipfile.ZipFile(self.build().snapshot_path) as archive:
            self.assertEqual(archive.getinfo("project_files/sample.py").date_time, (2020, 1, 2, 3, 4, 6))
            self.assertEqual(archive.getinfo("project_files/old.py").date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(archive.getinfo("PROJECT_CONTEXT.md").date_time[0], time.localtime().tm_year)

    def test_unconvertible_file_times_become_1980_instead_of_failing(self):
        path = self.base / "a.txt"
        path.write_text("x", encoding="utf-8")
        zip_path = self.base / "t.zip"
        with mock.patch("export.snapshot.time.localtime", side_effect=OSError(22, "Invalid argument")):
            snapshot.write_zip(zip_path, [(path, "a.txt")], workers=1)
        with zipfile.ZipFile(zip_path) as archive:
            self.assertEqual(archive.getinfo("a.txt").date_time, (1980, 1, 1, 0, 0, 0))

    def test_compound_suffixes_and_configured_case_apply_to_exclusions(self):
        (self.project / "deep").mkdir()
        for name in ("app.js", "app.min.js", "notes.toml", "x.tmp", "deep/lib.MIN.JS"):
            (self.project / name).write_text("v = 1\n", encoding="utf-8")
        self.settings.include_extensions |= {".js", ".TOML"}
        self.settings.exclude_suffixes |= {".min.js", ".TMP"}
        result = self.build()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        included = {Path(r["relative_path"]).as_posix() for r in manifest["included_files"]}
        skipped = {Path(r["relative_path"]).as_posix(): r["reason"] for r in manifest["skipped_files"]}
        self.assertTrue({"app.js", "notes.toml"} <= included, included)
        self.assertEqual(skipped["app.min.js"], "excluded_suffix:.min.js")
        self.assertEqual(skipped["deep/lib.MIN.JS"], "excluded_suffix:.min.js")
        self.assertEqual(skipped["x.tmp"], "excluded_suffix:.tmp")
        tree = result.context_path.read_text(encoding="utf-8").split("## Folder Tree")[1].split("## File Index")[0]
        self.assertIn("app.js", tree)
        self.assertNotIn("min.js", tree.lower())

    def test_settings_that_would_silently_do_nothing_are_rejected(self):
        cases = (
            (lambda s: s.include_extensions.clear(), "include_extensions is empty"),
            (lambda s: setattr(s, "include_extensions", {"py"}), "must start with a dot"),
            (lambda s: s.exclude_suffixes.add("min.js"), "must start with a dot"),
            (lambda s: s.exclude_dirs.add("lib/gen"), "single name"),
            (lambda s: s.exclude_files.add("lib\\gen.py"), "single name"),
        )
        for change, message in cases:
            with self.subTest(message=message):
                self.settings = settings_for_profile("archive")
                change(self.settings)
                with self.assertRaisesRegex(ValueError, message):
                    validate_settings(self.settings)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()
        self.assertFalse(self.exports().exists())
        for profile in ("standard", "archive"):
            validate_settings(settings_for_profile(profile))

    def test_a_file_that_cannot_be_staged_is_reported_instead_of_aborting(self):
        (self.project / "deep").mkdir()
        (self.project / "deep" / "gen.py").write_text("y = 2\n", encoding="utf-8")
        real = Path.write_bytes
        def refuse(path, data):
            if path.name == "gen.py":
                raise OSError(36, "File name too long")
            return real(path, data)
        self.settings = settings_for_profile("standard")
        with mock.patch.object(Path, "write_bytes", refuse):
            manifest = json.loads(self.build().manifest_path.read_text(encoding="utf-8"))
        reasons = {Path(r["relative_path"]).as_posix(): r["reason"] for r in manifest["skipped_files"]}
        self.assertEqual(reasons["deep/gen.py"], "read_unavailable")
        self.assertEqual([r["relative_path"] for r in manifest["included_files"]], ["sample.py"])
        self.assertEqual(manifest["source_completeness"]["status"], "FAIL")
        self.settings = settings_for_profile("archive")
        with mock.patch.object(Path, "write_bytes", refuse):
            with self.assertRaisesRegex(ValueError, "gen.py"):
                self.build()
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

    def test_bcc_source_is_exported_in_both_profiles(self):
        (self.project / "app.bcc").write_text('do greet(name: Text):\n    return "Hi " + name\n', encoding="utf-8")
        (self.project / "app.bccbin").write_text("compiled artifact", encoding="utf-8")
        for profile in ("standard", "archive"):
            self.settings = settings_for_profile(profile)
            self.settings.include_file_contents = True
            result = self.build()
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            included = {r["relative_path"]: r["extension"] for r in manifest["included_files"]}
            skipped = {r["relative_path"]: r["reason"] for r in manifest["skipped_files"]}
            self.assertEqual(included.get("app.bcc"), ".bcc", profile)
            self.assertEqual(skipped.get("app.bccbin"), "extension_not_included", profile)
            self.assertIn("```bcc\ndo greet(name: Text):", result.context_path.read_text(encoding="utf-8"))

    def test_zip_is_valid_ordered_and_parallel_safe(self):
        (self.project / "big.txt").write_bytes(b"block " * 300_000)
        (self.project / "empty.txt").write_bytes(b"")
        (self.project / "unicod\u00e9.txt").write_text("caf\u00e9\n", encoding="utf-8")
        self.settings.workers = 4
        with mock.patch("export.settings.detect_cpu_cores", return_value=4), mock.patch.object(snapshot, "BLOCK_BYTES", 65536):
            result = self.build()
        with zipfile.ZipFile(result.snapshot_path) as archive:
            self.assertIsNone(archive.testzip())
            names = archive.namelist()
            self.assertEqual(names[:4], ["PROJECT_CONTEXT.md", "PROJECT_MANIFEST.json", "PROJECT_SUMMARY.txt", "PROJECT_CONTEXT_SETTINGS.json"])
            self.assertEqual(archive.read("project_files/big.txt"), b"block " * 300_000)
            self.assertEqual(archive.read("project_files/empty.txt"), b"")
            self.assertEqual(archive.read("PROJECT_CONTEXT.md"), result.context_path.read_bytes())
            self.assertIn("project_files/unicod\u00e9.txt", names)

    def test_zip64_records_round_trip(self):
        members = []
        for name, data in (("a.txt", b"x" * 300_000), ("b.bin", os.urandom(70_000)), ("c.txt", b"")):
            path = self.base / name
            path.write_bytes(data)
            members.append((path, f"project_files/{name}"))
        zip_path = self.base / "forced64.zip"
        with mock.patch.multiple(snapshot, ZIP64_LIMIT=1000, ZIP64_COUNT_LIMIT=2, BLOCK_BYTES=32768, IN_FLIGHT_BYTES=50_000):
            snapshot.write_zip(zip_path, members, workers=3)
        with zipfile.ZipFile(zip_path) as archive:
            self.assertIsNone(archive.testzip())
            for path, name in members:
                self.assertEqual(archive.read(name), path.read_bytes())

    def test_git_state_prunes_excluded_folders(self):
        git = self.project / ".git"
        def store(kind, body):
            raw = f"{kind} {len(body)}\0".encode() + body
            sha = hashlib.sha1(raw).hexdigest()
            target = git / "objects" / sha[:2] / sha[2:]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zlib.compress(raw))
            return sha
        blob = store("blob", b"print('hello')\n")
        tree = store("tree", b"100644 sample.py\0" + bytes.fromhex(blob))
        commit = store("commit", f"tree {tree}\nauthor a <a> 0 +0000\ncommitter a <a> 0 +0000\n\ninitial\n".encode())
        (git / "refs" / "heads").mkdir(parents=True)
        (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (git / "refs" / "heads" / "main").write_text(commit, encoding="utf-8")
        modules = self.project / "Node_Modules" / "pkg"
        modules.mkdir(parents=True)
        (modules / "index.js").write_text("x", encoding="utf-8")
        (self.project / "new.py").write_text("y = 2\n", encoding="utf-8")
        state = build_git_state(self.project, exclude_dirs={"node_modules"}, exclude_files=set())
        self.assertEqual((state.is_dirty, state.untracked_files, state.modified_files), (True, ("new.py",), ()))
        (self.project / "sample.py").write_text("changed\n", encoding="utf-8")
        self.assertEqual(build_git_state(self.project, exclude_dirs={"node_modules"}).modified_files, ("sample.py",))

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

    def test_identity_is_a_leaf_module(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r});"
            "import application.identity;"
            "loaded = [m for m in sys.modules if m in ('application.storage',) or m.split('.')[0] in ('export', 'gui', 'tkinter')];"
            "assert not loaded, loaded"
        )
        self.assertEqual(subprocess.run([sys.executable, "-c", code], capture_output=True).returncode, 0)

    def test_engine_does_not_load_app_state_gui_or_network(self):
        code = (
            f"import sys; sys.path.insert(0, {str(APP_ROOT)!r});"
            "import export.pipeline;"
            "loaded = [m for m in sys.modules if m == 'application.storage' or m.split('.')[0] in ('gui', 'tkinter') or m == 'urllib.request'];"
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

    def test_fast_line_count_matches_splitlines(self):
        rng = random.Random(7)
        pieces = [b"a", b"\n", b"\r", b"\r\n", b"\x0b", b"\x0c", b"\x1c", b"\x1d", b"\x1e", b"\xc2\x85",
                  b"\xe2\x80\xa8", b"\xe2\x80\xa9", b"\xc2", b"\x85", b"\xff", b"\xf0\x9f\x98\x80"]
        for _ in range(20_000):
            data = b"".join(rng.choice(pieces) for _ in range(rng.randint(0, 10)))
            self.assertEqual(count_lines(data), len(data.decode("utf-8", errors="replace").splitlines()), data)

    def test_redaction_matches_line_by_line_rule(self):
        def reference(text):
            return "\n".join("[[REDACTED POSSIBLE SECRET LINE]]" if _SECRET_PATTERN.search(line) else line for line in text.splitlines())
        samples = ["a = 1\nAPI_KEY = x\nb", "Password : y\r\nok", "password\n= split across lines", "no secrets\n",
                   "pa\u017f\u017fword = long s", "API_\u212aEY = kelvin", "caf\u00e9\ntoken= t", ""]
        for index, text in enumerate(samples):
            path = self.root / f"s{index}.txt"
            path.write_text(text, encoding="utf-8", newline="")
            self.assertEqual(safe_read(path), reference(path.read_text(encoding="utf-8")), text)

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
