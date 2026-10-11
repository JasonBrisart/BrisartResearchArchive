"""
File: packages/tests/test_identity.py

Purpose
-------
Tests for packages.identity: recipient descriptor shape and validation.

Verifies: packages/identity.py.
Contains 9 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- packages.identity (packages/identity.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
- New recipient holds no key material.
- Empty identity id is rejected.
- Whitespace padded identity id is rejected.
- Separator in identity id is rejected.
- Nul in identity id is rejected.
- Overlong identity id is rejected.
- Empty label is rejected.
- Validate recipient rejects non dict.
- Validate recipient accepts a good descriptor.

Known limitations
-----------------
- Passing proves only the 9 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest packages.tests.test_identity -v
    python tests/run_tests.py
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




