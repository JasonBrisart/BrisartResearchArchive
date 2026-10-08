from entitle.records import RecordStore
from entitle.report import build_report, build_report_for_path, format_text
# entitle/tracking/__init__.py was removed (0.4.2), so these are imported
# directly from their owning submodules rather than the former
# entitle.tracking re-export layer.
from entitle.tracking.fork import record_fork
from entitle.tracking.deploy import register_deployment
from entitle.core import EntitlementResult


class TestBuildReport:
    def test_empty_store_report_has_zero_counts(self, store_path):
        report = build_report(RecordStore(store_path))
        assert report["record_count"] == 0
        assert report["counts_by_type"] == {}
        assert report["deployments_by_product"] == {}
        assert report["chain"]["valid"] is True

    def test_report_counts_records_by_type(self, store_path):
        store = RecordStore(store_path)
        entitlement = EntitlementResult.allowed_result(
            {"product_id": "EntitleDemo", "subject_id": "LabA", "issuer_id": "Jason",
             "entitlement_id": "ent-1", "rights": {"can_run": True, "deployment_limit": 3}}
        )
        register_deployment(store, entitlement, host="node-1")
        register_deployment(store, entitlement, host="node-2")
        record_fork(store=store_path, product="EntitleDemo", source_version="1.0", fork_name="f", maintainer="m")
        report = build_report(store)
        assert report["counts_by_type"]["deployment"] == 2
        assert report["counts_by_type"]["fork"] == 1
        assert report["deployments_by_product"]["EntitleDemo"] == 2

    def test_build_report_for_path_matches_build_report(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        assert build_report_for_path(store_path)["record_count"] == build_report(store)["record_count"]


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
