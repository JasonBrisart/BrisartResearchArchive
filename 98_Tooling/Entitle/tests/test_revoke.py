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

    def test_full_history_is_preserved_across_multiple_transitions(self, store_path):
        store = RecordStore(store_path)
        revoke(store, "ent-1")
        reinstate(store, "ent-1")
        revoke(store, "ent-1")
        reinstate(store, "ent-1")
        all_records = store.read_all()
        assert len(all_records) == 4
        assert is_revoked(store, "ent-1") is False


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
