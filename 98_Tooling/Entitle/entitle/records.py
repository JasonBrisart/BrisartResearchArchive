"""
Entitle Records

Append-only, tamper-evident local record log for Entitle.

This module is the shared record store used by Entitle's deployment tracking,
fork management, provenance records, and audit reporting.

Design goals:
    - Local-first: records live in a plain file you control.
    - Offline: no network, no services, no telemetry.
    - Auditable: every entry is human-readable JSON on its own line.
    - Tamper-evident: entries are linked in a SHA-256 hash chain, so any edit,
      deletion, or reordering of earlier records can be detected.

The store is intentionally append-only. Records are never rewritten in place;
corrections are made by appending new records.

Record schema versioning:
    Each record carries an explicit ``format`` marker (``entitle.record.v1``).
    The entitlement *payload* already carried its own format marker; from 0.4.0
    the *record* entries do too, so the on-disk record schema can be evolved in
    the future while still recognizing existing logs. The marker is part of the
    hashed region of each record, so it is covered by the tamper-evident chain
    like every other field.
"""
import datetime
import hashlib
import json
import uuid
from pathlib import Path

from .core import canonical_json

GENESIS_HASH = "0" * 64
RECORD_FORMAT = "entitle.record.v1"


def utc_now_iso():
    return datetime.datetime.now(
        datetime.timezone.utc
    ).replace(microsecond=0).isoformat()


def _entry_hash(record):
    """
    Compute the SHA-256 hash of a record over every field except the
    entry_hash itself. The record's prev_hash field is included, which is
    what chains each entry to the one before it.
    """
    base = {key: value for key, value in record.items() if key != "entry_hash"}
    return hashlib.sha256(canonical_json(base)).hexdigest()


class ChainStatus:
    def __init__(self, valid, broken_index, reason, record_count):
        self.valid = valid
        self.broken_index = broken_index
        self.reason = reason
        self.record_count = record_count

    def to_dict(self):
        return {
            "valid": self.valid,
            "broken_index": self.broken_index,
            "reason": self.reason,
            "record_count": self.record_count,
        }


class RecordStore:
    """
    Append-only, hash-chained record log backed by a single local file.
    Each line is one JSON record.
    """

    def __init__(self, path):
        self.path = Path(path)

    def read_all(self):
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records

    def last_hash(self):
        records = self.read_all()
        if not records:
            return GENESIS_HASH
        return records[-1].get("entry_hash", GENESIS_HASH)

    def append(self, record_type, data):
        record = {
            "format": RECORD_FORMAT,
            "record_id": uuid.uuid4().hex,
            "record_type": record_type,
            "created_at": utc_now_iso(),
            "prev_hash": self.last_hash(),
            "data": data or {},
        }
        record["entry_hash"] = _entry_hash(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
            handle.write("\n")
        return record

    def filter(self, record_type=None, predicate=None):
        results = []
        for record in self.read_all():
            if record_type is not None and record.get("record_type") != record_type:
                continue
            if predicate is not None and not predicate(record):
                continue
            results.append(record)
        return results

    def verify_chain(self):
        prev_hash = GENESIS_HASH
        records = self.read_all()
        for index, record in enumerate(records):
            if record.get("prev_hash") != prev_hash:
                return ChainStatus(False, index, "prev_hash_mismatch", len(records))
            if record.get("entry_hash") != _entry_hash(record):
                return ChainStatus(False, index, "entry_hash_mismatch", len(records))
            prev_hash = record["entry_hash"]
        return ChainStatus(True, None, "ok", len(records))
