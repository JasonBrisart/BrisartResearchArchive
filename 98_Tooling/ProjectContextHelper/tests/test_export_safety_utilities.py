"""
File: tests/test_export_safety_utilities.py

Purpose
-------
Check export redaction, hashing, and root validation.

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

import hashlib
import tempfile
import unittest
from pathlib import Path
from core.utils import normalize_extension, safe_read, sha256_file, validate_root

class ExportSafetyUtilityTests(unittest.TestCase):
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

    def test_file_hash_matches_independent_sha256(self):
        path = self.root / 'data.bin'
        value = bytes(range(256))
        path.write_bytes(value)
        self.assertEqual(sha256_file(path), hashlib.sha256(value).hexdigest())

    def test_missing_file_hash_returns_none(self):
        self.assertIsNone(sha256_file(self.root / 'missing'))

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

