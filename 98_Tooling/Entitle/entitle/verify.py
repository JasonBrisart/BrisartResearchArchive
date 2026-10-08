"""
Entitle Verify Tool

Verifies a protected Entitle entitlement container.

Example:
    python main.py verify \\
        --issuer JasonBrisart \\
        --subject ResearchLabA \\
        --product EntitleDemo \\
        --master-key "change-this-master-key-change-this-master-key" \\
        --file entitlements/lab_a.entitle
"""
import argparse
import json

from .bsr_adapter import verify_protected_entitlement


def _encode(value):
    return value if isinstance(value, bytes) else value.encode("utf-8")


def verify_entitlement(*, issuer, subject, product, master_key, file):
    """
    Verify a protected entitlement container.

    Single source of truth for "verify an entitlement" — used by both the CLI
    below and the GUI.

    Returns an EntitlementResult.
    """
    return verify_protected_entitlement(
        path=file,
        master_key=_encode(master_key),
        expected_product_id=product,
        issuer_id=issuer,
        subject_id=subject,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="verify",
        description="Verify a protected Entitle entitlement container.",
    )
    parser.add_argument("--issuer", required=True, help="Expected issuer ID.")
    parser.add_argument("--subject", required=True, help="Expected subject/customer/lab ID.")
    parser.add_argument("--product", required=True, help="Expected product ID.")
    parser.add_argument("--master-key", required=True, help="BSR master key text.")
    parser.add_argument("--file", required=True, help="Protected .entitle file.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    result = verify_entitlement(
        issuer=args.issuer,
        subject=args.subject,
        product=args.product,
        master_key=args.master_key,
        file=args.file,
    )
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    if result.allowed:
        print()
        print("VERIFIED: entitlement is valid.")
        return 0
    print()
    print(f"DENIED: {result.reason}")
    return 1
