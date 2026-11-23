"""
File: tests/test_app.py

Purpose
-------
Test the Archive around TFL: the six-section header on every Python file,
the standard-library-only rule, the offline guarantee (no network-capable
imports), navigation, settings persistence, and the version/changelog
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
- STANDARD_HEADER_SECTIONS lists the six required sections in order.
- NETWORK_MODULES: standard-library modules that can reach a network.
- Eight tests: SourceStandardTests (3), NavigationTests (1), VersionTests
  (1), SettingsTests (3).

Edge cases
----------
- The header and import tests parse every .py file, so a syntax error
  anywhere fails the suite.
- The header test checks structure only (title line, six sections in
  order, a blank line before each, an underline, and some text); it cannot
  tell whether the words are accurate.
- Settings files from earlier releases (updater preferences, theme, window
  size, default_framework) are accepted and their keys dropped.

Known limitations
-----------------
- The offline check is static: it finds imports, not dynamic loading.

Examples
--------
- python run.py --test
- python -m unittest discover -s tests -p "test_app.py"
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="brisart_app_test_")

STANDARD_HEADER_SECTIONS = (
    "Purpose", "Communication / relationships", "Settings / parameters",
    "Edge cases", "Known limitations", "Examples",
)


def python_files():
    return sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)


NETWORK_MODULES = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "poplib", "imaplib",
                   "telnetlib", "xmlrpc", "webbrowser", "socketserver"}


def imported_roots(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


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


if __name__ == "__main__":
    unittest.main()

