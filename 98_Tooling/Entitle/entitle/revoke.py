"""
File: entitle/revoke.py

Purpose
-------
Record and answer offline revocation in the record log. A revocation or reinstatement is an
  ordinary entry in the tamper-evident log, so it cannot be silently removed or reordered and an
  entitlement's whole history stays readable after it is reinstated. Deployments through
  entitle/tracking.py are refused while an entitlement is revoked, verification can consult the
  log, and entitle/revocation_list.py publishes what is revoked as a signed list for machines
  that never see the log.

Communication / relationships
-----------------------------
Imports entitle/common.py (require_identifier) and entitle/records.py (RECORD_TYPE_REVOCATION,
  RECORD_TYPE_REINSTATEMENT); the RecordStore is passed in. Imported by entitle/tracking.py
  (is_revoked), entitle/entitlements.py (is_revoked), entitle/revocation_list.py
  (revoked_entitlements, revocation_record_count), cli.py and gui/tabs.py. Covered by
  tests/test_revoke.py.

Settings / parameters
---------------------
revoke(store, entitlement_id, issuer_id=None, product_id=None, reason=None) and reinstate(...)
  append one record holding those four fields and return it. is_revoked(store, entitlement_id)
  returns a bool. revocation_status(store, entitlement_id) returns {"entitlement_id", "revoked",
  "last_record"}. revoked_entitlements(store, issuer_id=None) returns {entitlement_id: latest
  revocation record} for every ID currently revoked (with issuer_id, those recorded for that
  issuer or for none). revocation_record_count(store) counts revocations and reinstatements.

Edge cases
----------
The latest revocation or reinstatement for an ID decides, so revoke, reinstate, revoke leaves it
  revoked. Status is per entitlement_id; issuer_id and product_id are recorded for the audit and
  used only to filter a published list. Revoking an ID that was never issued, or twice, is
  recorded; nothing checks the entitlement exists. An ID that is blank, has spaces at either end
  or holds control characters raises ValueError before anything is written. A damaged log raises
  RecordStoreError rather than guessing a status.

Known limitations
-----------------
Revocation is offline: it reaches a program only through the log or a published list, and a
  copy of the software given neither never learns of it. IDs are matched exactly, so "Lab-1" and
  "lab-1" differ; IDs written with surrounding spaces before 0.7.0 still match only as written.

Examples
--------
From the directory containing run.py:

    from tempfile import TemporaryDirectory
    from entitle.records import RecordStore
    from entitle.revoke import is_revoked, reinstate, revoke, revoked_entitlements

    with TemporaryDirectory() as folder:
        store = RecordStore(f"{folder}/entitle_records.log")
        revoke(store, "lab-a-001", reason="key compromise")
        assert is_revoked(store, "lab-a-001") and set(revoked_entitlements(store)) == {"lab-a-001"}
        reinstate(store, "lab-a-001", reason="cleared")
        assert not is_revoked(store, "lab-a-001")
"""

from .common import require_identifier
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


def revoked_entitlements(store, issuer_id=None):
    """Every entitlement ID whose latest revocation record is a revocation, with that record.

    With issuer_id, only revocations recorded for that issuer or for no issuer are included.
    """
    latest = {}
    for record in store.read_all():
        if record.get("record_type") not in (RECORD_TYPE_REVOCATION, RECORD_TYPE_REINSTATEMENT):
            continue
        entitlement_id = record["data"].get("entitlement_id")
        if isinstance(entitlement_id, str):
            latest[entitlement_id] = record
    return {
        entitlement_id: record
        for entitlement_id, record in latest.items()
        if record["record_type"] == RECORD_TYPE_REVOCATION
        and (issuer_id is None or record["data"].get("issuer_id") in (None, issuer_id))
    }


def revocation_record_count(store):
    """How many revocation and reinstatement records the log holds; it only ever grows."""
    return len([r for r in store.read_all() if r.get("record_type") in (RECORD_TYPE_REVOCATION, RECORD_TYPE_REINSTATEMENT)])


def _append(store, record_type, entitlement_id, issuer_id, product_id, reason):
    require_identifier(entitlement_id=entitlement_id)
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
