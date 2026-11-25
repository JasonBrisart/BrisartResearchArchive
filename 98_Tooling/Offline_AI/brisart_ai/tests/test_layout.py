r"""
File: brisart_ai/tests/test_layout.py

Purpose
-------
Guard the package, state and external dependency boundaries in the actual
checkout.

Communication / relationships
-----------------------------
Direct module imports: unittest, brisart_ai.native_path (for
PROJECT_ROOT). Reads the real project folder; nothing is written.

Settings / parameters
---------------------
- ROOT_FILES: the only files allowed directly in the project root. Add a
  name here, and to docs/ARCHITECTURE.md, to allow another.
- _SKIPPED_FOLDERS: folders the __init__.py scan ignores (.git, virtual
  environments, node_modules, __pycache__).

Edge cases
----------
- Only files in the root are counted; folders (brisart_ai/, docs/, scripts/,
  __pycache__) are fine.
- A leftover brisart_ai_index.sqlite3 (or its -wal/-shm files) or a data/
  folder in the project is reported, because saved state belongs in the
  per-user folder (brisart_ai/state.py).

Known limitations
-----------------
- It checks the folder it runs from, so an index left beside the program by
  an earlier release makes it fail until run.py or cli.py has moved it, or it
  is deleted.
- README.md, LICENSE and similar files are not allowed in the root; the
  project overview is docs/README.md.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_layout.py
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
