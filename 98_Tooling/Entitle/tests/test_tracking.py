"""
File: tests/test_tracking.py

Purpose
-------
Verify entitle/tracking.py: counting deployments, the governed deployment rules (denied
  entitlement, missing can_run, deployment limit, unlimited, revoked), that deployments extend
  the hash chain, that forks and provenance are recorded without any policy check but refuse
  blank required fields, that the limit holds when many deployments race, and deploy_from_file
  against real entitlement files, including one written by the previous encryption.

Communication / relationships
-----------------------------
Imports entitle/rights.py, entitle/records.py, entitle/revoke.py, entitle/tracking.py and
  tests/support.py. Uses the store_path fixture from tests/conftest.py. Run by pytest;
  nothing imports it.

Settings / parameters
---------------------
Most tests build an EntitlementResult in memory; the deploy_from_file tests issue real
  entitlements into pytest's tmp_path. The race test runs eight threads against a limit of two,
  five times.

Edge cases
----------
A refusal is a returned outcome with a reason, never an exception, and writes no record. A
  wrong key is refused with entitlement_denied:bsr_verification_failed. A blank host or blank
  required fork or provenance field raises ValueError and writes nothing.

Known limitations
-----------------
Does not run the command line or the window (tests/test_cli.py, tests/test_gui.py) and does
  not test racing processes for deployments; process-level locking is covered in
  tests/test_records.py.

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_tracking.py
"""

import threading

import pytest

from entitle.rights import EntitlementResult
from entitle.records import RecordStore
from entitle.revoke import revoke
from entitle.tracking import count_deployments, deploy_from_file, record_fork, record_provenance, register_deployment
from support import ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PRODUCT, SUBJECT, issue_demo


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
        record = record_fork(RecordStore(store_path), product="EntitleDemo", source_version="1.4.0", fork_name="lab-a-custom", maintainer="ResearchLabA")
        assert record["record_type"] == "fork"
        assert record["data"]["fork_name"] == "lab-a-custom"

    def test_record_provenance_persists_expected_data(self, store_path):
        record = record_provenance(RecordStore(store_path), product="EntitleDemo", origin="JasonBrisart", version="1.4.0", custodian="ResearchLabA")
        assert record["record_type"] == "provenance"
        assert record["data"]["origin"] == "JasonBrisart"

    def test_list_records_filters_by_type(self, store_path):
        record_fork(RecordStore(store_path), product="P", source_version="1.0", fork_name="f", maintainer="m")
        record_provenance(RecordStore(store_path), product="P", origin="o", version="1.0", custodian="c")
        forks = RecordStore(store_path).filter(record_type="fork")
        assert len(forks) == 1
        assert forks[0]["record_type"] == "fork"

    def test_list_records_without_type_returns_everything(self, store_path):
        record_fork(RecordStore(store_path), product="P", source_version="1.0", fork_name="f", maintainer="m")
        record_provenance(RecordStore(store_path), product="P", origin="o", version="1.0", custodian="c")
        assert len(RecordStore(store_path).filter()) == 2


class TestRequiredFields:
    def test_blank_required_fields_are_refused_and_nothing_is_written(self, store_path):
        store = RecordStore(store_path)
        with pytest.raises(ValueError, match="host is required"):
            register_deployment(store, _allowed_entitlement(), host="  ")
        with pytest.raises(ValueError, match="fork name is required"):
            record_fork(store, product="P", source_version="1", fork_name="", maintainer="m")
        with pytest.raises(ValueError, match="custodian is required"):
            record_provenance(store, product="P", origin="o", version="1", custodian=None)
        assert not store_path.exists()


class TestConcurrentDeployments:
    def test_the_limit_holds_when_many_deployments_race(self, store_path):
        entitlement = _allowed_entitlement(deployment_limit=2)
        for _ in range(5):
            path = store_path.with_name(f"race_{_}.log")
            store = RecordStore(path)
            barrier = threading.Barrier(8)
            recorded = []

            def work(n):
                barrier.wait()
                recorded.append(register_deployment(store, entitlement, host=f"node-{n}")["recorded"])

            threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
            [t.start() for t in threads]
            [t.join() for t in threads]
            assert sum(recorded) == 2
            assert store.verify_chain().valid
            assert count_deployments(store, "EntitleDemo", "ResearchLabA", "ent-1") == 2


class TestDeployFromFile:
    def _deploy(self, tmp_path, store, **overrides):
        args = dict(issuer=ISSUER, subject=SUBJECT, product=PRODUCT, master_key=MASTER_KEY,
                    entitlement_path=tmp_path / "lab.entitle", host="node-1", store=store)
        args.update(overrides)
        return deploy_from_file(**args)

    def test_a_verified_entitlement_is_recorded_with_its_identity(self, tmp_path, store_path):
        issue_demo(tmp_path / "lab.entitle", entitlement_id="lab-1", deployment_limit=2)
        outcome = self._deploy(tmp_path, RecordStore(store_path), environment="air-gapped", notes="n")
        assert outcome["recorded"] is True
        data = outcome["record"]["data"]
        assert (data["entitlement_id"], data["issuer_id"], data["host"], data["environment"]) == (
            "lab-1", ISSUER, "node-1", "air-gapped")

    def test_a_wrong_key_is_refused_and_nothing_is_written(self, tmp_path, store_path):
        issue_demo(tmp_path / "lab.entitle")
        outcome = self._deploy(tmp_path, RecordStore(store_path), master_key="wrong-key-wrong-key-wrong-key-wrong-key")
        assert (outcome["recorded"], outcome["reason"]) == (False, "entitlement_denied:bsr_verification_failed")
        assert not store_path.exists()

    def test_an_entitlement_written_by_the_previous_encryption_still_deploys(self, store_path):
        outcome = self._deploy(LEGACY_ENTITLEMENT.parent, RecordStore(store_path), entitlement_path=LEGACY_ENTITLEMENT)
        assert outcome["recorded"] is True and outcome["deployment_limit"] == 2
        assert outcome["record"]["data"]["entitlement_id"] == "lab-a-demo-001"

    def test_revocation_is_honored_across_calls(self, tmp_path, store_path):
        issue_demo(tmp_path / "lab.entitle", entitlement_id="lab-1", deployment_limit=5)
        store = RecordStore(store_path)
        assert self._deploy(tmp_path, store)["recorded"] is True
        revoke(store, "lab-1")
        assert self._deploy(tmp_path, store, host="node-2")["reason"] == "entitlement_revoked"
