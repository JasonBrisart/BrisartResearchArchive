"""
Entitle Revoke

Offline revocation for Entitle entitlements.

Revocation is recorded as an append-only, tamper-evident entry in the same local
record store used by deployment/fork/provenance tracking. Because the store is
hash-chained, a revocation cannot be silently removed or reordered without
breaking the chain.

An entitlement is considered revoked if the store contains a "revocation" record
for its entitlement_id that is not followed by a later "reinstatement" record for
the same entitlement_id. This lets you both revoke and, if needed, reinstate,
while preserving the full history.

Example:
    python main.py revoke revoke --entitlement-id lab-a-demo-001 \\
        --issuer JasonBrisart --product EntitleDemo --reason "key compromise" \\
        --store records/entitle_records.log
"""
import argparse
import json

from .record_types import RECORD_TYPE_REINSTATEMENT, RECORD_TYPE_REVOCATION
from .records import RecordStore


def revocation_status(store, entitlement_id):
    """
    Return the effective revocation status for an entitlement_id.

    Walks the record log in order. The most recent revocation or reinstatement
    record for this entitlement_id wins.
    """
    revoked = False
    last_record = None
    for record in store.read_all():
        record_type = record.get("record_type")
        if record_type not in (RECORD_TYPE_REVOCATION, RECORD_TYPE_REINSTATEMENT):
            continue
        if record.get("data", {}).get("entitlement_id") != entitlement_id:
            continue
        revoked = record_type == RECORD_TYPE_REVOCATION
        last_record = record
    return {
        "entitlement_id": entitlement_id,
        "revoked": revoked,
        "last_record": last_record,
    }


def is_revoked(store, entitlement_id):
    return revocation_status(store, entitlement_id)["revoked"]


def revoke(store, entitlement_id, issuer_id=None, product_id=None, reason=None):
    return store.append(
        RECORD_TYPE_REVOCATION,
        {
            "entitlement_id": entitlement_id,
            "issuer_id": issuer_id,
            "product_id": product_id,
            "reason": reason,
        },
    )


def reinstate(store, entitlement_id, issuer_id=None, product_id=None, reason=None):
    return store.append(
        RECORD_TYPE_REINSTATEMENT,
        {
            "entitlement_id": entitlement_id,
            "issuer_id": issuer_id,
            "product_id": product_id,
            "reason": reason,
        },
    )


def _cmd_revoke(args):
    store = RecordStore(args.store)
    record = revoke(
        store,
        entitlement_id=args.entitlement_id,
        issuer_id=args.issuer,
        product_id=args.product,
        reason=args.reason,
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))


def _cmd_reinstate(args):
    store = RecordStore(args.store)
    record = reinstate(
        store,
        entitlement_id=args.entitlement_id,
        issuer_id=args.issuer,
        product_id=args.product,
        reason=args.reason,
    )
    print(json.dumps(record, indent=2, ensure_ascii=False))


def _cmd_check(args):
    store = RecordStore(args.store)
    status = revocation_status(store, args.entitlement_id)
    print(json.dumps(status, indent=2, ensure_ascii=False))
    print()
    print("REVOKED" if status["revoked"] else "ACTIVE")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="revoke",
        description="Revoke, reinstate, or check Entitle entitlements offline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    rev = subparsers.add_parser("revoke", help="Record a revocation.")
    rev.add_argument("--entitlement-id", required=True)
    rev.add_argument("--issuer", default=None)
    rev.add_argument("--product", default=None)
    rev.add_argument("--reason", default=None)
    rev.add_argument("--store", required=True, help="Record store file path.")
    rev.set_defaults(func=_cmd_revoke)

    rei = subparsers.add_parser("reinstate", help="Record a reinstatement.")
    rei.add_argument("--entitlement-id", required=True)
    rei.add_argument("--issuer", default=None)
    rei.add_argument("--product", default=None)
    rei.add_argument("--reason", default=None)
    rei.add_argument("--store", required=True, help="Record store file path.")
    rei.set_defaults(func=_cmd_reinstate)

    chk = subparsers.add_parser("check", help="Check revocation status.")
    chk.add_argument("--entitlement-id", required=True)
    chk.add_argument("--store", required=True, help="Record store file path.")
    chk.set_defaults(func=_cmd_check)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
