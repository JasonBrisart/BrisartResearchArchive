"""
File: packages/tests/test_verification.py

Purpose
-------
Tests for packages.verification: the fast "does this master key belong to
this recipient" check that runs before any key slot is touched.

Communication / relationships
-----------------------------
Direct module imports: secrets, unittest, packages.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Run this test file with the project-scoped test runner.

Additional module documentation
-------------------------------
Tests for packages.verification: the fast "does this master key belong to
this recipient" check that runs before any key slot is touched.

Fast: build_recipient_verifier / verify_recipient_master_key use the keyed-MAC
factor path (~15 ms), not the slow KDF.
"""

import secrets
import unittest

from packages import verification


class RecipientVerifierTests(unittest.TestCase):
    def setUp(self):
        self.master_key = secrets.token_bytes(32)

    def test_correct_key_and_id_verify(self):
        verifier = verification.build_recipient_verifier(self.master_key, "alice")
        self.assertTrue(
            verification.verify_recipient_master_key(self.master_key, "alice", verifier))

    def test_wrong_master_key_does_not_verify(self):
        verifier = verification.build_recipient_verifier(self.master_key, "alice")
        self.assertFalse(
            verification.verify_recipient_master_key(secrets.token_bytes(32), "alice", verifier))

    def test_verifier_is_bound_to_the_identity_id(self):
        # A verifier built for "alice" must not verify under identity "bob",
        # even with the same master key.
        verifier = verification.build_recipient_verifier(self.master_key, "alice")
        self.assertFalse(
            verification.verify_recipient_master_key(self.master_key, "bob", verifier))

    def test_malformed_verifier_does_not_verify(self):
        self.assertFalse(
            verification.verify_recipient_master_key(self.master_key, "alice", "garbage"))


if __name__ == "__main__":
    unittest.main()

