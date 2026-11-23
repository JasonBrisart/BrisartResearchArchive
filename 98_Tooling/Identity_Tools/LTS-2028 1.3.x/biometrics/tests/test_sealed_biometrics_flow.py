"""
File: biometrics/tests/test_sealed_biometrics_flow.py

Purpose
-------
End-to-end test that templates are actually sealed (not stored in the clear)
and that a wrong master key cannot open them.

Verifies: biometrics/engine/enrollment.py, biometrics/engine/verification.py,
biometrics/identity/identity_store.py, biometrics/samples/sample_generator.py.
Contains 4 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.engine.enrollment (biometrics/engine/enrollment.py)
- biometrics.engine.verification (biometrics/engine/verification.py)
- biometrics.identity.identity_store (biometrics/identity/identity_store.py)
- biometrics.samples.sample_generator (biometrics/samples/sample_generator.py)
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
- Stored template is not plaintext json vector.
- Verification succeeds with correct master key.
- Verification fails authentication with wrong master key.
- Template cannot be opened under different identity context.

Known limitations
-----------------
- Passing proves only the 4 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_sealed_biometrics_flow -v
    python tests/run_tests.py
"""

import json
import secrets
import tempfile
import unittest
from pathlib import Path

from biometrics.engine import enrollment, verification
from biometrics.identity.identity_store import IdentityStore
from biometrics.samples import sample_generator


class SealedTemplateTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp_dir.name)
        self.store = IdentityStore(self.tmp_path / "identities")
        self.master_key = secrets.token_bytes(32)
        self.fingerprint_path = self.tmp_path / "sample_fingerprint.pgm"
        sample_generator.write_fingerprint_sample(self.fingerprint_path, "seed-alpha")

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_stored_template_is_not_plaintext_json_vector(self):
        record = enrollment.enroll_identity(
            "alice",
            "Alice Example",
            self.master_key,
            {"fingerprint": self.fingerprint_path},
        )
        self.store.save(record)
        raw_text = (self.tmp_path / "identities" / "alice.json").read_text()
        self.assertNotIn('"vector"', raw_text)
        parsed = json.loads(raw_text)
        envelope = parsed["record"]["templates"]["fingerprint"]
        # NOTE: fixed 2026-08-24 -- this previously asserted "BSR2", but the
        # real algorithm constant (crypto.vendor.ALGORITHM /
        # vendor.brisart_security_envelope.ALGORITHM) is "BSR2-ARX-SPONGE-ETM".
        # The old assertion always failed even though sealing itself was
        # correct; see docs/BUGFIX_2026-08-24.md for the bug-fix entry.
        self.assertEqual(envelope["algorithm"], "BSR2-ARX-SPONGE-ETM")
        self.assertIn("ciphertext", envelope)

    def test_verification_succeeds_with_correct_master_key(self):
        record = enrollment.enroll_identity(
            "bob", "Bob Example", self.master_key, {"fingerprint": self.fingerprint_path}
        )
        result = verification.verify_identity(
            record, {"fingerprint": self.fingerprint_path}, self.master_key
        )
        self.assertTrue(result["matched"])

    def test_verification_fails_authentication_with_wrong_master_key(self):
        record = enrollment.enroll_identity(
            "carol", "Carol Example", self.master_key, {"fingerprint": self.fingerprint_path}
        )
        wrong_key = secrets.token_bytes(32)
        with self.assertRaises(verification.VerificationError):
            verification.verify_identity(
                record, {"fingerprint": self.fingerprint_path}, wrong_key
            )

    def test_template_cannot_be_opened_under_different_identity_context(self):
        record_a = enrollment.enroll_identity(
            "dave", "Dave Example", self.master_key, {"fingerprint": self.fingerprint_path}
        )
        record_b = enrollment.create_identity("erin", "Erin Example", self.master_key)
        tampered = dict(record_b)
        tampered["templates"] = dict(record_a["templates"])
        with self.assertRaises(verification.VerificationError):
            verification.verify_identity(
                tampered, {"fingerprint": self.fingerprint_path}, self.master_key
            )


if __name__ == "__main__":
    unittest.main()




