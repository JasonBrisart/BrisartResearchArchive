"""
File: vault/tests/test_record_ids_and_time.py

Purpose
-------
Tests for vault.core.ids and vault.core.time_tools.

Verifies: vault/core/ids.py, vault/core/time_tools.py.
Contains 11 test case(s) across 2 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- vault.core.ids (vault/core/ids.py)
- vault.core.time_tools (vault/core/time_tools.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
RecordIdTests:
- New record id is valid.
- New record ids are unique.
- Empty id is rejected.
- Whitespace padded id is rejected.
- Separator in id is rejected.
- Nul in id is rejected.
- Overlong id is rejected.
- Non string id is rejected.
TimeToolsTests:
- New record shares one timestamp.
- Stamp updated preserves creation time.
- Chronological order is a string comparison.

Known limitations
-----------------
- Passing proves only the 11 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest vault.tests.test_record_ids_and_time -v
    python tests/run_tests.py
"""

import unittest
from vault.core import ids, time_tools
from vault.core.ids import RecordIdError


class RecordIdTests(unittest.TestCase):
    def test_new_record_id_is_valid(self):
        rid = ids.new_record_id()
        self.assertEqual(ids.validate_record_id(rid), rid)

    def test_new_record_ids_are_unique(self):
        generated = {ids.new_record_id() for _ in range(1000)}
        self.assertEqual(len(generated), 1000)

    def test_empty_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id("")

    def test_whitespace_padded_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id("  rid  ")

    def test_separator_in_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id("a|b")

    def test_nul_in_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id("a\x00b")

    def test_overlong_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id("x" * 200)

    def test_non_string_id_is_rejected(self):
        with self.assertRaises(RecordIdError):
            ids.validate_record_id(12345)


class TimeToolsTests(unittest.TestCase):
    def test_new_record_shares_one_timestamp(self):
        # The 0.4.0 fix: created_at and updated_at must be identical for a
        # brand-new record so it never looks pre-modified.
        stamps = time_tools.stamp_new_record()
        self.assertEqual(stamps["created_at"], stamps["updated_at"])

    def test_stamp_updated_preserves_creation_time(self):
        created = "2026-08-24T10:00:00+00:00"
        stamps = time_tools.stamp_updated(created)
        self.assertEqual(stamps["created_at"], created)

    def test_chronological_order_is_a_string_comparison(self):
        self.assertTrue(time_tools.is_chronologically_ordered(
            "2026-08-24T10:00:00+00:00", "2026-08-24T10:00:01+00:00"))
        self.assertFalse(time_tools.is_chronologically_ordered(
            "2026-08-24T10:00:02+00:00", "2026-08-24T10:00:01+00:00"))


if __name__ == "__main__":
    unittest.main()




