"""
File: common/timestamps.py

Purpose
-------
UTC timestamp helpers, the single canonical copy.

Public interface:
- utc_now() -- Current UTC time as ISO-8601 to the second (e.g.
  2026-08-23T14:25:30+00:00).
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
- No known limitations beyond the documented contract of its public interface.

Examples
--------
::

    from common.timestamps import (
        utc_now,
        filename_timestamp,
        microsecond_timestamp,
    )
    result = utc_now()
    filename_timestamp()
    microsecond_timestamp()
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




