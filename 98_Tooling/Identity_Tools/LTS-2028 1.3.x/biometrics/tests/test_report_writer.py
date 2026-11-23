"""
File: biometrics/tests/test_report_writer.py

Purpose
-------
Tests for biometrics.reports.report_writer.

Verifies: biometrics/reports/report_writer.py.
Contains 7 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.reports.report_writer (biometrics/reports/report_writer.py)
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
- Enrollment report sorts modalities.
- Enrollment report requires at least one modality.
- Verification report keeps only non secret fields.
- Verification report requires identity and results.
- Write report rejects bad format marker.
- Write and list reports round trip.
- List reports on missing dir returns empty.

Known limitations
-----------------
- Passing proves only the 7 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_report_writer -v
    python tests/run_tests.py
"""

import json
import tempfile
import unittest
from pathlib import Path
from biometrics.reports import report_writer
from biometrics.reports.report_writer import ReportWriterError


class ReportWriterTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.report_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_enrollment_report_sorts_modalities(self):
        report = report_writer.build_enrollment_report("alice", "Alice", ["voice", "fingerprint"])
        self.assertEqual(report["modalities_enrolled"], ["fingerprint", "voice"])

    def test_enrollment_report_requires_at_least_one_modality(self):
        with self.assertRaises(ReportWriterError):
            report_writer.build_enrollment_report("alice", "Alice", [])

    def test_verification_report_keeps_only_non_secret_fields(self):
        result = {
            "identity_id": "alice",
            "matched": True,
            "results": [{"modality": "voice", "score": 0.99, "threshold": 0.85,
                         "matched": True, "vector": [1, 2, 3]}],
        }
        report = report_writer.build_verification_report(result)
        self.assertNotIn("vector", report["modality_results"][0])
        self.assertTrue(report["matched"])

    def test_verification_report_requires_identity_and_results(self):
        with self.assertRaises(ReportWriterError):
            report_writer.build_verification_report({"identity_id": "alice"})

    def test_write_report_rejects_bad_format_marker(self):
        with self.assertRaises(ReportWriterError):
            report_writer.write_report(self.report_dir, {"event_type": "x", "identity_id": "y"})

    def test_write_and_list_reports_round_trip(self):
        report = report_writer.build_enrollment_report("bob", "Bob", ["voice"])
        path = report_writer.write_report(self.report_dir, report)
        self.assertEqual(json.loads(path.read_text())["identity_id"], "bob")
        self.assertEqual(len(report_writer.list_reports(self.report_dir, "bob")), 1)

    def test_list_reports_on_missing_dir_returns_empty(self):
        self.assertEqual(report_writer.list_reports(self.report_dir / "nope"), [])


if __name__ == "__main__":
    unittest.main()




