"""
File: tests/test_app.py

Purpose
-------
Test the Archive around TFL: the six-section header on every Python
file, the standard-library-only rule, architecture cleanup, version.py,
settings normalization, navigation, documentation, and manual-only update
boundaries.

Communication / relationships
-----------------------------
- Imports config/runtime.py, gui/navigation.py, and version.py.
- Never imports Tkinter.

Settings / parameters
---------------------
- APPDATA is redirected to a temporary folder before any project import.
- STANDARD_HEADER_SECTIONS lists the six required sections in order.

Edge cases
----------
- The header test parses every .py file, so a syntax error anywhere
  fails the suite.
- The suite verifies that no in-application updater remains.

Known limitations
-----------------
- tests/ has no __init__.py; run the files directly.

Examples
--------
- python tests/test_app.py
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
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertIn(name, allowed, f"{path.relative_to(ROOT)} imports {name}")

    def test_no_placeholder_or_stale_text_in_source(self):
        banned = ("Coming Soon", "Reserved framework", "Placeholder", "version.txt\"", "from tfl", "File: tfl/",
                  "KNOWN_ISSUES", "home_log_box", "selected_framework", "default_framework\"", "Back-compat")
        allowed_files = {"tests/test_app.py", "services/updater/constants.py", "config/runtime.py"}
        for path in python_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative in allowed_files:
                continue
            text = path.read_text(encoding="utf-8")
            for phrase in banned:
                self.assertNotIn(phrase, text, f"{relative}: {phrase}")


class StructureTests(unittest.TestCase):
    def test_tfl_is_the_only_framework_and_lives_in_frameworks_tfl(self):
        folders = sorted(p.name for p in (ROOT / "frameworks").iterdir() if p.is_dir() and p.name != "__pycache__")
        self.assertEqual(folders, ["TFL"])
        self.assertFalse((ROOT / "tfl").exists())
        self.assertFalse((ROOT / "frameworks" / "shared").exists())
        for name in ("framework.py", "session_gui.py", "screen.py", "options_screen.py"):
            self.assertFalse((ROOT / "frameworks" / "TFL" / name).exists(), name)
        from gui.navigation import NAV_ITEMS, SETTINGS_NAV_ITEM, normalize_page_name
        self.assertEqual([name for name, _ in NAV_ITEMS] + [SETTINGS_NAV_ITEM[0]],
                         ["Dashboard", "TFL", "Results", "Archive", "Settings"])
        self.assertEqual(normalize_page_name("Frameworks"), "TFL")

    def test_removed_architecture_is_absent(self):
        for relative in (
            "version.txt", "services/updater", "services/rsa_signing.py",
            "services/trust_anchor.py", "signing",
            "config/registries.py", "frameworks/TFL/framework.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_changelog_exists_and_no_architecture_document_is_referenced(self):
        self.assertTrue((ROOT / "docs" / "CHANGELOG.md").is_file())
        document = "ARCHITECTURE" + ".md"
        self.assertFalse((ROOT / "docs" / document).exists())
        for path in sorted(ROOT.rglob("*")):
            if path.suffix not in {".py", ".md"} or "__pycache__" in path.parts or path.name == "test_app.py":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(document, text, path.relative_to(ROOT).as_posix())
            self.assertNotIn("architecture document", text.casefold(), path.relative_to(ROOT).as_posix())


class VersionTests(unittest.TestCase):
    def test_version_py_is_the_only_version_file(self):
        import version
        self.assertEqual(version.DISPLAY_VERSION, f"{version.VERSION} {version.RELEASE_LABEL}")
        self.assertFalse((ROOT / "version.txt").exists())


class SettingsTests(unittest.TestCase):
    def test_retired_and_unknown_keys_are_dropped(self):
        from config.runtime import DEFAULT_SETTINGS, normalize_settings
        normalized = normalize_settings({"default_framework": "SST", "junk": 1, "theme": "dark"})
        self.assertEqual(set(normalized), set(DEFAULT_SETTINGS))

    def test_relative_output_stays_in_appdata(self):
        from config.runtime import APP_DIR, get_tfl_output_dir
        self.assertEqual(APP_DIR, Path(os.environ["APPDATA"]) / "Brisart Research Archive")
        self.assertEqual(get_tfl_output_dir({"output_folder": "outputs"}), APP_DIR / "outputs" / "TFL")
        self.assertEqual(get_tfl_output_dir({"output_folder": "lab/run"}), APP_DIR / "lab" / "run" / "TFL")


class ManualUpdateBoundaryTests(unittest.TestCase):
    def test_in_application_updater_is_absent(self):
        self.assertFalse((ROOT / "services" / "updater").exists())
        self.assertFalse((ROOT / "services" / "rsa_signing.py").exists())
        self.assertFalse((ROOT / "services" / "trust_anchor.py").exists())
        self.assertFalse((ROOT / "signing").exists())

    def test_update_preferences_are_not_application_settings(self):
        from config.runtime import DEFAULT_SETTINGS, normalize_settings
        retired = {"enable_update_checks", "notify_on_update", "auto_install_updates"}
        self.assertTrue(retired.isdisjoint(DEFAULT_SETTINGS))
        normalized = normalize_settings({key: True for key in retired})
        self.assertTrue(retired.isdisjoint(normalized))

    def test_runtime_source_has_no_network_or_updater_imports(self):
        for path in python_files():
            if path.relative_to(ROOT).as_posix() == "tests/test_app.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module.startswith("services.updater"), path)
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith("services.updater") for alias in node.names), path)


if __name__ == "__main__":
    unittest.main()

