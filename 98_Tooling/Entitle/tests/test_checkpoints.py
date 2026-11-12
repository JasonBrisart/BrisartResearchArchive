"""
File: tests/test_checkpoints.py

Purpose
-------
Verify entitle/checkpoints.py: a signed checkpoint proves the first N records of a log are
  unchanged, which is the case the hash chain alone cannot catch (a log cut short, or rewritten
  from a record onward with every later hash recomputed), while records added later are fine.

Communication / relationships
-----------------------------
Imports entitle/checkpoints.py, entitle/records.py (RecordStore, RecordStoreError, and the entry
  hash function to forge a rewritten log the way an attacker would) and tests/support.py
  (make_keys). Run by pytest; nothing imports it.

Settings / parameters
---------------------
One key pair per module; each test writes its own log of fork records under pytest's tmp_path.

Edge cases
----------
Covers an empty log, records appended after the checkpoint, truncation by one record, a
  rewritten log whose own chain verifies, an edited record inside the checkpointed prefix, a
  damaged log refused at creation, an untrusted key, a modified checkpoint file, and refusing to
  replace an existing checkpoint.

Known limitations
-----------------
A checkpoint says nothing about records written after it; that is by design and is tested only
  as "still valid".

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_checkpoints.py
"""
import json

import pytest

from entitle import records
from entitle.checkpoints import create_checkpoint, verify_checkpoint
from entitle.records import RecordStore, RecordStoreError
from support import make_keys


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    return make_keys(tmp_path_factory.mktemp("keys"))


def _log(store_path, count):
    store = RecordStore(store_path)
    for i in range(count):
        store.append("fork", {"i": i})
    return store


def _checkpoint(store, keys, tmp_path):
    path = tmp_path / "log.entitle-checkpoint"
    create_checkpoint(store, keys[0], output=path, overwrite=True)
    return path


def test_an_unchanged_log_and_one_that_only_grew_both_verify(store_path, keys, tmp_path):
    store = _log(store_path, 3)
    checkpoint = _checkpoint(store, keys, tmp_path)
    result = verify_checkpoint(store, checkpoint, [keys[1]])
    assert (result["valid"], result["reason"], result["record_count"], result["signed_by"]) == (
        True, "ok", 3, keys[1].key_id)
    store.append("fork", {"i": 3})
    assert verify_checkpoint(store, checkpoint, [keys[1]])["records_now"] == 4


def test_an_empty_log_can_be_checkpointed(store_path, keys, tmp_path):
    store = RecordStore(store_path)
    assert verify_checkpoint(store, _checkpoint(store, keys, tmp_path), [keys[1]])["valid"]


def test_cutting_the_end_off_is_caught(store_path, keys, tmp_path):
    store = _log(store_path, 3)
    checkpoint = _checkpoint(store, keys, tmp_path)
    lines = store_path.read_text(encoding="utf-8").splitlines()
    store_path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")
    assert store.verify_chain().valid  # the chain alone cannot see it
    assert verify_checkpoint(store, checkpoint, [keys[1]])["reason"] == "log_truncated"


def test_a_log_rewritten_with_recomputed_hashes_is_caught(store_path, keys, tmp_path):
    store = _log(store_path, 3)
    checkpoint = _checkpoint(store, keys, tmp_path)
    rewritten, previous = [], records.GENESIS_HASH
    for line in store_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        record["data"]["i"] += 100
        record["prev_hash"] = previous
        record["entry_hash"] = records._entry_hash(record)
        previous = record["entry_hash"]
        rewritten.append(json.dumps(record, sort_keys=True))
    store_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    assert store.verify_chain().valid  # a perfect forgery as far as the chain can tell
    assert verify_checkpoint(store, checkpoint, [keys[1]])["reason"] == "log_rewritten"


def test_an_edit_inside_the_checkpointed_records_is_a_broken_chain(store_path, keys, tmp_path):
    store = _log(store_path, 3)
    checkpoint = _checkpoint(store, keys, tmp_path)
    lines = store_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["data"]["i"] = 99
    lines[0] = json.dumps(record, sort_keys=True)
    store_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify_checkpoint(store, checkpoint, [keys[1]])["reason"] == "chain_broken"


def test_a_damaged_log_is_never_vouched_for(store_path, keys, tmp_path):
    store = _log(store_path, 2)
    store_path.write_text(store_path.read_text(encoding="utf-8")[:-20], encoding="utf-8")
    with pytest.raises(RecordStoreError, match="hash chain is broken"):
        create_checkpoint(store, keys[0], output=tmp_path / "x")
    assert not (tmp_path / "x").exists()


def test_an_untrusted_key_or_a_modified_checkpoint_is_refused(store_path, keys, tmp_path):
    store = _log(store_path, 2)
    checkpoint = _checkpoint(store, keys, tmp_path)
    stranger = make_keys(tmp_path / "stranger", name="Stranger")
    assert verify_checkpoint(store, checkpoint, [stranger[1]])["reason"] == "unknown_signing_key"
    text = checkpoint.read_text(encoding="utf-8")
    checkpoint.write_text(text.replace("Key-Id: ", "Key-Id: 0", 1), encoding="utf-8")
    assert verify_checkpoint(store, checkpoint, [keys[1]])["reason"] == "unknown_signing_key"


def test_an_existing_checkpoint_is_not_replaced_unless_asked(store_path, keys, tmp_path):
    store = _log(store_path, 1)
    path = _checkpoint(store, keys, tmp_path)
    with pytest.raises(FileExistsError):
        create_checkpoint(store, keys[0], output=path)
