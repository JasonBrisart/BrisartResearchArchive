"""
File: crypto/tests/test_factors.py

Purpose
-------
Tests for crypto.factors: new mac64 bindings verify only for the right master
key, factor name, and value; malformed and unknown records read as "does not
verify"; and bind_factor() rejects invalid input. Legacy keyed_mac bindings are
covered by crypto/tests/test_encryption_link.py, which holds one written by
1.9.2.

Verifies: crypto/factors.py.
Contains 8 test case(s) across 1 TestCase class(es).

Design notes:

Every case uses a random 32-byte master key; bindings are a single MAC, so the
whole module runs in well under a second.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
- crypto.factors (crypto/factors.py)
Standard library: secrets, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
None.

Edge cases
----------
BoundFactorTests:
- A new binding uses mac64 and verifies.
- A wrong value, a wrong master key, and a different factor name do not verify.
- A record whose stored name was edited does not verify under the new name.
- Malformed records, unknown algorithms, and non-string values return False.
- bind_factor() rejects a short master key and a name containing '$'.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest crypto.tests.test_factors -v
"""

import secrets
import unittest

from crypto import factors
from crypto.errors import Bsr2IntegrationError


class BoundFactorTests(unittest.TestCase):
    def setUp(self):
        self.master_key = secrets.token_bytes(32)

    def test_new_binding_uses_mac64_and_verifies(self):
        record = factors.bind_factor(self.master_key, "device", "fingerprint-value")
        self.assertTrue(record.startswith("bsr2$mac64$device$"))
        self.assertTrue(
            factors.verify_bound_factor(self.master_key, "device", "fingerprint-value", record)
        )

    def test_wrong_value_does_not_verify(self):
        record = factors.bind_factor(self.master_key, "device", "correct")
        self.assertFalse(factors.verify_bound_factor(self.master_key, "device", "wrong", record))

    def test_wrong_master_key_does_not_verify(self):
        record = factors.bind_factor(self.master_key, "device", "v")
        self.assertFalse(factors.verify_bound_factor(secrets.token_bytes(32), "device", "v", record))

    def test_a_binding_is_tied_to_its_factor_name(self):
        record = factors.bind_factor(self.master_key, "voice", "v")
        self.assertFalse(factors.verify_bound_factor(self.master_key, "fingerprint", "v", record))

    def test_editing_the_stored_name_does_not_move_a_binding(self):
        record = factors.bind_factor(self.master_key, "voice", "v")
        moved = record.replace("$voice$", "$fingerprint$")
        self.assertFalse(factors.verify_bound_factor(self.master_key, "fingerprint", "v", moved))

    def test_malformed_and_unknown_records_do_not_verify(self):
        record = factors.bind_factor(self.master_key, "device", "v")
        for bad in (
            "not-a-record",
            record.replace("mac64", "sha256"),
            record[:-2],
            record + "zz",
            None,
        ):
            self.assertFalse(factors.verify_bound_factor(self.master_key, "device", "v", bad))
        self.assertFalse(factors.verify_bound_factor(self.master_key, "device", 123, record))

    def test_bind_factor_rejects_short_master_key(self):
        with self.assertRaises(Bsr2IntegrationError):
            factors.bind_factor(b"tooshort", "device", "v")

    def test_bind_factor_rejects_dollar_in_factor_name(self):
        with self.assertRaises(Bsr2IntegrationError):
            factors.bind_factor(self.master_key, "bad$name", "v")


if __name__ == "__main__":
    unittest.main()
