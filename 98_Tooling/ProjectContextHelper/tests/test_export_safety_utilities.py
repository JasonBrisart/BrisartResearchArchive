"""
File: tests/test_export_safety_utilities.py

Purpose
-------
Run focused regression tests for extension normalization, text redaction, root validation, CPU
  core detection, and capture-worker resolution.

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
- test_valid_root_is_resolved: Assert that a valid temporary directory is returned as its
  resolved path.
- test_missing_root_is_rejected: Assert FileNotFoundError for a nonexistent root.
- test_file_instead_of_root_is_rejected: Create a regular file and assert NotADirectoryError
  when used as a root.
- test_cpu_core_detection_never_reports_zero: Assert at least one core is reported, including
  when the platform reports no count.
- test_worker_resolution: Assert auto uses the detected cores, explicit counts are kept or
  clamped to the detected cores, and nothing exceeds 32.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.utils: detect_cpu_cores, normalize_extension, resolve_workers, safe_read, validate_root,
  worker_limit.

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
- test_valid_root_is_resolved(self)
- test_missing_root_is_rejected(self)
- test_file_instead_of_root_is_rejected(self)
- test_cpu_core_detection_never_reports_zero(self)
- test_worker_resolution(self)

Edge cases
----------
Tests unredacted reads, missing roots, file-instead-of-directory roots, and a platform that
  reports no CPU count alongside normal cases. TemporaryDirectory cleanup is registered for each test.

The unredacted fixture explicitly checks trailing-newline preservation. Worker resolution is
  tested with explicit core counts so results do not depend on the test machine. (v4.1.0
  removed the two sha256_file tests with the helper; hash correctness is covered end to end by
  test_v4_engine.test_zip_hashes_match_manifest.)

Known limitations
-----------------
Does not cover the complete export pipeline, GUI, updater, persistence, Git parsing, or all
  security edge cases. Real affinity-restricted core detection is not simulated.

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

import tempfile
import unittest
from pathlib import Path
from unittest import mock
from core.utils import detect_cpu_cores, normalize_extension, resolve_workers, safe_read, validate_root, worker_limit

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
        with mock.patch("core.utils.os.process_cpu_count", create=True, return_value=None):
            self.assertEqual(detect_cpu_cores(), 1)

    def test_worker_resolution(self):
        self.assertEqual(resolve_workers("auto", cores=8), 8)
        self.assertEqual(resolve_workers(3, cores=8), 3)
        self.assertEqual(resolve_workers(16, cores=4), 4)
        self.assertEqual(resolve_workers("auto", cores=64), 32)
        self.assertEqual(worker_limit(1), 1)
