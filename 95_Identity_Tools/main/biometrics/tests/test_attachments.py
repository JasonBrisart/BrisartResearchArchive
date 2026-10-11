"""
File: biometrics/tests/test_attachments.py

Purpose
-------
Tests for the generic file-attachment feature on biometrics identity records
(biometrics/engine/attachments.py): sealing/opening arbitrary raw files,
independent of the voice/fingerprint/video modality system, independent of file
extension, and independent of any assumption about what the file's content
looks like.

Verifies: biometrics/identity/identity_record.py,
biometrics/engine/attachments.py.
Contains 9 test case(s) across 1 TestCase class(es).

Design notes:

Unlike the vault file-record tests, these do not need a real Keyring unlock (no
~85-90 second BSR2 KDF cost per test): attach/extract only need a 32-byte
master key, which attachments.py treats identically regardless of how it was
obtained, so a plain secrets.token_bytes(32) exercises the exact same
sealing/opening code path a real device-key-derived master key would.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- biometrics.engine.attachments (biometrics/engine/attachments.py)
Standard library: json, pathlib, secrets, tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) in setUp and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
- Arbitrary blob with no extension round trips exactly.
- Pdf shaped content round trips exactly.
- Public summary exposes metadata but never content.
- Wrong master key fails to extract.
- Attachment cannot be moved to a different identity.
- Attach file reads a real file with no extension.
- Remove identity attachment removes it.
- Extracting nonexistent attachment raises.
- Reattaching under same name replaces it.

Known limitations
-----------------
- Passing proves only the 9 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_attachments -v
    python tests/run_tests.py
"""

import secrets
import tempfile
import unittest
from pathlib import Path

from biometrics.identity.identity_record import new_record, public_summary, validate_record
from biometrics.engine.attachments import (
    AttachmentError,
    attach_bytes,
    attach_file,
    extract_attachment_bytes,
    extract_attachment_to_file,
    remove_identity_attachment,
)


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.master_key = secrets.token_bytes(32)
        self.record = new_record("alice", "Alice Example", "device-binding-placeholder")

    def test_arbitrary_blob_with_no_extension_round_trips_exactly(self):
        blob = secrets.token_bytes(5000) + b"\x00\xff" * 100
        record = attach_bytes(self.record, "random_blob", blob, self.master_key)
        validate_record(record)
        recovered = extract_attachment_bytes(record, "random_blob", self.master_key)
        self.assertEqual(recovered, blob)

    def test_pdf_shaped_content_round_trips_exactly(self):
        fake_pdf = b"%PDF-1.4\n" + secrets.token_bytes(3000)
        record = attach_bytes(self.record, "document.pdf", fake_pdf, self.master_key)
        recovered = extract_attachment_bytes(record, "document.pdf", self.master_key)
        self.assertEqual(recovered, fake_pdf)

    def test_public_summary_exposes_metadata_but_never_content(self):
        blob = secrets.token_bytes(1000)
        record = attach_bytes(self.record, "secret.bin", blob, self.master_key)
        summary = public_summary(record)
        filenames = [a["filename"] for a in summary["attachments"]]
        self.assertIn("secret.bin", filenames)
        import json
        summary_text = json.dumps(summary)
        self.assertNotIn(blob.hex()[:20], summary_text)

    def test_wrong_master_key_fails_to_extract(self):
        record = attach_bytes(self.record, "x", b"secret content", self.master_key)
        wrong_key = secrets.token_bytes(32)
        with self.assertRaises(AttachmentError):
            extract_attachment_bytes(record, "x", wrong_key)

    def test_attachment_cannot_be_moved_to_a_different_identity(self):
        record = attach_bytes(self.record, "x", b"secret content", self.master_key)
        other_record = new_record("bob", "Bob Example", "other-device-binding")
        tampered = dict(other_record)
        tampered["attachments"] = dict(record["attachments"])
        with self.assertRaises(AttachmentError):
            extract_attachment_bytes(tampered, "x", self.master_key)

    def test_attach_file_reads_a_real_file_with_no_extension(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "source_no_ext"
            content = secrets.token_bytes(8000)
            source.write_bytes(content)
            record = attach_file(self.record, "attached_no_ext", source, self.master_key)
            output = Path(tmp_dir) / "extracted_output_no_ext"
            extract_attachment_to_file(record, "attached_no_ext", self.master_key, output)
            self.assertEqual(output.read_bytes(), content)

    def test_remove_identity_attachment_removes_it(self):
        record = attach_bytes(self.record, "temp", b"data", self.master_key)
        record = remove_identity_attachment(record, "temp")
        self.assertFalse(any(a["filename"] == "temp" for a in public_summary(record)["attachments"]))
        with self.assertRaises(AttachmentError):
            extract_attachment_bytes(record, "temp", self.master_key)

    def test_extracting_nonexistent_attachment_raises(self):
        with self.assertRaises(AttachmentError):
            extract_attachment_bytes(self.record, "does-not-exist", self.master_key)

    def test_reattaching_under_same_name_replaces_it(self):
        record = attach_bytes(self.record, "x", b"first version", self.master_key)
        record = attach_bytes(record, "x", b"second version", self.master_key)
        recovered = extract_attachment_bytes(record, "x", self.master_key)
        self.assertEqual(recovered, b"second version")


if __name__ == "__main__":
    unittest.main()




