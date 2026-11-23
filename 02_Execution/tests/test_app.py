"""
File: tests/test_app.py

Purpose
-------
Test the Archive around TFL: the six-section header on every Python file
and that the file paths its headers cite exist, the standard-library-only
rule, the offline guarantee (no network-capable imports), the dependency
boundary between the TFL core and the host application, that the colour
palette has one owner, navigation, the settings file and Activity Log
(round trip, corruption, interrupted saves), and the version/changelog
pairing.

Communication / relationships
-----------------------------
- Imports config/runtime.py, gui/navigation.py, and version.py.
- Reads docs/CHANGELOG.md.
- Never imports Tkinter.
- Run with the rest of the suite by python run.py --test.

Settings / parameters
---------------------
- APPDATA is redirected to a temporary folder before any project import.
- NETWORK_MODULES: standard-library modules that can reach a network.
- HOST_PACKAGES: the application packages the TFL core must not import.
- STANDARD_HEADER_SECTIONS lists the six required sections in order.
- Twenty tests: SourceStandardTests (4), ArchitectureTests (4),
  NavigationTests (1), VersionTests (1), SettingsTests (3),
  SettingsFileTests (4), ActivityLogTests (3).

Edge cases
----------
- The header and import tests parse every .py file, so a syntax error
  anywhere fails the suite.
- The header test checks structure only (title line, six sections in
  order, a blank line before each, an underline, and some text); it cannot
  tell whether the words are accurate. The reference test catches one kind
  of inaccuracy: a header that cites a file path that does not exist.
- File-path citations are recognised only when they start with config/,
  controllers/, frameworks/, gui/, tests/, or docs/ and end in .py or .md.
- The settings and Activity Log tests redirect the module-level file paths
  to a temporary folder, so they never touch the real AppData files.
- Settings files from earlier releases (updater preferences, theme, window
  size, default_framework) are accepted and their keys dropped.

Known limitations
-----------------
- The offline and boundary checks are static: they find imports, not
  dynamic loading.
- Header references are checked for existence only, not for whether the
  cited file still does what the header says.

Examples
--------
- python run.py --test
- python -m unittest discover -s tests -p "test_app.py"
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="brisart_app_test_")

STANDARD_HEADER_SECTIONS = (
    "Purpose", "Communication / relationships", "Settings / parameters",
    "Edge cases", "Known limitations", "Examples",
)


def python_files():
    return sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)


HOST_PACKAGES = {"config", "controllers", "gui", "tkinter"}
HEADER_PATH = re.compile(r"(?<![\w/.])((?:config|controllers|frameworks|gui|tests|docs)/(?:\w+/)*\w+\.(?:py|md))")
NETWORK_MODULES = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "poplib", "imaplib",
                   "telnetlib", "xmlrpc", "webbrowser", "socketserver"}


def imported_modules(path: Path) -> set[str]:
    """Every absolute module name the file imports, dotted (relative imports are inside the package)."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def imported_roots(path: Path) -> set[str]:
    return {name.split(".")[0] for name in imported_modules(path)}


class SourceStandardTests(unittest.TestCase):
    def test_every_python_file_has_the_six_section_header(self):
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(file=relative):
                docstring = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")), clean=False) or ""
                lines = [line.strip() for line in docstring.strip().splitlines()]
                self.assertEqual(lines[0], f"File: {relative}")
                positions = []
                for section in STANDARD_HEADER_SECTIONS:
                    self.assertIn(section, lines)
                    index = lines.index(section)
                    positions.append(index)
                    self.assertEqual(lines[index - 1], "")
                    self.assertEqual(lines[index + 1], "-" * len(section))
                    self.assertTrue(lines[index + 2], f"{section} is empty")
                self.assertEqual(positions, sorted(positions))

    def test_every_import_is_standard_library_or_internal(self):
        internal = {p.name for p in ROOT.iterdir() if p.is_dir()} | {p.stem for p in ROOT.glob("*.py")}
        allowed = sys.stdlib_module_names | internal
        for path in python_files():
            for name in imported_roots(path):
                self.assertIn(name, allowed, f"{path.relative_to(ROOT)} imports {name}")

    def test_application_never_imports_network_modules(self):
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative.startswith("tests/"):
                continue
            with self.subTest(file=relative):
                self.assertEqual(imported_roots(path) & NETWORK_MODULES, set())


    def test_headers_cite_only_files_that_exist(self):
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            docstring = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")), clean=False) or ""
            for cited in sorted(set(HEADER_PATH.findall(docstring))):
                with self.subTest(file=relative, cites=cited):
                    self.assertTrue((ROOT / cited).is_file(), f"{relative} cites {cited}, which does not exist")


class ArchitectureTests(unittest.TestCase):
    TFL = ROOT / "frameworks" / "TFL"

    def test_tfl_core_does_not_depend_on_the_host_application(self):
        core = [p for p in sorted(self.TFL.glob("*.py")) if not p.name.startswith("gui_")]
        self.assertGreaterEqual(len(core), 10)
        for path in core:
            with self.subTest(file=path.name):
                self.assertEqual(imported_roots(path) & HOST_PACKAGES, set())

    def test_tfl_gui_screens_reach_the_host_only_through_the_app_object(self):
        screens = sorted(self.TFL.glob("gui_*.py"))
        self.assertEqual([p.name for p in screens], ["gui_options.py", "gui_screens.py", "gui_session.py"])
        for path in screens:
            with self.subTest(file=path.name):
                self.assertEqual(imported_roots(path) & {"config", "controllers"}, set())

    def test_colours_are_defined_only_in_the_theme_palette(self):
        colour = re.compile(r"^#[0-9a-fA-F]{6}$")
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            allowed = set()
            if relative == "gui/theme.py":
                palette = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                               and any(isinstance(t, ast.Name) and t.id == "COLORS" for t in n.targets))
                allowed = {id(n) for n in ast.walk(palette.value) if isinstance(n, ast.Constant)}
            with self.subTest(file=relative):
                stray = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                         and isinstance(n.value, str) and colour.match(n.value) and id(n) not in allowed]
                self.assertEqual(stray, [])

    def test_lower_layers_never_import_the_pages_or_the_window_above_them(self):
        lower = sorted((ROOT / "config").glob("*.py")) + sorted((ROOT / "controllers").glob("*.py"))
        lower += sorted((ROOT / "gui" / "components").glob("*.py")) + [ROOT / "gui" / "theme.py"]
        for path in lower:
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                above = {m for m in imported_modules(path)
                         if m.startswith("gui.pages") or m in {"gui.main_window", "gui.navigation"}}
                if path.name == "sidebar.py":
                    above.discard("gui.navigation")     # the sidebar reads the page list; nothing else may
                self.assertEqual(above, set())


class NavigationTests(unittest.TestCase):
    def test_sidebar_pages_and_aliases(self):
        from gui.navigation import NAV_ITEMS, SETTINGS_NAV_ITEM, normalize_page_name
        self.assertEqual([name for name, _ in NAV_ITEMS] + [SETTINGS_NAV_ITEM[0]],
                         ["Dashboard", "TFL", "Results", "Archive", "Settings"])
        self.assertEqual(normalize_page_name("Frameworks"), "TFL")


class VersionTests(unittest.TestCase):
    def test_newest_changelog_entry_matches_version(self):
        import version
        self.assertEqual(version.DISPLAY_VERSION, f"{version.VERSION} {version.RELEASE_LABEL}")
        changelog = (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8")
        newest = next(line for line in changelog.splitlines() if line.startswith("## ["))
        self.assertTrue(newest.startswith(f"## [{version.DISPLAY_VERSION}]"), newest)


class SettingsTests(unittest.TestCase):
    def test_only_the_output_folder_is_persisted_and_old_keys_are_dropped(self):
        from config.runtime import DEFAULT_SETTINGS, normalize_settings
        self.assertEqual(set(DEFAULT_SETTINGS), {"settings_version", "output_folder"})
        old = {"default_framework": "SST", "enable_update_checks": True, "notify_on_update": True,
               "auto_install_updates": True, "theme": "dark", "window_width": 1200, "window_height": 900,
               "output_folder": "lab"}
        self.assertEqual(normalize_settings(old), {"settings_version": 1, "output_folder": "lab"})

    def test_unsafe_output_folder_falls_back(self):
        from config.runtime import normalize_settings
        for bad in ("CON", "bad|name", "trailing.", "a\x00b"):
            with self.subTest(value=bad):
                self.assertEqual(normalize_settings({"output_folder": bad})["output_folder"], "outputs")

    def test_relative_output_stays_in_appdata(self):
        from config.runtime import APP_DIR, get_tfl_output_dir
        self.assertEqual(APP_DIR, Path(os.environ["APPDATA"]) / "Brisart Research Archive")
        self.assertEqual(get_tfl_output_dir({"output_folder": "outputs"}), APP_DIR / "outputs" / "TFL")
        self.assertEqual(get_tfl_output_dir({"output_folder": "lab/run"}), APP_DIR / "lab" / "run" / "TFL")


class SettingsFileTests(unittest.TestCase):
    """The one persisted setting survives corruption and interrupted saves."""

    def setUp(self):
        from config import runtime
        self.runtime = runtime
        self._directory = tempfile.TemporaryDirectory()
        self.folder = Path(self._directory.name)
        self._patches = [
            mock.patch.object(runtime, "APP_DIR", self.folder),
            mock.patch.object(runtime, "SETTINGS_FILE", self.folder / "user_settings.json"),
            mock.patch.object(runtime, "SETTINGS_TEMP_FILE", self.folder / "user_settings.json.tmp"),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self._directory.cleanup()

    def test_save_then_load_round_trips_and_leaves_only_the_settings_file(self):
        self.assertTrue(self.runtime.save_settings({"output_folder": "lab"}))
        self.assertEqual(self.runtime.load_settings()["output_folder"], "lab")
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["user_settings.json"])

    def test_unreadable_file_is_moved_aside_and_defaults_are_used(self):
        (self.folder / "user_settings.json").write_text("{not json", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            settings = self.runtime.load_settings()
        self.assertEqual(settings["output_folder"], "outputs")
        self.assertFalse((self.folder / "user_settings.json").exists())
        self.assertEqual((self.folder / "user_settings.invalid.json").read_text(encoding="utf-8"), "{not json")
        self.assertIn("user_settings.invalid.json", printed.getvalue())

    def test_interrupted_save_is_finished_when_the_main_file_is_missing(self):
        (self.folder / "user_settings.json.tmp").write_text(
            json.dumps({"settings_version": 1, "output_folder": "from_temp"}), encoding="utf-8")
        self.assertEqual(self.runtime.load_settings()["output_folder"], "from_temp")
        self.assertTrue((self.folder / "user_settings.json").is_file())
        self.assertFalse((self.folder / "user_settings.json.tmp").exists())

    def test_failed_save_keeps_the_previous_file_and_reports_false(self):
        self.assertTrue(self.runtime.save_settings({"output_folder": "first"}))
        with mock.patch.object(self.runtime, "write_json_file", side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(self.runtime.save_settings({"output_folder": "second"}))
        self.assertEqual(self.runtime.load_settings()["output_folder"], "first")
        self.assertFalse((self.folder / "user_settings.json.tmp").exists())


class ActivityLogTests(unittest.TestCase):
    def setUp(self):
        from config import activity_log
        self.log = activity_log
        self._directory = tempfile.TemporaryDirectory()
        self.file = Path(self._directory.name) / "activity_log.json"
        self._patches = [
            mock.patch.object(activity_log, "ACTIVITY_LOG_FILE", self.file),
            mock.patch.object(activity_log, "ACTIVITY_LOG_TEMP_FILE", self.file.with_name("activity_log.json.tmp")),
        ]
        for patch in self._patches:
            patch.start()

    def tearDown(self):
        for patch in self._patches:
            patch.stop()
        self._directory.cleanup()

    def test_entries_are_kept_oldest_first_capped_at_the_limit_and_blanks_ignored(self):
        self.log.append_activity_log_entry("   ")
        self.assertEqual(self.log.load_activity_log(), [])
        for number in range(self.log.MAX_PERSISTED_ENTRIES + 5):
            self.log.append_activity_log_entry(f"entry {number}")
        entries = self.log.load_activity_log()
        self.assertEqual(len(entries), self.log.MAX_PERSISTED_ENTRIES)
        self.assertEqual((entries[0], entries[-1]), ("entry 5", f"entry {self.log.MAX_PERSISTED_ENTRIES + 4}"))
        self.assertEqual(json.loads(self.file.read_text(encoding="utf-8")), entries)
        self.assertEqual(sorted(p.name for p in self.file.parent.iterdir()), ["activity_log.json"])

    def test_a_corrupt_log_loads_empty_and_the_next_entry_recovers_it(self):
        self.file.write_text("not json at all", encoding="utf-8")
        self.assertEqual(self.log.load_activity_log(), [])
        self.log.append_activity_log_entry("after the damage")
        self.assertEqual(self.log.load_activity_log(), ["after the damage"])

    def test_json_that_is_not_a_list_is_ignored(self):
        self.file.write_text('{"not": "a list"}', encoding="utf-8")
        self.assertEqual(self.log.load_activity_log(), [])


if __name__ == "__main__":
    unittest.main()

