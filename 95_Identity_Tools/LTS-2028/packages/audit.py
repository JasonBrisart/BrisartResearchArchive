"""
File: packages/audit.py

Purpose
-------
External, append-only audit trail for Identity-Bound Package events. Every
package lifecycle event (created, a recipient added or removed, opened, an open
denied, a custody violation detected) writes one small, independent JSON file
describing that event, into a directory separate from the package file itself.

Public interface:
- class PackageAuditError(ValueError) -- Raised when a package audit entry
  cannot be built or written.
- build_entry(action, package_id, actor_label="") -- Build an audit entry
  describing a single package lifecycle event.
- write_entry(audit_dir, entry) -- Persist an audit entry to ``audit_dir``,
  returning the path written to.
- record_event(audit_dir, action, package_id, actor_label="") -- Build and
  immediately persist an audit entry.
- list_entries(audit_dir, package_id=None) -- List audit entry file paths in
  ``audit_dir``, sorted oldest first.

Design notes:

This is what distinguishes it from packages.custody's hash chain, which travels
*inside* the package's own state: losing the package file, or never having had
access to it, still leaves this external trail intact. The two are
complementary, not redundant -- custody proves the package's own history was
not edited after the fact; this module proves an event happened at all,
independent of the package surviving. Entries never contain content keys,
master keys, or sealed payload bytes -- only package id, action, and actor
label. An audit review of "who touched this package, and when" never requires
unwrapping a content key or opening the package to do so.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.atomic_io (common/atomic_io.py)
- common.timestamps (common/timestamps.py)
Standard library: pathlib, secrets.
Imported by:
- packages/package.py
Covered by tests: packages/tests/test_package_audit.py.

Settings / parameters
---------------------
- AUDIT_FORMAT = "brisart-identity-tools/package-audit/v1"
- _SUFFIX_BYTES = 4
- _VALID_ACTIONS = tuple of 6 entries

Edge cases
----------
- build_entry() raises PackageAuditError: "unsupported audit action {...};
  expected one of {...}."
- build_entry() raises PackageAuditError: "package_id must be a non-empty
  string."
- write_entry() raises PackageAuditError: "entry does not have the expected
  format marker."

Known limitations
-----------------
- No known limitations beyond the documented contract of its public interface.

Examples
--------
::

    from packages.audit import build_entry, write_entry, record_event
    result = build_entry(action, package_id)
    write_entry(audit_dir, entry)
    record_event(audit_dir, action, package_id)
"""

import secrets
from pathlib import Path

from common.atomic_io import atomic_write_json
from common.timestamps import microsecond_timestamp, utc_now_iso

AUDIT_FORMAT = "brisart-identity-tools/package-audit/v1"
_SUFFIX_BYTES = 4
_VALID_ACTIONS = (
    "created",
    "recipient_added",
    "recipient_removed",
    "opened",
    "open_denied",
    "custody_violation_detected",
)


class PackageAuditError(ValueError):
    """Raised when a package audit entry cannot be built or written."""


def _entry_filename(action: str, package_id: str) -> str:
    timestamp = microsecond_timestamp()
    suffix = secrets.token_hex(_SUFFIX_BYTES)
    return f"{timestamp}_{action}_{package_id}_{suffix}.json"


def build_entry(action: str, package_id: str, actor_label: str = "") -> dict:
    """Build an audit entry describing a single package lifecycle event."""
    if action not in _VALID_ACTIONS:
        raise PackageAuditError(
            f"unsupported audit action {action!r}; expected one of {_VALID_ACTIONS}."
        )
    if not isinstance(package_id, str) or not package_id:
        raise PackageAuditError("package_id must be a non-empty string.")
    return {
        "format": AUDIT_FORMAT,
        "action": action,
        "package_id": package_id,
        "actor_label": actor_label,
        "recorded_at": utc_now_iso(),
    }


def write_entry(audit_dir, entry: dict) -> Path:
    """Persist an audit entry to ``audit_dir``, returning the path written to."""
    if entry.get("format") != AUDIT_FORMAT:
        raise PackageAuditError("entry does not have the expected format marker.")
    directory = Path(audit_dir)
    directory.mkdir(parents=True, exist_ok=True)
    filename = _entry_filename(entry["action"], entry["package_id"])
    path = directory / filename
    atomic_write_json(path, entry)
    return path


def record_event(audit_dir, action: str, package_id: str, actor_label: str = "") -> Path:
    """Build and immediately persist an audit entry."""
    entry = build_entry(action, package_id, actor_label)
    return write_entry(audit_dir, entry)


def list_entries(audit_dir, package_id: str = None) -> list:
    """List audit entry file paths in ``audit_dir``, sorted oldest first."""
    directory = Path(audit_dir)
    if not directory.is_dir():
        return []
    paths = sorted(directory.glob("*.json"))
    if package_id is None:
        return paths
    return [path for path in paths if f"_{package_id}_" in path.name]




