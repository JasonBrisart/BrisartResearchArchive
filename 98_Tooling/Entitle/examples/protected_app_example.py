"""
Protected App Example

This file demonstrates how another software project can use Entitle.

Behavior:
    - Base program can run.
    - Governed features require valid Entitle rights.
    - If the protected entitlement fails BSR verification, governed features remain locked.
    - No cloud activation.
    - No telemetry.
    - No online license server.

Run this from anywhere:
    python examples/protected_app_example.py
"""
import sys
from pathlib import Path

# Allow this script to be run directly (e.g. ``python examples/protected_app_example.py``)
# regardless of the current working directory, by putting the repository root on
# sys.path so ``entitle`` (and, via entitle.bootstrap, ``vendor/``) can be found.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from entitle.bootstrap import ensure_bsr_on_path
ensure_bsr_on_path()

from entitle.core import EntitlementDenied
from entitle.bsr_adapter import verify_protected_entitlement

ISSUER_ID = "JasonBrisart"
SUBJECT_ID = "ResearchLabA"
PRODUCT_ID = "EntitleDemo"
ENTITLEMENT_FILE = str(_REPO_ROOT / "entitlements" / "lab_a.entitle")

"""
For this demo, the master key is hardcoded.

For real internal deployments:
    - Store this in a local secure configuration area.
    - Keep issuer-side keys controlled.
    - Do not put sensitive master keys in public repositories.

Because BrisartSecurityResearch is experimental research software, this should be
treated as controlled-environment entitlement protection unless reviewed.
"""
MASTER_KEY = b"change-this-master-key-change-this-master-key"


def load_entitlement():
    return verify_protected_entitlement(
        path=ENTITLEMENT_FILE,
        master_key=MASTER_KEY,
        expected_product_id=PRODUCT_ID,
        issuer_id=ISSUER_ID,
        subject_id=SUBJECT_ID,
    )


def base_program():
    print("Base program started.")
    print("This area can remain available without governed rights.")


def enterprise_feature(entitlement):
    entitlement.require_right("can_use_enterprise_features")
    print("Enterprise feature unlocked.")
    print("Running governed enterprise workflow.")


def modify_feature(entitlement):
    entitlement.require_right("can_modify")
    print("Modification rights verified.")
    print("Opening private modification workflow.")


def fork_feature(entitlement):
    entitlement.require_right("can_fork")
    print("Fork rights verified.")
    print("Opening authorized internal fork workflow.")


def source_export_feature(entitlement):
    entitlement.require_right("can_export_source")
    print("Source export rights verified.")
    print("Preparing source export package.")


def redistribution_feature(entitlement):
    entitlement.require_right("can_redistribute")
    print("Redistribution rights verified.")
    print("Preparing redistribution package.")


def main():
    if not Path(ENTITLEMENT_FILE).exists():
        print(f"No entitlement file found at: {ENTITLEMENT_FILE}")
        print("Issue one first, for example:")
        print()
        print("  python main.py issue \\")
        print(f"      --issuer {ISSUER_ID} --subject {SUBJECT_ID} --product {PRODUCT_ID} \\")
        print("      --entitlement-id lab-a-demo-001 \\")
        print("      --master-key \"change-this-master-key-change-this-master-key\" \\")
        print("      --drbg-seed \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\" \\")
        print("      --drbg-personalization \"EntitleDemoPersonalization\" \\")
        print("      --modify --fork --deployment-limit 3 \\")
        print(f"      --output {ENTITLEMENT_FILE}")
        return

    entitlement = load_entitlement()
    print("Entitlement result:")
    print(entitlement.to_dict())
    print()

    base_program()
    print()

    if not entitlement.allowed:
        print("Entitlement verification failed.")
        print(f"Reason: {entitlement.reason}")
        print("Governed features remain locked.")
        return

    guarded_features = [
        ("Enterprise", enterprise_feature),
        ("Modification", modify_feature),
        ("Fork", fork_feature),
        ("Source Export", source_export_feature),
        ("Redistribution", redistribution_feature),
    ]
    for name, function in guarded_features:
        try:
            function(entitlement)
        except EntitlementDenied as exc:
            print(f"{name} locked: {exc}")


if __name__ == "__main__":
    main()
