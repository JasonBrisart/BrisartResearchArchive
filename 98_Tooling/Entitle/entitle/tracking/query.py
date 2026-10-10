"""
File: entitle/tracking/query.py

Purpose
-------
Entitle Tracking — Queries

Communication / relationships
-----------------------------
Direct module imports: ..records.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
Entitle Tracking — Queries

Read-only helpers for listing records from the shared record store.

This module contains no write logic; it exists so the CLI and GUI can list
records of a given type (or all records) without needing to know how the store
filters internally.
"""

from ..records import RecordStore


def list_records(*, store, record_type=None):
    record_store = RecordStore(store)
    return record_store.filter(record_type=record_type)

