"""
File: vault/tests/test_public_summary_file_metadata.py

Purpose
-------
Regression test for a bug found 2026-08-25: VaultService.list_records() (and
therefore the GUI's "Files / Folders / Drives" tab, which calls list_records()
on every refresh) silently dropped a file record's plaintext size/filename/hash
metadata, even though that metadata is stored right on the record in the clear
(see VaultService.upsert_file_bytes).

Verifies: vault/store/vault_file.py, vault/store/vault_service.py.
Contains 4 test case(s) across 1 TestCase class(es).

Design notes:

Root cause: vault.records.record_model.public_summary() only ever returned the
five fixed keys every record kind shares (record_id/label/kind/
created_at/updated_at). upsert_file_bytes() worked around this by manually
merging the file-specific fields back in on its own return value -- but
list_records() (and get_summary()) call public_summary() directly with no such
merge, so a file record's size/filename/hash were only ever visible immediately
after upsert, and vanished on every subsequent listing/refresh.

Fix: public_summary() now includes original_filename/file_size_bytes/
file_sha256 whenever they are present on the record, and omits them otherwise
(so a normal note/credential record's summary shape is unchanged).

Communication / relationships
-----------------------------
Depends on (project modules):
- vault.store.vault_file (vault/store/vault_file.py)
- vault.store.vault_service (vault/store/vault_service.py)
Standard library: pathlib, secrets, tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) in setUp and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
- File size survives a fresh list records call.
- Get summary also surfaces file metadata.
- Ordinary json records do not gain file metadata keys.
- Updating a file record keeps metadata current.

Known limitations
-----------------
- Passing proves only the 4 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest vault.tests.test_public_summary_file_metadata -v
    python tests/run_tests.py
"""

import secrets
import tempfile
import unittest
from pathlib import Path

from vault.store.vault_file import VAULT_FORMAT, save_state
from vault.store.vault_service import VaultService


class PublicSummaryFileMetadataTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self._tmp_dir.name) / "vault.json"
        save_state(self.vault_path, {"format": VAULT_FORMAT, "keyring": {"placeholder": True}, "records": {}})
        self.service = VaultService(self.vault_path)
        self.service._master_key = secrets.token_bytes(32)

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_file_size_survives_a_fresh_list_records_call(self):
        # This is the exact bug: upsert's own return value always had the
        # size, but a SEPARATE, later list_records() call (what the GUI's
        # refresh button actually does) previously lost it.
        content = b"some file content, twenty-seven bytes"
        self.service.upsert_file_bytes("myfile", content, original_filename="myfile.txt")
        listed = self.service.list_records()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["file_size_bytes"], len(content))
        self.assertEqual(listed[0]["original_filename"], "myfile.txt")
        self.assertEqual(len(listed[0]["file_sha256"]), 64)

    def test_get_summary_also_surfaces_file_metadata(self):
        summary = self.service.upsert_file_bytes("another", b"xyz", original_filename="a.bin")
        fetched = self.service.get_summary(summary["record_id"])
        self.assertEqual(fetched["file_size_bytes"], 3)
        self.assertEqual(fetched["original_filename"], "a.bin")

    def test_ordinary_json_records_do_not_gain_file_metadata_keys(self):
        # Guards against the fix leaking these keys onto record kinds that
        # never had them, which would be a regression of its own.
        self.service.upsert("a normal note", "note", {"text": "hi"})
        listed = self.service.list_records()
        self.assertNotIn("file_size_bytes", listed[0])
        self.assertNotIn("original_filename", listed[0])
        self.assertNotIn("file_sha256", listed[0])

    def test_updating_a_file_record_keeps_metadata_current(self):
        first = self.service.upsert_file_bytes("f", b"short", original_filename="f.txt")
        self.service.upsert_file_bytes(
            "f", b"a much longer replacement body", original_filename="f.txt",
            record_id=first["record_id"],
        )
        listed = self.service.list_records()
        self.assertEqual(listed[0]["file_size_bytes"], len(b"a much longer replacement body"))


if __name__ == "__main__":
    unittest.main()



