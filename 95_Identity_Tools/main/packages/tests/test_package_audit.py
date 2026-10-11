"""
File: packages/tests/test_package_audit.py

Purpose
-------
Tests for packages.audit: the external, append-only package audit trail.

Verifies: packages/audit.py.
Contains 10 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- packages.audit (packages/audit.py)
Standard library: json, pathlib, tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings. Each test builds its own isolated fixtures (temporary
directories, freshly generated keys) in setUp and removes them afterwards, so
tests are order-independent and never touch real data/ folders.

Edge cases
----------
- Build entry has expected shape.
- Unknown action is rejected.
- Empty package id is rejected.
- Record event writes a readable file.
- Write entry rejects bad format marker.
- List entries filters by package id.
- List entries on missing directory returns empty.
- Open denied and custody violation are valid actions.
- Entry filename uses microsecond precision.
- Rapid successive events sort oldest first by filename.

Known limitations
-----------------
- Passing proves only the 10 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest packages.tests.test_package_audit -v
    python tests/run_tests.py
"""

import json
import tempfile
import unittest
from pathlib import Path

from packages import audit
from packages.audit import PackageAuditError


class PackageAuditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_build_entry_has_expected_shape(self):
        entry = audit.build_entry("created", "pkg-1", "Alice")
        self.assertEqual(entry["action"], "created")
        self.assertEqual(entry["package_id"], "pkg-1")
        self.assertEqual(entry["actor_label"], "Alice")
        self.assertIn("recorded_at", entry)

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(PackageAuditError):
            audit.build_entry("teleported", "pkg-1")

    def test_empty_package_id_is_rejected(self):
        with self.assertRaises(PackageAuditError):
            audit.build_entry("created", "")

    def test_record_event_writes_a_readable_file(self):
        path = audit.record_event(self.audit_dir, "opened", "pkg-1", "Bob")
        self.assertTrue(path.is_file())
        stored = json.loads(path.read_text())
        self.assertEqual(stored["action"], "opened")

    def test_write_entry_rejects_bad_format_marker(self):
        with self.assertRaises(PackageAuditError):
            audit.write_entry(self.audit_dir, {"action": "created", "package_id": "pkg-1"})

    def test_list_entries_filters_by_package_id(self):
        audit.record_event(self.audit_dir, "created", "alpha", "A")
        audit.record_event(self.audit_dir, "created", "beta", "B")
        only_alpha = audit.list_entries(self.audit_dir, "alpha")
        self.assertEqual(len(only_alpha), 1)

    def test_list_entries_on_missing_directory_returns_empty(self):
        self.assertEqual(audit.list_entries(self.audit_dir / "nope"), [])

    def test_open_denied_and_custody_violation_are_valid_actions(self):
        audit.build_entry("open_denied", "pkg-1")
        audit.build_entry("custody_violation_detected", "pkg-1")

    # --- Fix 1 (2026-09-10) regression coverage -----------------------
    def test_entry_filename_uses_microsecond_precision(self):
        # Mirrors vault/tests/test_audit_log.py's identical regression test
        # for the same bug class: the filename must embed a
        # microsecond-precision stamp, not the old
        # utc_now_iso().replace(":", "").replace("+", "Z") construction,
        # so same-second events remain distinguishable by timestamp alone
        # (before the random suffix is even considered).
        path = audit.record_event(self.audit_dir, "created", "pkg-1", "Alice")
        self.assertRegex(
            path.name, r"^\d{8}_\d{6}_\d{6}Z_created_pkg-1_[0-9a-f]{8}\.json$"
        )

    def test_rapid_successive_events_sort_oldest_first_by_filename(self):
        # Before this fix, several audit events written in the same
        # wall-clock second -- exactly what packages.main's "demo" command,
        # or any real create -> add-recipient -> open workflow, produces --
        # sorted only by their random suffix, so list_entries()'s own
        # oldest-first ordering guarantee did not actually hold.
        paths = [
            audit.record_event(self.audit_dir, "created", f"pkg-{i}", f"Actor {i}")
            for i in range(20)
        ]
        listed = audit.list_entries(self.audit_dir)
        self.assertEqual([p.name for p in listed], sorted(p.name for p in paths))
        self.assertEqual(listed, paths)


if __name__ == "__main__":
    unittest.main()




