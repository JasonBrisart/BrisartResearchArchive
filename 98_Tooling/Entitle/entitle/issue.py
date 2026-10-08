"""
Entitle Issue Tool

Creates a protected offline entitlement container.

This module exposes:
    - ``issue_entitlement(...)`` — the plain function used by both the CLI below
      and the GUI. It builds an Entitle payload, protects it through BSR2, and
      saves the resulting container.
    - ``build_parser()`` / ``main(argv=None)`` — the CLI wrapper around it.

Example:
    python main.py issue \\
        --issuer JasonBrisart \\
        --subject ResearchLabA \\
        --product EntitleDemo \\
        --entitlement-id lab-a-demo-001 \\
        --master-key "change-this-master-key-change-this-master-key" \\
        --drbg-seed "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \\
        --drbg-personalization "EntitleDemoPersonalization" \\
        --output entitlements/lab_a.entitle
"""
import argparse
import datetime
import json

from .core import make_entitlement_payload
from .bsr_adapter import protect_entitlement_payload, save_protected_entitlement


def utc_now_iso():
    return datetime.datetime.now(
        datetime.timezone.utc
    ).replace(microsecond=0).isoformat()


def _encode(value):
    return value if isinstance(value, bytes) else value.encode("utf-8")


def build_rights(
    *,
    enterprise=False,
    modify=False,
    fork=False,
    export_source=False,
    redistribute=False,
    deployment_limit=1,
    support_tier="standard",
):
    return {
        "can_run": True,
        "can_use_enterprise_features": enterprise,
        "can_modify": modify,
        "can_fork": fork,
        "can_export_source": export_source,
        "can_redistribute": redistribute,
        "deployment_limit": deployment_limit,
        "support_tier": support_tier,
    }


def issue_entitlement(
    *,
    issuer,
    subject,
    product,
    entitlement_id,
    master_key,
    drbg_seed,
    drbg_personalization,
    output,
    expires=None,
    enterprise=False,
    modify=False,
    fork=False,
    export_source=False,
    redistribute=False,
    deployment_limit=1,
    support_tier="standard",
):
    """
    Build, protect, and save an Entitle entitlement container.

    This is the single source of truth for "issue an entitlement" — used directly
    by the CLI's ``main()`` below, and called directly by the GUI as well, so both
    surfaces stay in sync.

    Returns the plaintext payload dict (not the protected envelope).
    """
    payload = make_entitlement_payload(
        issuer_id=issuer,
        subject_id=subject,
        product_id=product,
        entitlement_id=entitlement_id,
        issued_at=utc_now_iso(),
        expires_at=expires,
        rights=build_rights(
            enterprise=enterprise,
            modify=modify,
            fork=fork,
            export_source=export_source,
            redistribute=redistribute,
            deployment_limit=deployment_limit,
            support_tier=support_tier,
        ),
        metadata={
            "created_by": "Entitle",
            "protection": "BrisartSecurityResearch envelope",
            "note": "Offline protected entitlement container.",
        },
    )
    envelope = protect_entitlement_payload(
        payload=payload,
        master_key=_encode(master_key),
        drbg_seed=_encode(drbg_seed),
        drbg_personalization=_encode(drbg_personalization),
    )
    save_protected_entitlement(envelope, output)
    return payload


def build_parser():
    parser = argparse.ArgumentParser(
        prog="issue",
        description="Create a protected Entitle entitlement container.",
    )
    parser.add_argument("--issuer", required=True, help="Issuer ID.")
    parser.add_argument("--subject", required=True, help="Customer/lab/organization ID.")
    parser.add_argument("--product", required=True, help="Product ID.")
    parser.add_argument("--entitlement-id", required=True, help="Entitlement ID.")
    parser.add_argument("--expires", default=None, help="Expiration ISO timestamp.")
    parser.add_argument("--output", required=True, help="Output .entitle path.")
    parser.add_argument(
        "--master-key",
        required=True,
        help="BSR master key text. Use strong local key material.",
    )
    parser.add_argument(
        "--drbg-seed",
        required=True,
        help="DRBG seed text. BSR requires sufficient seed material.",
    )
    parser.add_argument(
        "--drbg-personalization",
        required=True,
        help="DRBG personalization text.",
    )
    parser.add_argument("--enterprise", action="store_true", help="Grant enterprise feature rights.")
    parser.add_argument("--modify", action="store_true", help="Grant private modification rights.")
    parser.add_argument("--fork", action="store_true", help="Grant internal fork rights.")
    parser.add_argument("--export-source", action="store_true", help="Grant source export rights.")
    parser.add_argument("--redistribute", action="store_true", help="Grant redistribution rights.")
    parser.add_argument("--deployment-limit", type=int, default=1, help="Maximum authorized deployments.")
    parser.add_argument("--support-tier", default="standard", help="Support tier label.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = issue_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        entitlement_id=args.entitlement_id,
        master_key=args.master_key,
        drbg_seed=args.drbg_seed,
        drbg_personalization=args.drbg_personalization,
        output=args.output,
        expires=args.expires,
        enterprise=args.enterprise,
        modify=args.modify,
        fork=args.fork,
        export_source=args.export_source,
        redistribute=args.redistribute,
        deployment_limit=args.deployment_limit,
        support_tier=args.support_tier,
    )
    print("Protected entitlement created:")
    print(args.output)
    print()
    print("Payload summary:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0
