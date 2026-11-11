"""
File: tests/test_revoke.py

Purpose
-------
Verify revocation in entitle/revoke.py: status for an entitlement that was never revoked,
  revoked, reinstated and revoked again, scoping to one entitlement ID (matched exactly as
  typed), preserved history, and that revocations are hash-chained records.

Communication / relationships
-----------------------------
Imports entitle/records.py and entitle/revoke.py. Uses the store_path fixture from
  tests/conftest.py. Run by pytest; nothing imports it.

Settings / parameters
---------------------
Each test gets its own record store under pytest's tmp_path.

Edge cases
----------
The latest revocation or reinstatement for an ID decides its status; an ID with no records
  is active with no last record; a blank ID is refused before anything is written; an ID with a
  space or different capitalisation is a different ID.

Known limitations
-----------------
Does not cover how revocation affects deployments (tests/test_tracking.py) or the command
  line (tests/test_cli.py).

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_revoke.py
"""

import pytest

from entitle.records import RecordStore
from entitle.revoke import is_revoked, reinstate, revocation_status, revoke


class TestRevocationStatus:
    def test_never_revoked_entitlement_is_not_revoked(self, store_path):
        store = RecordStore(store_path)
        status = revocation_status(store, "ent-1")
        assert status["revoked"] is False
        assert status["last_record"] is None

    def test_revoke_marks_entitlement_as_revoked(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1", issuer_id="issuer", product_id="product", reason="key compromise")
        status = revocation_status(store, "ent-1")
        assert status["revoked"] is True
        assert status["last_record"]["data"]["reason"] == "key compromise"

    def test_reinstate_after_revoke_clears_revoked_status(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1", reason="compromised")
        reinstate(store, "ent-1", reason="cleared")
        status = revocation_status(store, "ent-1")
        assert status["revoked"] is False
        assert status["last_record"]["data"]["reason"] == "cleared"

    def test_revoke_after_reinstate_re_revokes(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1", reason="first")
        reinstate(store, "ent-1", reason="second")
        revoke(store, "ent-1", reason="third")
        status = revocation_status(store, "ent-1")
        assert status["revoked"] is True
        assert status["last_record"]["data"]["reason"] == "third"

    def test_status_is_scoped_to_entitlement_id(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1", reason="only ent-1")
        status_other = revocation_status(store, "ent-2")
        assert status_other["revoked"] is False
        assert status_other["last_record"] is None

    def test_ids_are_matched_exactly_as_typed(self, store_path):
        store = RecordStore(store_path)
        revoke(store, " ent-1", reason="typo with a leading space")
        revoke(store, "Ent-1", reason="typo in the capitalisation")
        assert is_revoked(store, "ent-1") is False and is_revoked(store, " ent-1") is True

    def test_full_history_is_preserved_across_multiple_transitions(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1")
        reinstate(store, "ent-1")
        revoke(store, "ent-1")
        reinstate(store, "ent-1")
        all_records = store.read_all()
        assert len(all_records) == 4
        assert is_revoked(store, "ent-1") is False


class TestRequiredFields:
    def test_a_blank_entitlement_id_is_refused_and_nothing_is_written(self, store_path):
        for action in (revoke, reinstate):
            with pytest.raises(ValueError, match="entitlement id is required"):
                action(RecordStore(store_path), "   ")
        assert not store_path.exists()


class TestIsRevoked:
    def test_is_revoked_matches_revocation_status(self, store_path):
        store = RecordStore(store_path)
        assert is_revoked(store, "ent-1") is False
        revoke(store, "ent-1")
        assert is_revoked(store, "ent-1") is True

    def test_revoke_and_reinstate_are_hash_chained(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1")
        reinstate(store, "ent-1")
        status = store.verify_chain()
        assert status.valid is True
        assert status.record_count == 2
