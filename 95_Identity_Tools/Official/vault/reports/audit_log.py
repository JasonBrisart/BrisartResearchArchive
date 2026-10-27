"""
File: vault/reports/audit_log.py

Purpose
-------
Append-only audit trail for vault mutation and lifecycle events. Every time a
vault record is created, updated, deleted, or the vault itself is
unlocked/locked, this module writes one small, independent JSON file describing
that event.

Public interface:
- class AuditLogError(ValueError) -- Raised when an audit entry cannot be built
  or written.
- build_entry(action, record_id="", label="", kind="") -- Build an audit entry
  describing a single vault mutation or lifecycle event.
- write_entry(audit_dir, entry) -- Persist an audit entry to ``audit_dir``,
  returning the path written to.
- record_event(audit_dir, action, record_id="", label="", kind="") -- Build and
  immediately persist an audit entry. Convenience wrapper around
  :func:`build_entry` + :func:`write_entry`.
- list_entries(audit_dir, record_id=None) -- List audit entry file paths in
  ``audit_dir``, sorted oldest first.

Design notes:

The vault's primary store only ever holds the *current* state of each record
(an update overwrites the previous version), so this module exists to answer
"what happened, and when" -- a question the vault store itself cannot answer on
its own. Entries never contain sealed payload bytes, key material, or decrypted
field values -- only record id, label, kind, the action taken, and a timestamp.
This is deliberate: a lab reviewing the audit trail to see what changed and
when should never need to unlock the vault or handle any secret material to do
so.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.atomic_io (common/atomic_io.py)
- common.timestamps (common/timestamps.py)
Standard library: pathlib, secrets.
Imported by:
- vault/store/vault_service.py
Covered by tests: vault/tests/test_audit_log.py.

Settings / parameters
---------------------
- AUDIT_FORMAT = "brisart-identity-tools/vault-audit/v1"
- _SUFFIX_BYTES = 4
- _VALID_ACTIONS = ("created", "updated", "deleted", "unlocked", "locked")

Edge cases
----------
- build_entry() raises AuditLogError: "unsupported audit action {...}; expected
  one of {...}."
- write_entry() raises AuditLogError: "entry does not have the expected format
  marker."

Known limitations
-----------------
- "Append-only" describes what this module does, not what is enforced. It never
  edits or deletes an entry, but nothing stops another process or person from
  doing so, and entries are not hashed, chained, or signed.
- record_id is not validated here, and it becomes part of the file name.
  vault.core.ids.validate_record_id() rejects only empty ids, edge whitespace,
  ids over 128 characters, "|" and NUL, so an id such as "x/../../y" passes it.
  In a test, record_event() with that id wrote the entry outside the audit
  directory. Reject path separators in record ids before they reach this
  module.
- list_entries(record_id=...) matches the text "_<record_id>_" anywhere in a
  file name, so it can return the wrong entries: a filter of "created" also
  matched an entry whose action was "created" for a different record.
- Vault-level events (unlocked, locked) have no record id and are filed under
  the name "vault", so a real record whose id is "vault" cannot be
  distinguished from them by name.
- Only the action is validated. write_entry() checks the format marker only; a
  non-dict entry raises AttributeError and a missing key raises KeyError.
- Labels and kinds are stored in the clear, exactly as they are in the vault
  file itself, so they must not contain secrets.
- Ordering comes from the UTC stamp in the file name, so it is chronological
  only while the system clock moves forward.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path

    from vault.reports.audit_log import list_entries, record_event

    with tempfile.TemporaryDirectory() as folder:
        audit_dir = Path(folder) / "audit"
        record_event(audit_dir, "unlocked")              # a vault-level event
        record_event(audit_dir, "created", "rec-1", "Email", "credential")
        for path in list_entries(audit_dir, record_id="rec-1"):
            print(path.name)
"""

import secrets
from pathlib import Path

from common.atomic_io import atomic_write_json
from common.timestamps import microsecond_timestamp, utc_now_iso

AUDIT_FORMAT = "brisart-identity-tools/vault-audit/v1"
_SUFFIX_BYTES = 4
_VALID_ACTIONS = ("created", "updated", "deleted", "unlocked", "locked")


class AuditLogError(ValueError):
    """Raised when an audit entry cannot be built or written."""


def _entry_filename(action: str, record_id: str) -> str:
    timestamp = microsecond_timestamp()
    suffix = secrets.token_hex(_SUFFIX_BYTES)
    safe_record_id = record_id or "vault"
    return f"{timestamp}_{action}_{safe_record_id}_{suffix}.json"


def build_entry(action: str, record_id: str = "", label: str = "", kind: str = "") -> dict:
    """Build an audit entry describing a single vault mutation or lifecycle event.

    ``record_id``/``label``/``kind`` are left as empty strings for
    vault-level events like ``"unlocked"`` or ``"locked"`` that are not
    about one specific record.
    """
    if action not in _VALID_ACTIONS:
        raise AuditLogError(
            f"unsupported audit action {action!r}; expected one of {_VALID_ACTIONS}."
        )
    return {
        "format": AUDIT_FORMAT,
        "action": action,
        "record_id": record_id,
        "label": label,
        "kind": kind,
        "recorded_at": utc_now_iso(),
    }


def write_entry(audit_dir, entry: dict) -> Path:
    """Persist an audit entry to ``audit_dir``, returning the path written to."""
    if entry.get("format") != AUDIT_FORMAT:
        raise AuditLogError("entry does not have the expected format marker.")
    directory = Path(audit_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = _entry_filename(entry["action"], entry.get("record_id", ""))
    path = directory / filename
    atomic_write_json(path, entry)
    return path


def record_event(audit_dir, action: str, record_id: str = "", label: str = "", kind: str = "") -> Path:
    """Build and immediately persist an audit entry. Convenience wrapper
    around :func:`build_entry` + :func:`write_entry`."""
    entry = build_entry(action, record_id, label, kind)
    return write_entry(audit_dir, entry)


def list_entries(audit_dir, record_id: str = None) -> list:
    """List audit entry file paths in ``audit_dir``, sorted oldest first.

    If ``record_id`` is given, only entries whose filename contains that
    record id are returned.
    """
    directory = Path(audit_dir)
    if not directory.is_dir():
        return []
    paths = sorted(directory.glob("*.json"))
    if record_id is None:
        return paths
    return [path for path in paths if f"_{record_id}_" in path.name]




