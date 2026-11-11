"""
File: entitle/records.py

Purpose
-------
Own Entitle's tamper-evident record log: an append-only file where every line is one JSON
  record, each linked to the one before it by a SHA-256 hash chain, so an edit, deletion or
  reordering of an earlier record is detectable. Also owns the vocabulary of record types and
  the writer lock that keeps two writers from forking the chain.

Communication / relationships
-----------------------------
Imports the entitle package root (EntitleError, canonical_json, utc_now_iso) and, depending on
  the platform, fcntl (Linux, macOS) or msvcrt (Windows) for the writer lock. Imported by
  entitle/revoke.py (revocation and reinstatement types), entitle/tracking.py (deployment, fork
  and provenance types), entitle/report.py (RECORD_TYPE_DEPLOYMENT), cli.py (RecordStore,
  ALL_RECORD_TYPES) and gui/tabs.py (RecordStore). Uses no encryption, so the log works
  without 97_Encryption. Covered by tests/test_records.py.

Settings / parameters
---------------------
Each record carries format ("entitle.record.v1"), record_id, record_type, created_at,
  prev_hash, data and entry_hash; the hash covers every field except entry_hash itself. The
  first record chains to GENESIS_HASH (64 zeros). The five record types are deployment, fork,
  provenance, revocation and reinstatement; they are stored in every record, so they never
  change. The writer lock is an operating-system lock on a "<store>.lock" file beside the store;
  a waiting writer gives up after LOCK_TIMEOUT_SECONDS (5). read_all(strict=False) skips
  unreadable lines instead of raising.

Edge cases
----------
transaction() makes a read-then-append sequence atomic across threads and processes and can be
  nested, so tracking.register_deployment checks revocation, counts deployments and appends as
  one step. The operating system releases the lock when its holder exits, so a killed process
  never leaves the store locked and there is no stale-lock guesswork. The lock file stays beside
  the store between writes; deleting it while nobody is writing is harmless. A missing store
  reads as empty and its chain is valid. A line that is not a JSON object makes read_all and
  append raise RecordStoreError, while verify_chain reports it as chain status
  unparseable_record at that record's index, so tampering is reported rather than crashing the
  audit. Each append is flushed to disk before the lock is released. Parent folders are created
  on the first append.

Known limitations
-----------------
Detection only: the chain shows that earlier records changed, not who changed them, and
  someone who rewrites every record and every hash after the edit produces a valid chain.
  Every append re-reads the whole file to find the last hash, so very large logs get slower.
  The lock is advisory between copies of Entitle, is tested on a local Linux filesystem only,
  and network filesystems may not honor it. A crash in the middle of writing a line leaves a
  damaged last record, which then stops further appends until it is removed by hand.

Examples
--------
Usage from the directory containing main.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RECORD_TYPE_FORK, RecordStore

    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/records/entitle_records.log")
        first = store.append(RECORD_TYPE_FORK, {"fork_name": "lab-a"})
        second = store.append(RECORD_TYPE_FORK, {"fork_name": "lab-b"})
        assert second["prev_hash"] == first["entry_hash"]
        assert store.verify_chain().valid
        assert len(store.filter(record_type=RECORD_TYPE_FORK)) == 2
"""

import hashlib
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import EntitleError, canonical_json, utc_now_iso

if os.name == "nt":
    import msvcrt
else:
    import fcntl

RECORD_TYPE_DEPLOYMENT = "deployment"
RECORD_TYPE_FORK = "fork"
RECORD_TYPE_PROVENANCE = "provenance"
RECORD_TYPE_REVOCATION = "revocation"
RECORD_TYPE_REINSTATEMENT = "reinstatement"
ALL_RECORD_TYPES = (
    RECORD_TYPE_DEPLOYMENT,
    RECORD_TYPE_FORK,
    RECORD_TYPE_PROVENANCE,
    RECORD_TYPE_REVOCATION,
    RECORD_TYPE_REINSTATEMENT,
)

GENESIS_HASH = "0" * 64
RECORD_FORMAT = "entitle.record.v1"
LOCK_TIMEOUT_SECONDS = 5.0

_PROCESS_LOCK = threading.RLock()  # one writer thread per process at a time
_HELD = threading.local()  # .depth: resolved store path -> nesting depth, for this thread


class RecordStoreError(EntitleError):
    """Raised when the record file cannot be read as a record log."""


def _entry_hash(record):
    base = {key: value for key, value in record.items() if key != "entry_hash"}
    return hashlib.sha256(canonical_json(base)).hexdigest()


def _parse_record(line, index, name):
    try:
        record = json.loads(line)
    except ValueError:
        record = None
    if not isinstance(record, dict):
        raise RecordStoreError(f"{name}: record {index} is not a valid JSON object.")
    if not isinstance(record.get("data"), dict):
        raise RecordStoreError(f"{name}: record {index} has no data object.")
    return record


def _busy(lock_path):
    return TimeoutError(
        f"The record store is busy ({lock_path.name} is held by another Entitle writer). "
        "Try again in a moment."
    )


def _try_os_lock(handle):
    if os.name == "nt":
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _os_unlock(handle):
    try:
        if os.name == "nt":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


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
    def __init__(self, path):
        self.path = Path(path)

    def _lines(self):
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]

    def read_all(self, strict=True):
        records = []
        for index, line in enumerate(self._lines()):
            try:
                records.append(_parse_record(line, index, self.path.name))
            except RecordStoreError:
                if strict:
                    raise
        return records

    def last_hash(self):
        records = self.read_all()
        return records[-1].get("entry_hash", GENESIS_HASH) if records else GENESIS_HASH

    @contextmanager
    def transaction(self):
        key = str(self.path.resolve())
        depth = _HELD.__dict__.setdefault("depth", {})
        if key in depth:
            depth[key] += 1
            try:
                yield
            finally:
                depth[key] -= 1
            return
        lock_path = self.path.with_name(self.path.name + ".lock")
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        if not _PROCESS_LOCK.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            raise _busy(lock_path)
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, "a+b")
            while True:
                try:
                    _try_os_lock(handle)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        handle.close()
                        raise _busy(lock_path) from None
                    time.sleep(0.02)
            depth[key] = 1
            try:
                yield
            finally:
                del depth[key]
                _os_unlock(handle)
        finally:
            _PROCESS_LOCK.release()

    def append(self, record_type, data):
        with self.transaction():
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
                handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return record

    def filter(self, record_type=None, predicate=None):
        return [
            record
            for record in self.read_all()
            if (record_type is None or record.get("record_type") == record_type)
            and (predicate is None or predicate(record))
        ]

    def verify_chain(self):
        lines = self._lines()
        prev_hash = GENESIS_HASH
        for index, line in enumerate(lines):
            try:
                record = _parse_record(line, index, self.path.name)
            except RecordStoreError:
                return ChainStatus(False, index, "unparseable_record", len(lines))
            if record.get("prev_hash") != prev_hash:
                return ChainStatus(False, index, "prev_hash_mismatch", len(lines))
            if record.get("entry_hash") != _entry_hash(record):
                return ChainStatus(False, index, "entry_hash_mismatch", len(lines))
            prev_hash = record["entry_hash"]
        return ChainStatus(True, None, "ok", len(lines))
