from entitle.core import EntitlementResult
from entitle.records import RecordStore
from entitle.revoke import revoke
# entitle/tracking/__init__.py was removed (0.4.2, PEP 420 namespace packages),
# so each function is imported from its owning submodule rather than the
# former entitle.tracking package-level re-export.
from entitle.tracking.deploy import count_deployments, register_deployment
from entitle.tracking.fork import record_fork
from entitle.tracking.provenance import record_provenance
from entitle.tracking.query import list_records


def _allowed_entitlement(deployment_limit=1, can_run=True, **payload_overrides):
    payload = {
        "product_id": "EntitleDemo", "subject_id": "ResearchLabA", "issuer_id": "JasonBrisart",
        "entitlement_id": "ent-1", "rights": {"can_run": can_run, "deployment_limit": deployment_limit},
    }
    payload.update(payload_overrides)
    return EntitlementResult.allowed_result(payload)


class TestCountDeployments:
    def test_zero_deployments_initially(self, store_path):
        assert count_deployments(RecordStore(store_path), "EntitleDemo", "ResearchLabA", "ent-1") == 0

    def test_counts_only_matching_product_subject_entitlement(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=10)
        register_deployment(store, entitlement, host="node-1")
        register_deployment(store, entitlement, host="node-2")
        other = _allowed_entitlement(deployment_limit=10, entitlement_id="ent-2")
        register_deployment(store, other, host="node-3")
        assert count_deployments(store, "EntitleDemo", "ResearchLabA", "ent-1") == 2
        assert count_deployments(store, "EntitleDemo", "ResearchLabA", "ent-2") == 1


class TestRegisterDeployment:
    def test_denied_entitlement_is_not_recorded(self, store_path):
        store = RecordStore(store_path)
        outcome = register_deployment(store, EntitlementResult.denied_result("wrong_product"), host="node-1")
        assert outcome["recorded"] is False
        assert outcome["reason"] == "entitlement_denied:wrong_product"
        assert store.read_all() == []

    def test_missing_can_run_right_is_refused(self, store_path):
        outcome = register_deployment(RecordStore(store_path), _allowed_entitlement(can_run=False), host="node-1")
        assert outcome["recorded"] is False
        assert outcome["reason"] == "run_right_not_granted"

    def test_first_deployment_within_limit_is_recorded(self, store_path):
        outcome = register_deployment(RecordStore(store_path), _allowed_entitlement(deployment_limit=2), host="node-1", environment="air-gapped")
        assert outcome["recorded"] is True
        assert outcome["reason"] == "deployment_recorded"
        assert outcome["deployments_used"] == 1
        assert outcome["record"]["data"]["host"] == "node-1"
        assert outcome["record"]["data"]["environment"] == "air-gapped"

    def test_deployment_limit_is_enforced(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=2)
        register_deployment(store, entitlement, host="node-1")
        register_deployment(store, entitlement, host="node-2")
        third = register_deployment(store, entitlement, host="node-3")
        assert third["recorded"] is False
        assert third["reason"] == "deployment_limit_reached"
        assert third["deployments_used"] == 2

    def test_none_deployment_limit_means_unlimited(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=None)
        for i in range(5):
            assert register_deployment(store, entitlement, host=f"node-{i}")["recorded"] is True

    def test_revoked_entitlement_refuses_new_deployment(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=10)
        register_deployment(store, entitlement, host="node-1")
        revoke(store, "ent-1", reason="key compromise")
        outcome = register_deployment(store, entitlement, host="node-2")
        assert outcome["recorded"] is False
        assert outcome["reason"] == "entitlement_revoked"

    def test_deployment_record_is_appended_to_hash_chain(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=5)
        register_deployment(store, entitlement, host="node-1")
        register_deployment(store, entitlement, host="node-2")
        status = store.verify_chain()
        assert status.valid is True
        assert status.record_count == 2

    def test_deployment_count_increments_across_calls(self, store_path):
        store = RecordStore(store_path)
        entitlement = _allowed_entitlement(deployment_limit=5)
        first = register_deployment(store, entitlement, host="node-1")
        second = register_deployment(store, entitlement, host="node-2")
        assert first["deployments_used"] == 1
        assert second["deployments_used"] == 2


class TestForkAndProvenance:
    def test_record_fork_persists_expected_data(self, store_path):
        record = record_fork(store=store_path, product="EntitleDemo", source_version="1.4.0", fork_name="lab-a-custom", maintainer="ResearchLabA")
        assert record["record_type"] == "fork"
        assert record["data"]["fork_name"] == "lab-a-custom"

    def test_record_provenance_persists_expected_data(self, store_path):
        record = record_provenance(store=store_path, product="EntitleDemo", origin="JasonBrisart", version="1.4.0", custodian="ResearchLabA")
        assert record["record_type"] == "provenance"
        assert record["data"]["origin"] == "JasonBrisart"

    def test_list_records_filters_by_type(self, store_path):
        record_fork(store=store_path, product="P", source_version="1.0", fork_name="f", maintainer="m")
        record_provenance(store=store_path, product="P", origin="o", version="1.0", custodian="c")
        forks = list_records(store=store_path, record_type="fork")
        assert len(forks) == 1
        assert forks[0]["record_type"] == "fork"

    def test_list_records_without_type_returns_everything(self, store_path):
        record_fork(store=store_path, product="P", source_version="1.0", fork_name="f", maintainer="m")
        record_provenance(store=store_path, product="P", origin="o", version="1.0", custodian="c")
        assert len(list_records(store=store_path)) == 2
