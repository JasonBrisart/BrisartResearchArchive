"""
File: entitle/checkpoints.py

Purpose
-------
Close the one gap a hash chain cannot: a log cut short at the end, or rewritten from some record
  onward with every later hash recomputed, still verifies on its own. A checkpoint is a signed
  statement "this log had N records and record N ended with this hash", kept somewhere the log's
  operator cannot edit (with the auditor, on removable media, in a lab notebook). Checking the log
  against it later proves the first N records are still exactly what they were.

Communication / relationships
-----------------------------
Imports entitle/common.py (utc_now_iso, write_text_atomically), entitle/records.py (RecordStore
  methods head, entry_hash_at and verify_chain) and entitle/signing.py (sign_document,
  open_document, SignatureRejected). The RecordStore and keys are passed in. Imported by cli.py
  (checkpoint create and verify) and gui/tabs.py (Audit Report tab). Covered by
  tests/test_checkpoints.py.

Settings / parameters
---------------------
The payload is format entitle.checkpoint.v1 with store_name (the log's file name, for people;
  it is not checked), record_count, head_hash and created_at. The document kind is "checkpoint".
  verify_checkpoint returns {"valid", "reason", "record_count", "head_hash", "records_now",
  "signed_by", "created_at"}.

Edge cases
----------
create_checkpoint refuses a log whose chain is already broken (signing a damaged log would
  vouch for it) and an empty log is a valid checkpoint of zero records. verify_checkpoint
  reasons: ok; log_truncated (fewer records than the checkpoint); log_rewritten (record N no
  longer ends with the signed hash); chain_broken (the log does not verify up to record N); and,
  from the signature check, signature_invalid, unknown_signing_key, not_signed_document or
  payload_invalid. Records added after the checkpoint are expected and do not affect the result.

Known limitations
-----------------
A checkpoint protects only the records it covers; records written after it are protected by the
  next one. It proves the log has not changed, not that the records were true when written.

Examples
--------
From the directory containing run.py (with a key pair from entitle/signing.py):

    from entitle.checkpoints import create_checkpoint, verify_checkpoint
    from entitle.records import RecordStore

    store = RecordStore("records/entitle_records.log")
    create_checkpoint(store, signing_key, output="records/checkpoint-0001.entitle-checkpoint")
    result = verify_checkpoint(store, "records/checkpoint-0001.entitle-checkpoint", [public_key])
    assert result["valid"], result["reason"]
"""
from pathlib import Path

from .common import utc_now_iso, write_text_atomically
from .signing import SignatureRejected, open_document, sign_document

CHECKPOINT_FORMAT = "entitle.checkpoint.v1"
KIND = "checkpoint"
MAX_FILE_BYTES = 64 * 1024


def create_checkpoint(store, signing_key, *, output, overwrite=False):
    record_count, head_hash = store.head()
    payload = {
        "format": CHECKPOINT_FORMAT,
        "store_name": store.path.name,
        "record_count": record_count,
        "head_hash": head_hash,
        "created_at": utc_now_iso(),
    }
    write_text_atomically(output, sign_document(KIND, payload, signing_key), overwrite=overwrite)
    return payload


def verify_checkpoint(store, checkpoint_path, trusted_keys):
    path = Path(checkpoint_path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} is too large to be a checkpoint.")
    result = {"valid": False, "reason": None, "record_count": None, "head_hash": None, "records_now": None,
              "signed_by": None, "created_at": None}
    try:
        payload, key = open_document(path.read_bytes().decode("utf-8-sig", errors="replace"), KIND, trusted_keys)
    except SignatureRejected as rejected:
        return {**result, "reason": rejected.reason}
    count, head_hash = payload.get("record_count"), payload.get("head_hash")
    if payload.get("format") != CHECKPOINT_FORMAT or not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return {**result, "reason": "payload_invalid"}
    chain = store.verify_chain()
    result.update(record_count=count, head_hash=head_hash, records_now=chain.record_count, signed_by=key.key_id,
                  created_at=payload.get("created_at"))
    if chain.record_count < count:
        return {**result, "reason": "log_truncated"}
    if not chain.valid and chain.broken_index < count:
        return {**result, "reason": "chain_broken"}
    if count and store.entry_hash_at(count - 1) != head_hash:
        return {**result, "reason": "log_rewritten"}
    return {**result, "valid": True, "reason": "ok"}
