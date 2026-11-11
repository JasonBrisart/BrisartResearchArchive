"""
File: tests/test_records.py

Purpose
-------
Verify the record store in entitle/records.py: appending and chaining, filtering, chain
  verification against edits, deletions, reordering and unparseable lines, lenient reading for
  the audit, damage of every kind (including bytes that are not UTF-8, as a power failure in the
  middle of a multi-byte character leaves) never making the audit raise, the writer lock under
  concurrent threads and processes (no lost records, no forked chain), a lock held by another
  process, a writer killed while holding the lock, a lock file left behind by 0.5.0, a
  byte-order mark added by a Windows editor, and that a log written by v0.4.1 still verifies
  and can be extended.

Communication / relationships
-----------------------------
Imports entitle/records.py, entitle/common.py (EntitleError) and tests/support.py (fixtures and
  the lock holder). Uses tests/fixtures/legacy_v0_4_1_records.log, a six-record log written by
  Entitle 0.4.1. Needs no encryption. Run by pytest; nothing imports it.

Settings / parameters
---------------------
Each test gets its own store under pytest's tmp_path. The process test starts four Python
  processes of eight appends each; the thread test uses eight threads of ten. Lock tests hold the
  lock from a separate process (tests/support.py) and shorten LOCK_TIMEOUT_SECONDS so they do
  not wait five seconds. The damage test applies each of fourteen corruptions under ten fixed
  seeds, so it is deterministic.

Edge cases
----------
Tampering tests edit the file directly: a changed field, a deleted record, reversed order, a
  truncated line, a line that is JSON but not an object, and a record whose data is not an
  object. Damage tests also cut a multi-byte character in half, insert invalid UTF-8, add
  garbage, NUL bytes, a byte-order mark, Windows line endings and blank lines. A lock held by
  another process is never taken over, however old its file is.

Known limitations
-----------------
The lock is checked on a local Linux filesystem only; the Windows branch of the lock and
  network filesystems are not exercised here. The detection tests cannot show who edited a log,
  only that it no longer verifies. Truncating a log at a record boundary is not detectable and is
  not tested as if it were.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_records.py
"""

import json
import os
import random
import subprocess
import sys
import threading
import time

import pytest

from entitle import records
from entitle.common import EntitleError
from entitle.records import (
    ALL_RECORD_TYPES,
    GENESIS_HASH,
    RECORD_FORMAT,
    RECORD_TYPE_DEPLOYMENT,
    RECORD_TYPE_FORK,
    RECORD_TYPE_PROVENANCE,
    RECORD_TYPE_REINSTATEMENT,
    RECORD_TYPE_REVOCATION,
    RecordStore,
    RecordStoreError,
)
from support import ENTITLE_ROOT, FIXTURES, store_lock_held_elsewhere


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


class TestRecordTypes:
    def test_the_five_types_are_stable_strings(self):
        assert ALL_RECORD_TYPES == ("deployment", "fork", "provenance", "revocation", "reinstatement")
        assert (RECORD_TYPE_DEPLOYMENT, RECORD_TYPE_FORK, RECORD_TYPE_PROVENANCE,
                RECORD_TYPE_REVOCATION, RECORD_TYPE_REINSTATEMENT) == ALL_RECORD_TYPES


class TestCorruptedStore:
    def _corrupt(self, store_path, index, replacement):
        lines = store_path.read_text(encoding="utf-8").strip().split("\n")
        lines[index] = replacement
        store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _filled(self, store_path, count=4):
        store = RecordStore(store_path)
        for i in range(count):
            store.append("fork", {"i": i})
        return store

    def test_truncated_line_is_reported_by_verify_chain_not_raised(self, store_path):
        store = self._filled(store_path)
        self._corrupt(store_path, 2, '{"format": "entitle.record.v1", "reco')
        status = store.verify_chain()
        assert (status.valid, status.broken_index, status.reason) == (False, 2, "unparseable_record")
        assert status.record_count == 4

    def test_json_that_is_not_an_object_is_unparseable(self, store_path):
        store = self._filled(store_path, 2)
        self._corrupt(store_path, 1, "[1, 2, 3]")
        assert store.verify_chain().reason == "unparseable_record"

    def test_a_record_whose_data_is_not_an_object_is_unparseable(self, store_path):
        store = self._filled(store_path, 2)
        record = json.loads(store_path.read_text(encoding="utf-8").split("\n")[1])
        record["data"] = ["not", "an", "object"]
        self._corrupt(store_path, 1, json.dumps(record))
        assert store.verify_chain().reason == "unparseable_record"
        with pytest.raises(RecordStoreError, match="record 1 has no data object"):
            store.read_all()

    def test_lenient_reading_skips_only_the_unreadable_lines(self, store_path):
        store = self._filled(store_path, 4)
        self._corrupt(store_path, 2, "not json")
        assert [r["data"]["i"] for r in store.read_all(strict=False)] == [0, 1, 3]

    def test_read_all_and_append_raise_a_clear_error(self, store_path):
        store = self._filled(store_path, 2)
        self._corrupt(store_path, 0, "not json")
        with pytest.raises(RecordStoreError, match="record 0 is not a valid JSON object") as caught:
            store.read_all()
        assert isinstance(caught.value, EntitleError)
        before = store_path.read_text(encoding="utf-8")
        with pytest.raises(RecordStoreError):
            store.append("fork", {"late": True})
        assert store_path.read_text(encoding="utf-8") == before


class TestDamageNeverMakesTheAuditRaise:
    @staticmethod
    def _damage(kind, raw, rng):
        lines = raw.split(b"\n")
        position = rng.randrange(1, len(raw) - 1)
        if kind == "truncate":
            return raw[:position]
        if kind == "flip_bit":
            return raw[:position] + bytes([raw[position] ^ (1 << rng.randrange(8))]) + raw[position + 1:]
        if kind == "cut_multibyte_character":  # what a power failure mid-append leaves behind
            return raw[: raw.rfind("лаб".encode()) + 1]
        if kind == "invalid_utf8":
            return raw[:position] + b"\xff\xfe\x80" + raw[position:]
        if kind == "garbage_line":
            return raw + rng.randbytes(40) + b"\n"
        if kind == "nul_byte":
            return raw[:position] + b"\x00" + raw[position:]
        if kind == "delete_line":  # never the last record: cutting the end is undetectable (see Known limitations)
            del lines[rng.randrange(len(lines) - 2)]
            return b"\n".join(lines)
        if kind == "duplicate_line":
            index = rng.randrange(len(lines) - 1)
            lines.insert(index, lines[index])
            return b"\n".join(lines)
        if kind == "swap_lines":
            index = rng.randrange(len(lines) - 2)
            lines[index], lines[index + 1] = lines[index + 1], lines[index]
            return b"\n".join(lines)
        if kind == "byte_order_mark":
            return b"\xef\xbb\xbf" + raw
        if kind == "windows_line_endings":
            return raw.replace(b"\n", b"\r\n")
        if kind == "blank_lines":
            return raw.replace(b"\n", b"\n\n", 2)
        if kind == "data_replaced_by_list":
            record = json.loads(lines[1])
            record["data"] = [1]
            lines[1] = json.dumps(record).encode()
            return b"\n".join(lines)
        if kind == "empty":
            return b""
        raise AssertionError(kind)

    KINDS = ("truncate", "flip_bit", "cut_multibyte_character", "invalid_utf8", "garbage_line", "nul_byte",
             "delete_line", "duplicate_line", "swap_lines", "byte_order_mark", "windows_line_endings",
             "blank_lines", "data_replaced_by_list", "empty")
    HARMLESS = {"byte_order_mark", "windows_line_endings", "blank_lines", "empty"}

    @pytest.mark.parametrize("kind", KINDS)
    def test_every_kind_of_damage_is_reported_or_harmless_never_raised(self, store_path, kind):
        store = RecordStore(store_path)
        for i in range(5):
            store.append("fork", {"i": i, "name": f"лаб-实验室-{i}"})
        original = store_path.read_bytes()
        for seed in range(10):
            store_path.write_bytes(self._damage(kind, original, random.Random(seed)))
            status = store.verify_chain()  # must never raise
            readable = store.read_all(strict=False)  # must never raise
            assert len(readable) <= status.record_count
            if kind in self.HARMLESS:
                assert status.valid, (kind, seed, status.reason)
            elif kind not in ("truncate", "flip_bit", "nul_byte"):
                assert not status.valid, (kind, seed)  # these always change what the chain covers

    def test_a_character_cut_in_half_is_one_damaged_record_not_an_unreadable_log(self, store_path):
        store = RecordStore(store_path)
        for i in range(3):
            store.append("fork", {"i": i, "host": "узел-" + str(i)})
        raw = store_path.read_bytes()
        store_path.write_bytes(raw[: raw.rfind("узел".encode()) + 1])  # the last record loses most of a character
        status = store.verify_chain()
        assert (status.valid, status.broken_index, status.reason) == (False, 2, "unparseable_record")
        assert [r["data"]["i"] for r in store.read_all(strict=False)] == [0, 1]


class TestEditorsAndWindows:
    def test_a_byte_order_mark_at_the_start_is_ignored_and_appending_still_works(self, store_path):
        store = RecordStore(store_path)
        store.append("fork", {"a": 1})
        store_path.write_bytes(b"\xef\xbb\xbf" + store_path.read_bytes())
        assert store.verify_chain().valid and store.read_all()[0]["data"] == {"a": 1}
        store.append("fork", {"a": 2})
        status = store.verify_chain()
        assert (status.valid, status.record_count) == (True, 2)

    def test_windows_line_endings_do_not_change_the_chain(self, store_path):
        store = RecordStore(store_path)
        for i in range(3):
            store.append("fork", {"i": i})
        store_path.write_bytes(store_path.read_bytes().replace(b"\n", b"\r\n"))
        assert store.verify_chain().valid and [r["data"]["i"] for r in store.read_all()] == [0, 1, 2]


class TestWriterLock:
    def test_nested_transactions_do_not_deadlock(self, store_path):
        store = RecordStore(store_path)
        with store.transaction():
            with store.transaction():
                store.append("fork", {"a": 1})
            store.append("fork", {"a": 2})
        assert store.verify_chain().record_count == 2

    def test_concurrent_threads_keep_every_record_and_a_valid_chain(self, store_path):
        store = RecordStore(store_path)
        barrier = threading.Barrier(8)

        def work(thread):
            barrier.wait()
            for i in range(10):
                store.append("fork", {"thread": thread, "i": i})

        threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        status = store.verify_chain()
        assert status.valid, status.reason
        assert status.record_count == 80

    def test_concurrent_processes_keep_every_record_and_a_valid_chain(self, store_path):
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "from entitle.records import RecordStore; s = RecordStore(sys.argv[2]);"
            "[s.append('fork', {'p': sys.argv[3], 'i': i}) for i in range(8)]"
        )
        processes = [
            subprocess.Popen([sys.executable, "-c", code, str(ENTITLE_ROOT), str(store_path), str(n)])
            for n in range(4)
        ]
        assert [p.wait(timeout=120) for p in processes] == [0, 0, 0, 0]
        status = RecordStore(store_path).verify_chain()
        assert status.valid, status.reason
        assert status.record_count == 32

    def test_a_lock_held_by_another_process_times_out_and_is_never_taken(self, store_path, monkeypatch):
        monkeypatch.setattr(records, "LOCK_TIMEOUT_SECONDS", 0.3)
        with store_lock_held_elsewhere(store_path):
            started = time.monotonic()
            with pytest.raises(TimeoutError, match="record store is busy"):
                RecordStore(store_path).append("fork", {"a": 1})
            assert time.monotonic() - started < 5
        assert not store_path.exists()

    def test_a_killed_writer_releases_the_store_at_once(self, store_path, monkeypatch):
        monkeypatch.setattr(records, "LOCK_TIMEOUT_SECONDS", 2.0)
        with store_lock_held_elsewhere(store_path):
            pass  # the holder is killed here, while it still holds the lock
        started = time.monotonic()
        RecordStore(store_path).append("fork", {"a": 1})
        assert time.monotonic() - started < 2.0
        assert RecordStore(store_path).verify_chain().record_count == 1

    def test_an_old_lock_file_nobody_holds_does_not_block_writers(self, store_path):
        store_path.parent.mkdir(parents=True)
        lock = store_path.with_name(store_path.name + ".lock")
        lock.write_text("left by 0.5.0", encoding="utf-8")
        old = lock.stat().st_mtime - 120
        os.utime(lock, (old, old))
        RecordStore(store_path).append("fork", {"a": 1})
        assert RecordStore(store_path).verify_chain().record_count == 1


class TestRecordsWrittenByV041:
    def test_the_previous_release_log_still_verifies_and_reads(self):
        store = RecordStore(FIXTURES / "legacy_v0_4_1_records.log")
        status = store.verify_chain()
        assert (status.valid, status.record_count) == (True, 6)
        assert sorted(r["record_type"] for r in store.read_all()) == sorted(
            ["deployment", "deployment", "fork", "provenance", "revocation", "reinstatement"]
        )
        assert all(r["format"] == RECORD_FORMAT for r in store.read_all())

    def test_new_records_can_extend_the_previous_release_log(self, tmp_path):
        copy = tmp_path / "legacy.log"
        copy.write_bytes((FIXTURES / "legacy_v0_4_1_records.log").read_bytes())
        store = RecordStore(copy)
        store.append("fork", {"fork_name": "after-upgrade"})
        status = store.verify_chain()
        assert (status.valid, status.record_count) == (True, 7)
