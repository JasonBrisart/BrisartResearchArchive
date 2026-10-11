"""
File: vault/core/time_tools.py

Purpose
-------
Timestamp helpers specific to vault record bookkeeping.

Public interface:
- stamp_new_record() -- Return ``{"created_at", "updated_at"}`` both set to the
  same instant.
- stamp_updated(existing_created_at) -- Return ``{"created_at", "updated_at"}``
  preserving the original creation time.
- is_chronologically_ordered(earlier, later) -- Report whether ``earlier``
  sorts at or before ``later``.

Design notes:

Wraps :mod:`common.timestamps` rather than duplicating its logic, but adds two
things ``common`` deliberately does not know about: comparing two
already-formatted ISO strings without re-parsing the whole vault on every sort,
and stamping a record with ``created_at``/``updated_at`` from a single captured
instant so the two fields can never straddle a second boundary.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.timestamps (common/timestamps.py)
Standard library: none.
Imported by:
- vault/store/vault_service.py
Covered by tests: vault/tests/test_record_ids_and_time.py.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- is_chronologically_ordered() compares text, not time, and is correct only for
  strings in the exact format common.timestamps.utc_now_iso produces. A "Z"
  suffix, a non-UTC offset, or fractional seconds can give wrong answers:
  2026-01-01T05:00:00+05:00 (which is 00:00 UTC) is reported as later than
  2026-01-01T01:00:00+00:00, and the same instant written with "Z" and with
  "+00:00" is ordered in one direction only.
- Equal timestamps return True in both directions, so two events in the same
  second cannot be told apart by order.
- Second resolution only; see common/timestamps.py.
- stamp_updated() does not validate existing_created_at (None is accepted and
  returned as-is) and does not compare it with the new time, so a clock set
  backwards can produce an updated_at earlier than created_at.

Examples
--------
Run from the repository root.

::

    from vault.core.time_tools import (
        is_chronologically_ordered,
        stamp_new_record,
        stamp_updated,
    )

    created = stamp_new_record()                 # created_at == updated_at
    updated = stamp_updated(created["created_at"])
    first = created["created_at"]
    print(is_chronologically_ordered(first, updated["updated_at"]))
"""

from common.timestamps import utc_now_iso


def stamp_new_record() -> dict:
    """Return ``{"created_at", "updated_at"}`` both set to the same instant.

    Two separate ``utc_now_iso()`` calls can straddle a second boundary and
    make a brand-new record's ``updated_at`` appear to be a moment after its
    own ``created_at`` -- capturing one timestamp and reusing it avoids that.
    """
    now = utc_now_iso()
    return {"created_at": now, "updated_at": now}


def stamp_updated(existing_created_at: str) -> dict:
    """Return ``{"created_at", "updated_at"}`` preserving the original creation time."""
    return {"created_at": existing_created_at, "updated_at": utc_now_iso()}


def is_chronologically_ordered(earlier: str, later: str) -> bool:
    """Report whether ``earlier`` sorts at or before ``later``.

    ISO 8601 timestamps in the format ``common.timestamps.utc_now_iso``
    produces are lexically sortable, so this is a plain string comparison --
    no parsing required, which matters when comparing many record timestamps
    during a listing sort.
    """
    return earlier <= later




