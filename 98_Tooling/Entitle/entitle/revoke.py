"""
File: entitle/revoke.py

Purpose
-------
Record and answer offline revocation. A revocation or reinstatement is an ordinary entry in the
  tamper-evident record log, so it cannot be silently removed or reordered, and an
  entitlement's whole history stays readable after it is reinstated. Deployments through
  entitle/tracking.py are refused while an entitlement is revoked.

Communication / relationships
-----------------------------
Imports entitle/common.py (require_text) and entitle/records.py (RECORD_TYPE_REVOCATION,
  RECORD_TYPE_REINSTATEMENT); the RecordStore is passed in by the caller. Imported by
  entitle/tracking.py (is_revoked), cli.py (revoke revoke, reinstate and check) and gui/tabs.py
  (Revoke / Reinstate tab). Covered by tests/test_revoke.py.

Settings / parameters
---------------------
revoke(store, entitlement_id, issuer_id=None, product_id=None, reason=None) and reinstate(...)
  append one record whose data holds those four fields and return it. is_revoked(store,
  entitlement_id) returns a bool. revocation_status(store, entitlement_id) returns
  {"entitlement_id", "revoked", "last_record"}, where last_record is the latest revocation or
  reinstatement for that ID, or None.

Edge cases
----------
The latest revocation or reinstatement for an ID decides, so revoke, reinstate, revoke leaves it
  revoked. Status is per entitlement_id: revoking one never affects another, and issuer_id and
  product_id are recorded for the audit but not used to match. Revoking an ID that was never
  issued, or revoking twice, is accepted and recorded; nothing checks that the entitlement
  exists. A blank entitlement_id raises ValueError before anything is written, because a record
  can never be removed. A damaged record log raises RecordStoreError rather than guessing a
  status.

Known limitations
-----------------
Revocation is advisory and offline: it stops deployments recorded through Entitle, but not a
  copy of the software that never consults the record log, and not an entitlement file already
  on a machine without that log. verify does not check revocation. An ID is matched exactly as
  typed, so a revocation recorded for " lab-1" or "Lab-1" does not revoke "lab-1".

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RecordStore
    from entitle.revoke import is_revoked, reinstate, revoke

    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/entitle_records.log")
        revoke(store, "lab-a-001", reason="key compromise")
        assert is_revoked(store, "lab-a-001")
        reinstate(store, "lab-a-001", reason="cleared")
        assert not is_revoked(store, "lab-a-001")
"""

from .common import require_text
from .records import RECORD_TYPE_REINSTATEMENT, RECORD_TYPE_REVOCATION


def revocation_status(store, entitlement_id):
    revoked = False
    last_record = None
    for record in store.read_all():
        record_type = record.get("record_type")
        if record_type not in (RECORD_TYPE_REVOCATION, RECORD_TYPE_REINSTATEMENT):
            continue
        if record["data"].get("entitlement_id") != entitlement_id:
            continue
        revoked = record_type == RECORD_TYPE_REVOCATION
        last_record = record
    return {"entitlement_id": entitlement_id, "revoked": revoked, "last_record": last_record}


def is_revoked(store, entitlement_id):
    return revocation_status(store, entitlement_id)["revoked"]


def _append(store, record_type, entitlement_id, issuer_id, product_id, reason):
    require_text(entitlement_id=entitlement_id)
    return store.append(
        record_type,
        {
            "entitlement_id": entitlement_id,
            "issuer_id": issuer_id,
            "product_id": product_id,
            "reason": reason,
        },
    )


def revoke(store, entitlement_id, issuer_id=None, product_id=None, reason=None):
    return _append(store, RECORD_TYPE_REVOCATION, entitlement_id, issuer_id, product_id, reason)


def reinstate(store, entitlement_id, issuer_id=None, product_id=None, reason=None):
    return _append(store, RECORD_TYPE_REINSTATEMENT, entitlement_id, issuer_id, product_id, reason)
