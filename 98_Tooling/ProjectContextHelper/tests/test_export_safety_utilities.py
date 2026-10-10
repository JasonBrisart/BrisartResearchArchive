"""
File: tests/test_export_safety_utilities.py

Purpose
-------
Run focused regression tests for extension normalization, text redaction, file hashing, and root
  validation.

Implemented responsibilities:
- setUp: Create a fresh TemporaryDirectory fixture, register cleanup, and store its Path for
  each unittest case.
- test_extension_normalization_handles_whitespace_and_case: Assert whitespace/case normalization
  for PY and .JSON and preservation of an empty normalized extension.
- test_redaction_removes_secret_lines_but_preserves_other_lines: Write a fixture with api_key
  plus benign lines; assert secret removal, placeholder insertion, and preservation of the
  benign values.
- test_explicit_unredacted_read_preserves_original: Assert that disabling redaction returns the
  exact fixture text including its trailing newline.
- test_file_hash_matches_independent_sha256: Hash a fixture containing all 256 byte values and
  compare the result with an independent hashlib.sha256 calculation.
- test_missing_file_hash_returns_none: Assert that hashing a nonexistent path returns None
  rather than raising.
- test_valid_root_is_resolved: Assert that a valid temporary directory is returned as its
  resolved path.
- test_missing_root_is_rejected: Assert FileNotFoundError for a nonexistent root.
- test_file_instead_of_root_is_rejected: Create a regular file and assert NotADirectoryError
  when used as a root.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.utils: normalize_extension, safe_read, sha256_file, validate_root.

Consumers in the supplied source:
No direct application-module importer is present in the supplied source; entry points/tests may
  be invoked through their execution guards or discovery.

Settings / parameters
---------------------
Uses unittest and temporary filesystem fixtures; does not need pytest for direct discovery.

Function signatures (nested callbacks are scoped to their enclosing function):
- setUp(self)
- test_extension_normalization_handles_whitespace_and_case(self)
- test_redaction_removes_secret_lines_but_preserves_other_lines(self)
- test_explicit_unredacted_read_preserves_original(self)
- test_file_hash_matches_independent_sha256(self)
- test_missing_file_hash_returns_none(self)
- test_valid_root_is_resolved(self)
- test_missing_root_is_rejected(self)
- test_file_instead_of_root_is_rejected(self)

Edge cases
----------
Tests unredacted reads, missing-file hashes, missing roots, and file-instead-of-directory roots
  alongside normal cases. TemporaryDirectory cleanup is registered for each test.

The binary hash fixture is not passed through text decoding. The unredacted fixture explicitly
  checks trailing-newline preservation.

Known limitations
-----------------
Does not cover the complete export pipeline, GUI, updater, persistence, Git parsing, or all
  security edge cases.

The tests use fixture-only values and do not test secret discovery across arbitrary formats, ZIP
  redaction, or live application settings.

Examples
--------
Usage from the directory containing run.py:

    python -m unittest discover -s tests -v
    python -m unittest discover -s tests -p test_export_safety_utilities.py -v

    Run from the directory containing run.py so core.utils is importable.
    Each test gets an isolated temporary directory; the fixture files are removed
    through unittest cleanup.
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

