import json

from entitle.records import GENESIS_HASH, RECORD_FORMAT, RecordStore


class TestRecordStoreBasics:
    def test_empty_store_returns_no_records(self, store_path):
        store = RecordStore(store_path)
        assert store.read_all() == []
        assert store.last_hash() == GENESIS_HASH

    def test_append_creates_parent_directory(self, store_path):
        assert not store_path.parent.exists()
        store = RecordStore(store_path)
        store.append("deployment", {"host": "node-1"})
        assert store_path.parent.exists()
        assert store_path.exists()

    def test_append_returns_record_with_expected_fields(self, store_path):
        store = RecordStore(store_path)
        record = store.append("fork", {"fork_name": "custom"})
        assert record["format"] == RECORD_FORMAT
        assert record["record_type"] == "fork"
        assert record["data"] == {"fork_name": "custom"}
        assert record["prev_hash"] == GENESIS_HASH
        assert "entry_hash" in record
        assert "record_id" in record
        assert "created_at" in record

    def test_record_format_marker_is_present_and_versioned(self, store_path):
        store = RecordStore(store_path)
        record = store.append("fork", {"a": 1})
        assert record["format"] == "entitle.record.v1"

    def test_each_line_is_valid_json(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store.append("provenance", {"b": 2})
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # must not raise

    def test_records_are_chained_by_hash(self, store_path):
        store = RecordStore(store_path)
        first = store.append("fork", {"a": 1})
        second = store.append("fork", {"b": 2})
        assert second["prev_hash"] == first["entry_hash"]
        assert store.last_hash() == second["entry_hash"]


class TestRecordStoreFilter:
    def test_filter_by_record_type(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store.append("provenance", {"b": 2})
        store.append("fork", {"c": 3})
        forks = store.filter(record_type="fork")
        assert len(forks) == 2
        assert all(r["record_type"] == "fork" for r in forks)

    def test_filter_by_predicate(self, store_path):
        store = RecordStore(store_path)
        store.append("deployment", {"host": "node-1"})
        store.append("deployment", {"host": "node-2"})
        matches = store.filter(
            record_type="deployment",
            predicate=lambda r: r["data"]["host"] == "node-2",
        )
        assert len(matches) == 1
        assert matches[0]["data"]["host"] == "node-2"

    def test_filter_with_no_matches_returns_empty_list(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        assert store.filter(record_type="revocation") == []


class TestVerifyChain:
    def test_empty_store_chain_is_valid(self, store_path):
        store = RecordStore(store_path)
        status = store.verify_chain()
        assert status.valid is True
        assert status.record_count == 0
        assert status.broken_index is None

    def test_intact_chain_across_multiple_records_is_valid(self, store_path):
        store = RecordStore(store_path)
        for i in range(5):
            store.append("fork", {"index": i})
        status = store.verify_chain()
        assert status.valid is True
        assert status.record_count == 5

    def test_tampering_with_a_field_breaks_the_chain(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store.append("fork", {"a": 2})
        store.append("fork", {"a": 3})
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        records = [json.loads(line) for line in lines]
        # Tamper with the middle record's data without recomputing its hash.
        records[1]["data"]["a"] = 999
        store_path.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
            encoding="utf-8",
        )
        status = store.verify_chain()
        assert status.valid is False
        assert status.broken_index == 1
        assert status.reason == "entry_hash_mismatch"

    def test_deleting_a_record_breaks_the_chain(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store.append("fork", {"a": 2})
        store.append("fork", {"a": 3})
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        records = [json.loads(line) for line in lines]
        del records[1]  # remove the middle record; later prev_hash no longer matches
        store_path.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
            encoding="utf-8",
        )
        status = store.verify_chain()
        assert status.valid is False
        assert status.reason == "prev_hash_mismatch"

    def test_reordering_records_breaks_the_chain(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store.append("fork", {"a": 2})
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        records = [json.loads(line) for line in lines]
        records.reverse()
        store_path.write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in records) + "\n",
            encoding="utf-8",
        )
        status = store.verify_chain()
        assert status.valid is False
        assert status.broken_index == 0

    def test_to_dict_reflects_status(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        status = store.verify_chain()
        as_dict = status.to_dict()
        assert as_dict["valid"] is True
        assert as_dict["record_count"] == 1
