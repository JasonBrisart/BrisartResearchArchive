"""
File: examples/protected_app_example.py

Purpose
-------
Show how another program guards its features with Entitle, the recommended way: the program
  ships with the issuer's public key only, checks a signed entitlement, and so can verify but
  can never issue. The base program always runs; each governed feature (enterprise, modify,
  fork, source export, redistribution) runs only when a verified entitlement grants the
  matching right. Anything short of a verified entitlement leaves every governed feature locked.
  There is no activation server, telemetry or network use.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError), entitle/entitlements.py (verify_entitlement),
  entitle/host.py (HostState), entitle/rights.py (EntitlementDenied) and entitle/signing.py
  (load_public_keys): the whole interface a protected program needs. Puts the Entitle folder
  on sys.path so it runs from any working folder. Nothing imports it; tests/test_example.py
  loads it by path and runs main().

Settings / parameters
---------------------
ISSUER_ID (JasonBrisart), SUBJECT_ID (ResearchLabA) and PRODUCT_ID (EntitleDemo) must match the
  entitlement; they match the commands in docs/README.md. PUBLIC_KEY_FILE (keys/issuer.public-key),
  ENTITLEMENT_FILE (entitlements/lab_a.entitle), REVOCATION_LIST_FILE
  (entitlements/revoked.entitle-crl, used only if present) and HOST_STATE_FILE
  (entitlements/host-state.json) are under the Entitle folder; main() takes each as an argument.
  The source holds no secret.

Edge cases
----------
With no entitlement or public key file it prints the commands that create them and returns. A
  denied entitlement (another issuer's key, wrong lab or product, expired, not yet valid, bound
  to another machine, revoked in the revocation list, a clock wound back behind the host state)
  keeps every governed feature locked and prints the reason. A check that cannot run at all is
  treated the same way: the signature module not found, a shared-key file (this program has no
  master key, by design), a file that is not an entitlement (damaged, empty, UTF-16, too large)
  or one that cannot be read. The base program still starts and nothing governed unlocks.

Known limitations
-----------------
The program checks once at start. Like any check that runs on a machine the user controls, it
  can be patched out by someone who edits this program; what signing guarantees is that nobody
  without the issuer's signing key can produce an entitlement it accepts. The host state file can
  be deleted, which resets the clock check. It needs 97_Encryption beside 98_Tooling.

Examples
--------
Create keys and issue a signed entitlement (docs/README.md, "Quick start"), then from any folder:

    python examples/protected_app_example.py
"""
import sys
from pathlib import Path

_ENTITLE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENTITLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENTITLE_ROOT))

from entitle.common import EntitleError  # noqa: E402
from entitle.entitlements import verify_entitlement  # noqa: E402
from entitle.host import HostState  # noqa: E402
from entitle.rights import EntitlementDenied  # noqa: E402
from entitle.signing import load_public_keys  # noqa: E402

ISSUER_ID = "JasonBrisart"
SUBJECT_ID = "ResearchLabA"
PRODUCT_ID = "EntitleDemo"
ENTITLEMENT_FILE = _ENTITLE_ROOT / "entitlements" / "lab_a.entitle"
PUBLIC_KEY_FILE = _ENTITLE_ROOT / "keys" / "issuer.public-key"
REVOCATION_LIST_FILE = _ENTITLE_ROOT / "entitlements" / "revoked.entitle-crl"
HOST_STATE_FILE = _ENTITLE_ROOT / "entitlements" / "host-state.json"


def load_entitlement(entitlement_file, public_key_file, revocation_list_file, host_state_file):
    revocation_list = Path(revocation_list_file) if revocation_list_file else None
    return verify_entitlement(
        issuer=ISSUER_ID,
        subject=SUBJECT_ID,
        product=PRODUCT_ID,
        public_keys=load_public_keys([public_key_file]),
        revocation_list=revocation_list if revocation_list and revocation_list.exists() else None,
        host_state=HostState(host_state_file) if host_state_file else None,
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


def _print_how_to_issue(entitlement_file, public_key_file):
    print("Create the issuer keys once, then issue a signed entitlement, for example:")
    print()
    print("  python run.py keys generate --name JasonBrisart \\")
    print(f"      --signing-key ~/EntitleKeys/issuer.signing-key --public-key {public_key_file}")
    print("  python run.py issue \\")
    print(f"      --issuer {ISSUER_ID} --subject {SUBJECT_ID} --product {PRODUCT_ID} \\")
    print("      --entitlement-id lab-a-demo-001 --signing-key ~/EntitleKeys/issuer.signing-key \\")
    print("      --modify --fork --deployment-limit 3 \\")
    print(f"      --output {entitlement_file}")


def main(entitlement_file=ENTITLEMENT_FILE, public_key_file=PUBLIC_KEY_FILE,
         revocation_list_file=REVOCATION_LIST_FILE, host_state_file=HOST_STATE_FILE):
    missing = [str(path) for path in (entitlement_file, public_key_file) if not Path(path).exists()]
    if missing:
        print(f"Not found: {', '.join(missing)}")
        _print_how_to_issue(entitlement_file, public_key_file)
        return
    try:
        entitlement = load_entitlement(entitlement_file, public_key_file, revocation_list_file, host_state_file)
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
