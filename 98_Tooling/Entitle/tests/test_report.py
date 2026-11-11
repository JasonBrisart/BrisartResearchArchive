"""
File: tests/test_report.py

Purpose
-------
Verify entitle/report.py: counts by record type and deployments by product, the text
  rendering (empty sections, a broken chain), a store file that does not exist, a store with a
  truncated record, and a report over a log written by v0.4.1.

Communication / relationships
-----------------------------
Imports entitle/rights.py, entitle/records.py, entitle/report.py, entitle/tracking.py and
  tests/support.py. Uses the store_path fixture from tests/conftest.py and
  tests/fixtures/legacy_v0_4_1_records.log. Run by pytest; nothing imports it.

Settings / parameters
---------------------
Each test gets its own store under pytest's tmp_path; the corruption test truncates one line
  of a three-record log.

Edge cases
----------
A missing store reports store_exists false and the text says so; an existing empty store is
  verified across 0 records with no such note; a damaged store still yields a report that counts
  the readable records, states how many are unreadable, and marks the chain BROKEN.

Known limitations
-----------------
Does not run the report command (tests/test_cli.py) and does not test very large logs.

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_report.py
"""

from entitle.rights import EntitlementResult
from entitle.records import RecordStore
from entitle.report import build_report, format_text
from entitle.tracking import record_fork, register_deployment
from support import FIXTURES


class TestBuildReport:
    def test_empty_store_report_has_zero_counts(self, store_path):
        report = build_report(RecordStore(store_path))
        assert report["record_count"] == 0 and report["unreadable_records"] == 0
        assert report["counts_by_type"] == {}
        assert report["deployments_by_product"] == {}
        assert report["chain"]["valid"] is True
        assert "Unreadable" not in format_text(report)

    def test_report_counts_records_by_type(self, store_path):
        store = RecordStore(store_path)
        entitlement = EntitlementResult.allowed_result(
            {"product_id": "EntitleDemo", "subject_id": "LabA", "issuer_id": "Jason",
             "entitlement_id": "ent-1", "rights": {"can_run": True, "deployment_limit": 3}}
        )
        register_deployment(store, entitlement, host="node-1")
        register_deployment(store, entitlement, host="node-2")
        record_fork(store, product="EntitleDemo", source_version="1.0", fork_name="f", maintainer="m")
        report = build_report(store)
        assert report["counts_by_type"]["deployment"] == 2
        assert report["counts_by_type"]["fork"] == 1
        assert report["deployments_by_product"]["EntitleDemo"] == 2


class TestFormatText:
    def test_empty_report_renders_none_placeholders(self, store_path):
        report = build_report(RecordStore(store_path))
        text = format_text(report)
        assert "Entitle Audit Report" in text
        assert "(none)" in text
        assert "VERIFIED" in text

    def test_broken_chain_is_reported_in_text(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        report = build_report(store)
        report["chain"]["valid"] = False
        report["chain"]["reason"] = "entry_hash_mismatch"
        report["chain"]["broken_index"] = 0
        text = format_text(report)
        assert "BROKEN" in text
        assert "entry_hash_mismatch" in text


class TestStoresThatAreMissingOrDamaged:
    def test_a_missing_store_is_reported_as_missing_not_as_verified(self, tmp_path):
        report = build_report(RecordStore(tmp_path / "typo" / "records.log"))
        assert report["store_exists"] is False and report["record_count"] == 0
        text = format_text(report)
        assert "this store file does not exist" in text

    def test_an_existing_empty_store_has_no_missing_note(self, store_path):
        store_path.parent.mkdir(parents=True)
        store_path.write_text("", encoding="utf-8")
        report = build_report(RecordStore(store_path))
        assert report["store_exists"] is True
        assert "does not exist" not in format_text(report)

    def test_a_truncated_record_produces_a_broken_report_instead_of_crashing(self, store_path):
        store = RecordStore(store_path)
        for i in range(3):
            store.append("fork", {"i": i})
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        lines[1] = lines[1][:30]
        store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = build_report(store)
        assert report["chain"]["valid"] is False
        assert (report["chain"]["reason"], report["chain"]["broken_index"]) == ("unparseable_record", 1)
        assert (report["record_count"], report["unreadable_records"]) == (2, 1)
        assert report["counts_by_type"] == {"fork": 2}
        text = format_text(report)
        assert "Unreadable records: 1" in text
        assert "BROKEN: unparseable_record at record index 1." in text

    def test_the_previous_release_log_reports_its_known_counts(self):
        report = build_report(RecordStore(FIXTURES / "legacy_v0_4_1_records.log"))
        assert report["record_count"] == 6 and report["chain"]["valid"] is True
        assert report["counts_by_type"]["deployment"] == 2
        assert report["deployments_by_product"] == {"EntitleDemo": 2}
