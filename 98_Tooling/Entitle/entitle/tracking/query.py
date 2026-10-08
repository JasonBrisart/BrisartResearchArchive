"""
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
