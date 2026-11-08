"""
File: crypto/tests/test_context.py

Purpose
-------
Tests for crypto.context: canonical context-string construction and the
rejection of characters that could forge a different context.

Verifies: crypto/context.py, crypto/errors.py.
Contains 9 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.errors (crypto/errors.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
ContextConstructionTests:
- Record context is deterministic.
- Different kinds produce different contexts.
- All contexts share the versioned prefix.
- Field order matters so swapped fields differ.
ContextRejectionTests:
- Separator in a field is rejected.
- Nul byte in a field is rejected.
- Empty field is rejected.
- Non string field is rejected.
- A field cannot be shifted across the separator boundary.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.
- Passing proves only the 9 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest crypto.tests.test_context -v
    python tests/run_tests.py
"""

import unittest
from crypto import context
from crypto.errors import Bsr2IntegrationError


class ContextConstructionTests(unittest.TestCase):
    def test_record_context_is_deterministic(self):
        a = context.record_context("rid", "credential", "Email")
        b = context.record_context("rid", "credential", "Email")
        self.assertEqual(a, b)

    def test_different_kinds_produce_different_contexts(self):
        template = context.template_context("alice", "voice")
        attachment = context.attachment_context("alice", "voice")
        self.assertNotEqual(template, attachment)

    def test_all_contexts_share_the_versioned_prefix(self):
        for value in (
            context.record_context("r", "k", "l"),
            context.template_context("i", "m"),
            context.attachment_context("i", "f"),
            context.identity_context("i"),
            context.package_context("p"),
            context.key_slot_context("p", "i"),
            context.keyring_context("passphrase"),
        ):
            self.assertTrue(value.startswith("BrisartIdentityTools/v1|"))

    def test_field_order_matters_so_swapped_fields_differ(self):
        self.assertNotEqual(
            context.key_slot_context("p", "i"),
            context.key_slot_context("i", "p"),
        )


class ContextRejectionTests(unittest.TestCase):
    def test_separator_in_a_field_is_rejected(self):
        with self.assertRaises(Bsr2IntegrationError):
            context.template_context("al|ice", "voice")

    def test_nul_byte_in_a_field_is_rejected(self):
        with self.assertRaises(Bsr2IntegrationError):
            context.template_context("alice\x00", "voice")

    def test_empty_field_is_rejected(self):
        with self.assertRaises(Bsr2IntegrationError):
            context.record_context("", "kind", "label")

    def test_non_string_field_is_rejected(self):
        with self.assertRaises(Bsr2IntegrationError):
            context.record_context(123, "kind", "label")

    def test_a_field_cannot_be_shifted_across_the_separator_boundary(self):
        # "a" + "b|c" must not collide with "a|b" + "c" style inputs; the
        # separator being rejected inside a field is what guarantees this.
        with self.assertRaises(Bsr2IntegrationError):
            context.template_context("a", "b|c")


if __name__ == "__main__":
    unittest.main()




