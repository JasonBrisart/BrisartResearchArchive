"""
File: tests/test_snapshot_integrity.py

Purpose
-------
Check snapshot verification against changed, missing, and unchanged files.

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
import json
import tempfile
import unittest
from pathlib import Path
from engine.app_info import MANIFEST_FILENAME
from engine.integrity_check import load_manifest, verify_snapshot_against_source

class SnapshotIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.snapshot = self.root / 'snapshot'
        self.source.mkdir()
        self.snapshot.mkdir()

    def record(self, data=b'original', use_hash=True):
        (self.source / 'file.txt').write_bytes(data)
        record = {'relative_path': 'file.txt', 'size_bytes': len(data)}
        if use_hash:
            record['sha256'] = hashlib.sha256(data).hexdigest()
        (self.snapshot / MANIFEST_FILENAME).write_text(
            json.dumps({'included_files': [record]}), encoding='utf-8')

    def verify(self):
        return verify_snapshot_against_source(self.snapshot, self.source)

    def test_unchanged_file_matches_recorded_hash(self):
        self.record()
        result = self.verify()
        self.assertEqual(result['matched'], ['file.txt'])
        self.assertEqual(result['changed_count'], 0)
        self.assertEqual(result['missing_count'], 0)

    def test_same_size_content_change_is_detected_by_hash(self):
        self.record(b'abc')
        (self.source / 'file.txt').write_bytes(b'xyz')
        self.assertEqual(self.verify()['changed_count'], 1)

    def test_deleted_file_is_reported_missing(self):
        self.record()
        (self.source / 'file.txt').unlink()
        self.assertEqual(self.verify()['missing'], ['file.txt'])

    def test_directory_in_place_of_file_is_reported_missing(self):
        self.record()
        path = self.source / 'file.txt'
        path.unlink()
        path.mkdir()
        self.assertEqual(self.verify()['missing_count'], 1)

    def test_size_change_is_detected_without_hash(self):
        self.record(use_hash=False)
        (self.source / 'file.txt').write_bytes(b'longer replacement')
        self.assertEqual(self.verify()['changed_count'], 1)

    def test_missing_manifest_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            load_manifest(self.snapshot)

    def test_malformed_manifest_is_rejected(self):
        (self.snapshot / MANIFEST_FILENAME).write_text('{invalid', encoding='utf-8')
        with self.assertRaises(json.JSONDecodeError):
            load_manifest(self.snapshot)

