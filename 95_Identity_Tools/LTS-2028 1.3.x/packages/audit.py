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
  describing a single package lifecycle event. Validates action and
  package_id; writes nothing.
- write_entry(audit_dir, entry) -- Persist an audit entry to ``audit_dir`` as a
  new file, returning the path written to.
- record_event(audit_dir, action, package_id, actor_label="") -- Build and
  immediately persist an audit entry. Returns the path written to.
- list_entries(audit_dir, package_id=None) -- List audit entry file paths in
  ``audit_dir``, sorted oldest first. Returns paths only; it does not read or
  parse the files.

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

One file per event. Nothing is ever read back and rewritten, so there is no
shared log file to corrupt, lock, or truncate. Each file is written through
common.atomic_io, so a reader sees either no file or the complete one, never a
half-written entry.

File names carry the ordering and the identity. A name has the form
``<UTC stamp>_<action>_<package_id>_<random>.json``, for example
``20261011_104730_317860Z_created_pkg-1_dc0bc131.json``. The stamp has
microsecond precision, and the random part (8 hex characters) means two events
in the same microsecond, or from two processes, cannot overwrite each other.
list_entries() orders and filters by name alone.

The caller chooses the directory. This module has no default location; the
directory is created, including parents, on the first write.

Each file holds five fields, written with sorted keys: format, action,
package_id, actor_label, and recorded_at (UTC, ISO-8601, to the second).

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
- AUDIT_FORMAT = "brisart-identity-tools/package-audit/v1" -- Stored in every
  entry as "format". write_entry() refuses an entry without this exact value.
- _SUFFIX_BYTES = 4 -- Random bytes in each file name, written as 8 hex
  characters.
- _VALID_ACTIONS = ("created", "recipient_added", "recipient_removed",
  "opened", "open_denied", "custody_violation_detected") -- The only actions
  build_entry() accepts. They are also embedded in file names, so a new action
  changes what list_entries() can match (see Known limitations).
- build_entry(actor_label="") -- Optional free-text label for who performed the
  action; stored as given.
- list_entries(package_id=None) -- None lists every entry in the directory.

Edge cases
----------
- build_entry() raises PackageAuditError: "unsupported audit action {...};
  expected one of {...}."
- build_entry() raises PackageAuditError: "package_id must be a non-empty
  string."
- write_entry() raises PackageAuditError: "entry does not have the expected
  format marker."
- write_entry() checks only that format marker. It does not check that action
  is one of the valid actions, so an entry built by hand with any action is
  written. An entry that is not a dict raises AttributeError, and one missing
  "action" or "package_id" raises KeyError.
- A failed write raises common.atomic_io.AtomicWriteError; creating the
  directory can raise OSError, which is not translated.
- list_entries() returns an empty list, not an error, when the directory does
  not exist. It ignores everything that is not a .json file directly inside
  the directory, including files in subfolders.
- record_event() raises whatever build_entry() or write_entry() raises, and
  writes nothing if validation fails.

Known limitations
-----------------
- "Append-only" describes what this module does, not what is enforced. It
  never edits or deletes an entry, but nothing stops another process or person
  from doing so, and entries are not hashed, chained, or signed. A deleted or
  altered file leaves no trace. Pair it with packages.custody and the
  Integrity Ledger if tamper-evidence matters.
- package_id is checked only for being a non-empty string, and it becomes part
  of the file name. An id containing a path separator creates a nested folder
  inside the audit directory; an id such as "x/../../y" writes one level above
  it and leaves an empty folder behind. Callers must pass safe ids. The error
  list documented for packages/package.py shows no further check on the id.
- list_entries(package_id=...) matches the text "_<package_id>_" anywhere in a
  file name, so it can return the wrong entries. Id "pkg" also returns entries
  for "pkg_1" and "pkg_2", and an id that equals an action fragment, such as
  "added", matches that action's entries. Treat the filtered list as a
  candidate list, or use ids that cannot appear inside another id or action.
- Ordering comes from the file name's UTC stamp. It is chronological only while
  the system clock moves forward; a clock change can put entries out of order.
  Two events within the same microsecond are ordered by the random suffix, not
  by the order they happened.
- actor_label is whatever the caller passes. It is not validated, may be any
  type, and is not authenticated, so it records a claim, not an identity.
- Entries are plain JSON. No file mode is requested, so permissions come from
  the process umask, and anyone who can read the directory can read the package
  ids and actor labels in it.
- list_entries() returns paths and does not validate the files. Reading,
  parsing, and interpreting entries is left to the caller.

Examples
--------
Run from the repository root.

::

    from pathlib import Path

    from packages.audit import (
        build_entry,
        list_entries,
        record_event,
        write_entry,
    )

    audit_dir = Path("package_audit")

    # Build and write in one call.
    path = record_event(audit_dir, "created", "pkg-1", "Alice")

    # Or build first, then write, for example to inspect the entry.
    entry = build_entry("opened", "pkg-1", "Bob")
    write_entry(audit_dir, entry)

    # Oldest first. Use ids that cannot appear inside another id.
    for entry_path in list_entries(audit_dir, package_id="pkg-1"):
        print(entry_path.name)
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




