"""
File: tests/test_project_scan_boundaries.py

Purpose
-------
Check project scanning, excluded paths, and root validation.

Communication / relationships
-----------------------------
Imports existing project modules; runs under the project-scoped CI workflow.

Settings / parameters
---------------------
Uses unittest and temporary fixtures; no application settings are changed.

Edge cases
----------
Covers normal behavior and selected invalid or missing inputs.

Known limitations
-----------------
Targeted regression coverage only; not a complete application or GUI audit.

Examples
--------
Run python -m pytest -v from the containing project directory.
"""

import tempfile
import unittest
from pathlib import Path
from filesystem import validate_root, is_excluded, iter_project_files

class ProjectScanBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_valid_project_root_is_resolved(self):
        self.assertEqual(validate_root(self.root), self.root.resolve())

    def test_missing_root_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            validate_root(self.root / 'missing')

    def test_file_instead_of_root_is_rejected(self):
        path = self.root / 'file.txt'
        path.write_text('fixture', encoding='utf-8')
        with self.assertRaises(NotADirectoryError):
            validate_root(path)

    def test_path_outside_project_is_excluded(self):
        self.assertTrue(is_excluded(self.root.parent / 'outside.txt', self.root))

    def test_git_and_cache_paths_are_excluded(self):
        for folder in ['.git', '__pycache__']:
            with self.subTest(folder=folder):
                self.assertTrue(is_excluded(self.root / folder / 'file.py', self.root))

    def test_scan_includes_source_but_excludes_git_metadata(self):
        source = self.root / 'main.py'
        source.write_text('pass\n', encoding='utf-8')
        git = self.root / '.git'
        git.mkdir()
        (git / 'config').write_text('fixture', encoding='utf-8')
        self.assertEqual(iter_project_files(self.root), [source])

    def test_empty_project_has_no_files(self):
        self.assertEqual(iter_project_files(self.root), [])

