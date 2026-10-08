"""
Entitle Tracking — Provenance

Records provenance and ownership entries in the shared tamper-evident record
store.

A provenance record documents where software originated and how it has evolved:
origin, version, previous version, and current custodian. Like fork records, it
is documentary and written unconditionally; it does not consult an entitlement or
the revocation history.
"""
from ..record_types import RECORD_TYPE_PROVENANCE
from ..records import RecordStore


def record_provenance(*, store, product, origin, version, custodian, previous_version=None, notes=None):
    record_store = RecordStore(store)
    return record_store.append(
        RECORD_TYPE_PROVENANCE,
        {
            "product_id": product,
            "origin": origin,
            "version": version,
            "previous_version": previous_version,
            "custodian": custodian,
            "notes": notes,
        },
    )
