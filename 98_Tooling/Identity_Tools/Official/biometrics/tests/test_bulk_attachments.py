"""
File: biometrics/tests/test_bulk_attachments.py

Purpose
-------
Tests for biometrics.engine.bulk_attachments: chunked, multi-path
file/folder/drive attachments on an identity record.

Verifies: biometrics/identity/identity_record.py,
biometrics/engine/bulk_attachments.py, biometrics/app.py (the --chunk-mb check
of attach-paths).
Contains 14 test case(s) across 2 TestCase class(es).

Design notes:

Like biometrics/tests/test_attachments.py, these use an injected 32-byte master
key (secrets.token_bytes) rather than a real Keyring unlock, so they exercise
the full chunk/bundle/manifest logic and real BSR2 sealing of each chunk
WITHOUT paying the slow KDF cost. A 256-byte chunk size forces the
multi-chunk path while keeping each test to a few seconds, matching
vault/tests/test_bulk_file_service.py.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- biometrics.engine.bulk_attachments (biometrics/engine/bulk_attachments.py)
- biometrics.app (biometrics/app.py)
Standard library: argparse, pathlib, secrets, tempfile, unittest, unittest.mock.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) in setUp and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
- Small content uses a single chunk.
- Multi chunk content round trips exactly.
- Empty content round trips.
- A manifest attachment is created.
- Restore detects a missing chunk.
- Restore missing bundle raises.
- Attach paths bundles mixed files and folders.
- Attach paths requires at least one path.
- Attach paths rejects a nonexistent path.
- Remove bulk attachment clears chunks and manifest.
- A zero or negative chunk size is rejected and nothing is attached.
- A non-integer or bool chunk size is rejected.
- Attach paths checks the chunk size before it reads any path.
- attach-paths rejects a --chunk-mb outside 1..15 before the keyring is loaded.

Known limitations
-----------------
- Tracked in docs/KNOWN_ISSUES.md: KI-003: Bulk processing is constrained by
  throughput, memory, and temporary storage
- Passing proves only the 14 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_bulk_attachments -v
    python tests/run_tests.py
"""

import argparse
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biometrics import app as biometrics_app
from biometrics.identity.identity_record import new_record
from biometrics.engine import bulk_attachments
from biometrics.engine.bulk_attachments import BulkAttachmentError


class BulkAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.master_key = secrets.token_bytes(32)
        self.record = new_record("alice", "Alice Example", "device-binding-placeholder")
        # 256-byte chunks force the multi-chunk path with a few hundred bytes of
        # data. BSR2 seals roughly 1.4 KB/s in pure Python, so the former 32 KiB
        # chunks made single tests take minutes under --fast.
        self.small_chunk = 256

    def test_small_content_uses_a_single_chunk(self):
        data = b"a short attachment"
        record = bulk_attachments.attach_large_bytes(
            self.record, "note", data, self.master_key, chunk_bytes=self.small_chunk)
        self.assertEqual(
            bulk_attachments.restore_large_bytes(record, "note", self.master_key), data)

    def test_multi_chunk_content_round_trips_exactly(self):
        data = secrets.token_bytes(self.small_chunk * 3 + 123)
        record = bulk_attachments.attach_large_bytes(
            self.record, "big", data, self.master_key, chunk_bytes=self.small_chunk)
        self.assertEqual(
            bulk_attachments.restore_large_bytes(record, "big", self.master_key), data)

    def test_empty_content_round_trips(self):
        record = bulk_attachments.attach_large_bytes(
            self.record, "empty", b"", self.master_key, chunk_bytes=self.small_chunk)
        self.assertEqual(
            bulk_attachments.restore_large_bytes(record, "empty", self.master_key), b"")

    def test_a_manifest_attachment_is_created(self):
        record = bulk_attachments.attach_large_bytes(
            self.record, "bundle", b"data", self.master_key, chunk_bytes=self.small_chunk)
        self.assertIn("bundle.manifest", record.get("attachments", {}))

    def test_restore_detects_a_missing_chunk(self):
        data = secrets.token_bytes(self.small_chunk * 2 + 50)
        record = bulk_attachments.attach_large_bytes(
            self.record, "corrupt", data, self.master_key, chunk_bytes=self.small_chunk)
        # Drop one chunk attachment and confirm reassembly refuses.
        del record["attachments"]["corrupt.chunk0"]
        with self.assertRaises(BulkAttachmentError):
            bulk_attachments.restore_large_bytes(record, "corrupt", self.master_key)

    def test_restore_missing_bundle_raises(self):
        with self.assertRaises(BulkAttachmentError):
            bulk_attachments.restore_large_bytes(self.record, "nope", self.master_key)

    def test_attach_paths_bundles_mixed_files_and_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            standalone = tmp_path / "report.pdf"
            standalone.write_bytes(b"%PDF fake")
            folder = tmp_path / "Photos"
            (folder / "sub").mkdir(parents=True)
            (folder / "a.txt").write_bytes(b"file a")
            (folder / "sub" / "b_no_ext").write_bytes(b"no extension file")

            record, report = bulk_attachments.attach_paths(
                self.record, "my-bundle", [standalone, folder], self.master_key,
                chunk_bytes=self.small_chunk)
            self.assertEqual(report["files_bundled"], 3)

            restore_dir = tmp_path / "restored"
            result = bulk_attachments.restore_paths(
                record, "my-bundle", self.master_key, restore_dir)
            self.assertEqual(result["files_restored"], 3)
            self.assertEqual((restore_dir / "report.pdf").read_bytes(), b"%PDF fake")
            self.assertEqual(
                (restore_dir / "Photos" / "sub" / "b_no_ext").read_bytes(),
                b"no extension file")

    def test_attach_paths_requires_at_least_one_path(self):
        with self.assertRaises(BulkAttachmentError):
            bulk_attachments.attach_paths(self.record, "empty", [], self.master_key)

    def test_attach_paths_rejects_a_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(BulkAttachmentError):
                bulk_attachments.attach_paths(
                    self.record, "bad", [Path(tmp) / "does_not_exist"], self.master_key)

    def test_remove_bulk_attachment_clears_chunks_and_manifest(self):
        data = secrets.token_bytes(self.small_chunk * 2 + 10)
        record = bulk_attachments.attach_large_bytes(
            self.record, "temp", data, self.master_key, chunk_bytes=self.small_chunk)
        record = bulk_attachments.remove_bulk_attachment(record, "temp", self.master_key)
        remaining = [name for name in record.get("attachments", {}) if name.startswith("temp")]
        self.assertEqual(remaining, [])
        with self.assertRaises(BulkAttachmentError):
            bulk_attachments.restore_large_bytes(record, "temp", self.master_key)

    # --- BUG FIX regression tests (2026-11-23, LTS-2028-COR-10, KI-006) -----
    # chunk_bytes was never validated. Zero crashed with a bare ValueError from
    # range(); a negative value made the chunk iterator yield nothing, so
    # attach_large_bytes() reported success after attaching a manifest with no
    # data chunks, and restore_large_bytes() could never recover the content.

    def test_a_zero_or_negative_chunk_size_is_rejected_and_nothing_is_attached(self):
        for bad in (0, -1, -256):
            with self.subTest(chunk_bytes=bad):
                with self.assertRaises(BulkAttachmentError):
                    bulk_attachments.attach_large_bytes(
                        self.record, "bad", b"some data", self.master_key, chunk_bytes=bad)
        self.assertEqual(self.record.get("attachments", {}), {})

    def test_a_non_integer_chunk_size_is_rejected(self):
        # True is an int to Python but would silently mean one-byte chunks.
        for bad in (1.5, "8", None, True):
            with self.subTest(chunk_bytes=bad):
                with self.assertRaises(BulkAttachmentError):
                    bulk_attachments.attach_large_bytes(
                        self.record, "bad", b"some data", self.master_key, chunk_bytes=bad)

    def test_attach_paths_checks_the_chunk_size_before_it_reads_any_path(self):
        # The path does not exist, so reaching the zip step would raise the
        # "no readable files" error instead; the chunk-size message must win.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(BulkAttachmentError, "chunk_bytes"):
                bulk_attachments.attach_paths(
                    self.record, "bad", [Path(tmp) / "does_not_exist"], self.master_key,
                    chunk_bytes=-1)


class AttachPathsChunkSizeCommandTests(unittest.TestCase):
    def test_an_out_of_range_chunk_mb_is_rejected_before_the_keyring_is_loaded(self):
        for bad in (0, -1, biometrics_app.MAX_CHUNK_MB + 1):
            with self.subTest(chunk_mb=bad):
                args = argparse.Namespace(
                    identity_id="alice", name="bundle", paths=["unused"], chunk_mb=bad)
                with mock.patch.object(
                        biometrics_app, "_load_or_create_keyring",
                        side_effect=AssertionError("keyring must not be touched")):
                    with self.assertRaisesRegex(biometrics_app.AppError, "--chunk-mb"):
                        biometrics_app.command_attach_paths(args)


if __name__ == "__main__":
    unittest.main()
