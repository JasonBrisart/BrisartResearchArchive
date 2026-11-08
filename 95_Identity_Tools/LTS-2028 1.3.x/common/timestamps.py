"""
File: common/timestamps.py

Purpose
-------
UTC timestamp helpers, the single canonical copy.

Public interface:
- utc_now() -- Current UTC time as ISO-8601 to the second (e.g.
  2026-08-23T14:25:30+00:00).
- utc_now_iso -- Alias of utc_now (the same function object).
- filename_timestamp() -- Filename-safe UTC stamp to the second, e.g.
  20260823_142530Z.
- microsecond_timestamp() -- Filename-safe UTC stamp with microseconds, e.g.
  20260823_142530_004821Z.

Design notes:

Three formats were previously redefined across three files; all three are kept
here because they serve different needs:
- utc_now ISO-8601 to the second. Was in vault time_tools and LabID
  identity_record.
- filename_timestamp filename-safe stamp to the second. Was vault utc_stamp.
- microsecond_timestamp filename-safe stamp with microseconds. Was LabID
  report_timestamp; the extra precision stops two reports written in the same
  second from colliding on filename.

All timezone-aware UTC. The old naive-local helper is intentionally dropped.

``utc_now_iso`` is an alias of ``utc_now``: every consumer in this repository
(vault, biometrics, and packages timestamp call sites) imports ``utc_now_iso``,
so both names are kept -- ``utc_now`` for any external dependant,
``utc_now_iso`` because it is what every actual call site here uses.

Communication / relationships
-----------------------------
Standard library: datetime.
Imported by:
- biometrics/identity/identity_store.py
- biometrics/reports/report_writer.py
- packages/audit.py
- packages/custody.py
- vault/core/time_tools.py
- vault/reports/audit_log.py
Covered by tests: common/tests/test_common_utils.py.

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
- Every function reads the system clock. There is no monotonic guarantee, so a
  clock set backwards can make later stamps sort earlier.
- utc_now() has one-second resolution, so two events in the same second get
  identical stamps (vault.core.time_tools captures one value for that reason).
- microsecond_timestamp() is not guaranteed unique: two calls inside one clock
  tick return the same value. Callers that need unique names add their own
  suffix, as packages/audit.py and vault/reports/audit_log.py do with random
  hex.
- The formats sort correctly only against their own kind. utc_now() output
  ("2026-08-23T14:25:30+00:00") and the filename stamps ("20260823_142530Z")
  are different formats and must not be compared with each other.
- utc_now_iso is the same function object as utc_now, kept as an alias for
  import compatibility (see docs/CHANGELOG.md 1.0.0 'Fixed'), not a separate
  implementation.
- UTC only. There is deliberately no local-time helper, so any display in local
  time is the caller's job.

Examples
--------
Run from the repository root.

::

    from common.timestamps import (
        filename_timestamp,
        microsecond_timestamp,
        utc_now,
    )

    print(utc_now())                # 2026-08-23T14:25:30+00:00, to the second
    print(filename_timestamp())     # 20260823_142530Z
    print(microsecond_timestamp())  # 20260823_142530_004821Z
"""

import datetime as _dt


def utc_now() -> str:
    """Current UTC time as ISO-8601 to the second (e.g. 2026-08-23T14:25:30+00:00)."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


utc_now_iso = utc_now


def filename_timestamp() -> str:
    """Filename-safe UTC stamp to the second, e.g. 20260823_142530Z."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d_%H%M%SZ")


def microsecond_timestamp() -> str:
    """Filename-safe UTC stamp with microseconds, e.g. 20260823_142530_004821Z."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")




