"""
File: examples/protected_app_example.py

Purpose
-------
Show how another program guards its features with Entitle: the base program always runs, and
  each governed feature (enterprise, modify, fork, source export, redistribution) runs only when
  a verified entitlement grants the matching right. Anything short of a verified entitlement
  leaves every governed feature locked. There is no activation server, telemetry or network use.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError), entitle/rights.py (EntitlementDenied) and
  entitle/entitlements.py (verify_entitlement): the whole interface a protected program needs.
  Puts the Entitle folder on sys.path so it runs from any working folder. Nothing imports it;
  tests/test_example.py loads it by path and runs main().

Settings / parameters
---------------------
ISSUER_ID (JasonBrisart), SUBJECT_ID (ResearchLabA), PRODUCT_ID (EntitleDemo) and MASTER_KEY
  must match the entitlement being checked; they match the issue command in docs/README.md.
  ENTITLEMENT_FILE defaults to entitlements/lab_a.entitle in the Entitle folder, and
  main(entitlement_file) takes another path. MASTER_KEY is a demo value written into the source.

Edge cases
----------
With no entitlement file it prints the issue command that would create one and returns. A file
  that is denied (wrong key, wrong product, expired) keeps every governed feature locked and
  prints the reason. A check that cannot run at all is treated the same way: 97_Encryption not
  found, a file that is not an entitlement (damaged, empty, UTF-16, or too large) or one that
  cannot be read. The base program still starts, the reason is printed, and nothing governed
  unlocks. A verified entitlement unlocks only the features whose rights it grants; the rest
  print "locked" with the missing right.

Known limitations
-----------------
Never put a real master key in source: keep it in controlled local configuration, outside
  public repositories. The program checks the entitlement once at start; it does not consult
  the record log, so it does not see revocations. BSR2 (97_Encryption) is experimental research
  cryptography, so treat this as protection for controlled environments. Like the rest of
  Entitle it needs 97_Encryption beside 98_Tooling.

Examples
--------
Issue the demo entitlement (docs/README.md, "Issue an entitlement"), then from any folder:

    python examples/protected_app_example.py
"""

import sys
from pathlib import Path

_ENTITLE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENTITLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENTITLE_ROOT))

from entitle.common import EntitleError  # noqa: E402
from entitle.entitlements import verify_entitlement  # noqa: E402
from entitle.rights import EntitlementDenied  # noqa: E402

ISSUER_ID = "JasonBrisart"
SUBJECT_ID = "ResearchLabA"
PRODUCT_ID = "EntitleDemo"
ENTITLEMENT_FILE = str(_ENTITLE_ROOT / "entitlements" / "lab_a.entitle")
MASTER_KEY = "change-this-master-key-change-this-master-key"


def load_entitlement(entitlement_file):
    return verify_entitlement(
        issuer=ISSUER_ID,
        subject=SUBJECT_ID,
        product=PRODUCT_ID,
        master_key=MASTER_KEY,
        path=entitlement_file,
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


def main(entitlement_file=ENTITLEMENT_FILE):
    if not Path(entitlement_file).exists():
        print(f"No entitlement file found at: {entitlement_file}")
        print("Issue one first, for example:")
        print()
        print("  python run.py issue \\")
        print(f"      --issuer {ISSUER_ID} --subject {SUBJECT_ID} --product {PRODUCT_ID} \\")
        print("      --entitlement-id lab-a-demo-001 \\")
        print(f'      --master-key "{MASTER_KEY}" \\')
        print("      --modify --fork --deployment-limit 3 \\")
        print(f"      --output {entitlement_file}")
        return

    try:
        entitlement = load_entitlement(entitlement_file)
    except (EntitleError, ValueError, OSError) as exc:
        print("Entitlement could not be checked.")
        print(f"Reason: {exc}")
        print()
        base_program()
        print()
        print("Governed features remain locked.")
        return

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
