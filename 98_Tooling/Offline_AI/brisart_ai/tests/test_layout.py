"""
File: brisart_ai/tests/test_layout.py

Purpose
-------
Exercise the distributable root, external dependency and user-state boundaries.

Protected scenarios: TestProjectLayout verifies root holds only the three entry files;
TestProjectLayout verifies no saved state inside the project; TestProjectLayout verifies
external native implementations are not packaged; TestProjectLayout verifies no init py
anywhere in the project.

Communication / relationships
-----------------------------
Uses the actual project directory.

Direct project imports: brisart_ai.

The cases use self.assertEqual, self.assertFalse to check returned values, persisted
state or raised errors. The suite is run through scripts/run_tests.py so Native API
discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

Module configuration and named constants: ROOT_FILES (set, 3 entries).

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Bundled APIs, repository-local state and prohibited root files.

Regression coverage includes
TestProjectLayout.test_root_holds_only_the_three_entry_files,
TestProjectLayout.test_no_saved_state_inside_the_project,
TestProjectLayout.test_external_native_implementations_are_not_packaged,
TestProjectLayout.test_no_init_py_anywhere_in_the_project.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_layout.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/tests/test_layout.py -k
test_no_saved_state_inside_the_project.
"""

import unittest

from brisart_ai import native_path

ROOT_FILES = {"run.py", "cli.py", "version.py"}
_SKIPPED_FOLDERS = {".git", ".venv", "venv", "env", "node_modules", "__pycache__"}


class TestProjectLayout(unittest.TestCase):
    def test_root_holds_only_the_three_entry_files(self):
        root = native_path.PROJECT_ROOT
        files = {path.name for path in root.iterdir() if path.is_file()}
        self.assertEqual(files, ROOT_FILES)

    def test_no_saved_state_inside_the_project(self):
        root = native_path.PROJECT_ROOT
        found = sorted(
            str(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file()
            and not _SKIPPED_FOLDERS.intersection(path.parts)
            and (".sqlite3" in path.name or path.name == "research_settings.json")
        )
        self.assertEqual(found, [], msg="saved state lives in the per-user folder now")
        self.assertFalse((root / "data").exists())

    def test_external_native_implementations_are_not_packaged(self):
        root = native_path.PROJECT_ROOT
        self.assertFalse((root / "brisart_ai" / "native").exists())
        for name in native_path.REQUIRED_MODULES:
            self.assertFalse(any(root.rglob(name)), msg=f"Bundled native module: {name}")

    def test_no_init_py_anywhere_in_the_project(self):
        root = native_path.PROJECT_ROOT
        found = sorted(
            str(path.relative_to(root))
            for path in root.rglob("__init__.py")
            if not _SKIPPED_FOLDERS.intersection(path.parts)
        )
        self.assertEqual(found, [], msg="brisart_ai uses namespace packages; see brisart_ai/version_info.py")


if __name__ == "__main__":
    unittest.main()

