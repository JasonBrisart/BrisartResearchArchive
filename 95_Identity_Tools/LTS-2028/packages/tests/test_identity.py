"""
File: packages/tests/test_identity.py

Purpose
-------
Tests for packages.identity: recipient descriptor shape and validation.

Communication / relationships
-----------------------------
Direct module imports: unittest, packages, packages.identity.

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
"""

import unittest
from packages import identity
from packages.identity import RecipientIdentityError


class RecipientIdentityTests(unittest.TestCase):
    def test_new_recipient_holds_no_key_material(self):
        recipient = identity.new_recipient("alice", "Alice")
        self.assertEqual(set(recipient), {"identity_id", "label"})

    def test_empty_identity_id_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_identity_id("")

    def test_whitespace_padded_identity_id_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_identity_id("  alice  ")

    def test_separator_in_identity_id_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_identity_id("al|ice")

    def test_nul_in_identity_id_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_identity_id("alice\x00")

    def test_overlong_identity_id_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_identity_id("a" * 200)

    def test_empty_label_is_rejected(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_label("   ")

    def test_validate_recipient_rejects_non_dict(self):
        with self.assertRaises(RecipientIdentityError):
            identity.validate_recipient(["not", "a", "dict"])

    def test_validate_recipient_accepts_a_good_descriptor(self):
        recipient = identity.new_recipient("bob", "Bob")
        self.assertEqual(identity.validate_recipient(recipient), recipient)


if __name__ == "__main__":
    unittest.main()

