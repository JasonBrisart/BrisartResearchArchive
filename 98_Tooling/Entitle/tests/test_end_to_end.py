"""
File: tests/test_end_to_end.py

Purpose
-------
Prove Entitle works from a fresh install to a finished audit, through real processes, using
  whichever 97_Encryption/Official sits beside it. The whole workflow runs the way an operator
  would run it: version and encryption link, issue, verify (right and wrong key), migrate a file
  written by the previous encryption, deploy up to and past the limit, deploy from the migrated
  file, fork, provenance, revoke, a refused deployment, reinstate, the audit report, tamper
  detection. A second test runs the signed lifecycle the same way: keys made outside the archive
  with a passphrase file, a signed entitlement, verify with the public key only, deployments under
  --strict, a release, a signed checkpoint, the example application holding only the public key,
  and a signed revocation list that locks it. A third races several real run.py processes against
  a deployment limit. This is the test to run on the real archive: it uses the real BSR2 library
  and nothing else stands between Entitle and it.

Communication / relationships
-----------------------------
Imports entitle/encryption.py (the folder to copy, including brisart_security_signature),
  entitle/records.py (to read the log the processes wrote), tests/support.py and version.py (the
  version the processes report). Copies the Entitle folder and the linked 97_Encryption/Official
  into a temporary archive (98_Tooling/Entitle and 97_Encryption/Official side by side) and runs
  run.py and examples/protected_app_example.py there, so the installed copy, not the development
  tree, is what is exercised. Run by pytest; nothing imports it.

Settings / parameters
---------------------
Everything is written under pytest's tmp_path. Each command is a separate Python process with a
  120-second limit; the race test starts six at once. Expect tens of seconds with the real
  library, because BSR2 is pure Python and deliberately slow.

Edge cases
----------
The previous-format entitlement is the fixture in tests/fixtures/, issued for the demo identity
  and key; after migrating it, it is deployed from like any other file. The tamper step edits one
  field of a record in place. The race test expects exactly the limit's worth of recorded
  deployments, an intact chain, and the others refused with deployment_limit_reached.

Known limitations
-----------------
Does not open a window (tests/test_gui.py covers the window against a stand-in) and runs on the
  platform the suite is run on, so Windows and macOS are only covered when the suite is run there.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_end_to_end.py -v
"""

import json
import shutil
import subprocess
import sys

from entitle import encryption
from entitle.records import RecordStore
from support import ENTITLE_ROOT, ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PASSPHRASE, PRODUCT, SUBJECT, run_entitle
from version import __version__

IDENTITY = ["--issuer", ISSUER, "--subject", SUBJECT, "--product", PRODUCT]


def _install(tmp_path):
    """A fresh archive: Entitle in 98_Tooling and the linked BSR2 in 97_Encryption, side by side."""
    archive = tmp_path / "archive"
    installed = archive / "98_Tooling" / "Entitle"
    shutil.copytree(ENTITLE_ROOT, installed, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", "entitlements", "records", "reports", "keys"))
    shutil.copytree(encryption.ENCRYPTION_DIR, archive / "97_Encryption" / "Official",
                    ignore=shutil.ignore_patterns("__pycache__", "tests", "docs", "research", "tools", "audio"))
    return installed


def test_a_fresh_install_runs_the_whole_lifecycle_with_the_linked_encryption(tmp_path):
    installed = _install(tmp_path)
    work = tmp_path / "work"
    work.mkdir()

    def run(*args, expect=0):
        done = run_entitle(*args, cwd=work, root=installed)
        assert done.returncode == expect, f"run.py {' '.join(args[:3])} exited {done.returncode}\n{done.stdout}\n{done.stderr}"
        assert "Traceback" not in done.stderr
        return done

    # The install links the encryption that sits beside it.
    version = run("--version").stdout.splitlines()
    assert version[0] == f"Entitle {__version__}"
    assert version[1].startswith("Encryption: ") and version[1].endswith(", from 97_Encryption/Official")
    assert version[2] == "Signatures: Ed25519 (RFC 8032), from 97_Encryption/Official"

    # Issue, verify, and refuse a wrong key.
    lab = work / "entitlements" / "lab.entitle"
    run("issue", *IDENTITY, "--entitlement-id", "lab-1", "--master-key", MASTER_KEY, "--deployment-limit", "2",
        "--modify", "--fork", "--output", str(lab))
    assert lab.read_text(encoding="utf-8").startswith("-----BEGIN BSR2 SEALED MESSAGE-----")
    verified = run("verify", *IDENTITY, "--master-key", MASTER_KEY, "--file", str(lab))
    assert "VERIFIED: entitlement is valid." in verified.stdout and "previous encryption" not in verified.stdout and "shared-key entitlement" in verified.stdout
    denied = run("verify", *IDENTITY, "--master-key", "wrong-key-wrong-key-wrong-key-wrong-key", "--file", str(lab), expect=1)
    assert "DENIED: bsr_verification_failed" in denied.stdout

    # A file written by the previous encryption is flagged, migrated, and then unchanged.
    old = work / "entitlements" / "older.entitle"
    shutil.copyfile(LEGACY_ENTITLEMENT, old)
    assert "NOTE: this file still uses the previous encryption" in run("verify", *IDENTITY, "--master-key", MASTER_KEY, "--file", str(old)).stdout
    assert run("migrate", *IDENTITY, "--master-key", MASTER_KEY, "--file", str(old)).stdout.startswith("MIGRATED:")
    assert "previous encryption" not in run("verify", *IDENTITY, "--master-key", MASTER_KEY, "--file", str(old)).stdout
    assert run("migrate", *IDENTITY, "--master-key", MASTER_KEY, "--file", str(old)).stdout.startswith("UNCHANGED:")

    # Governed deployments: up to the limit, then refused; the migrated file deploys like any other.
    store = str(work / "records" / "entitle_records.log")

    def deploy(path, host):
        return json.loads(run("track", "deploy", *IDENTITY, "--master-key", MASTER_KEY, "--entitlement", str(path),
                              "--host", host, "--environment", "air-gapped", "--store", store).stdout)

    assert [deploy(lab, h)["recorded"] for h in ("node-1", "node-2")] == [True, True]
    refused = deploy(lab, "node-3")
    assert (refused["recorded"], refused["reason"], refused["deployments_used"]) == (False, "deployment_limit_reached", 2)
    from_migrated = deploy(old, "node-4")
    assert from_migrated["recorded"] is True and from_migrated["record"]["data"]["entitlement_id"] == "lab-a-demo-001"

    # Documentary records, then revocation and reinstatement.
    run("track", "fork", "--product", PRODUCT, "--source-version", "1.4.0", "--fork-name", "lab-custom",
        "--maintainer", SUBJECT, "--store", store)
    run("track", "provenance", "--product", PRODUCT, "--origin", ISSUER, "--version", "1.4.0",
        "--custodian", SUBJECT, "--store", store)
    run("revoke", "revoke", "--entitlement-id", "lab-a-demo-001", "--reason", "key compromise", "--store", store)
    assert deploy(old, "node-5")["reason"] == "entitlement_revoked"
    run("revoke", "reinstate", "--entitlement-id", "lab-a-demo-001", "--reason", "cleared", "--store", store)
    assert run("revoke", "check", "--entitlement-id", "lab-a-demo-001", "--store", store).stdout.rstrip().endswith("ACTIVE")

    # The audit sees all of it and the chain is intact.
    report = json.loads(run("report", "--store", store, "--format", "json").stdout)
    assert report["chain"] == {"valid": True, "broken_index": None, "reason": "ok", "record_count": 7}
    assert report["counts_by_type"] == {"deployment": 3, "fork": 1, "provenance": 1, "revocation": 1, "reinstatement": 1}
    assert report["deployments_by_product"] == {PRODUCT: 3}

    # Editing a record is detected.
    log = work / "records" / "entitle_records.log"
    lines = log.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["data"]["host"] = "somewhere-else"
    lines[1] = json.dumps(record, sort_keys=True)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "BROKEN: entry_hash_mismatch at record index 1." in run("report", "--store", store).stdout




def test_a_fresh_install_runs_the_signed_lifecycle_and_the_example_holds_only_a_public_key(tmp_path):
    installed = _install(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    secrets = tmp_path / "outside-the-archive"
    passphrase = secrets / "passphrase.txt"
    secrets.mkdir()
    passphrase.write_text(PASSPHRASE, encoding="utf-8")
    signing_key, public_key = secrets / "issuer.signing-key", installed / "keys" / "issuer.public-key"
    with_key = ["--signing-key", str(signing_key), "--passphrase-file", str(passphrase)]

    def run(*args, expect=0):
        done = run_entitle(*args, cwd=work, root=installed, env={"ENTITLE_PASSPHRASE": ""})
        assert done.returncode == expect, f"run.py {' '.join(args[:3])} exited {done.returncode}\n{done.stdout}\n{done.stderr}"
        assert "Traceback" not in done.stderr
        return done

    run("keys", "generate", "--name", ISSUER, "--signing-key", str(signing_key), "--public-key", str(public_key),
        "--passphrase-file", str(passphrase))
    demo = installed / "entitlements" / "lab_a.entitle"
    run("issue", *IDENTITY, "--entitlement-id", "lab-a-demo-001", *with_key, "--modify", "--deployment-limit", "1",
        "--output", str(demo))
    assert "VERIFIED" in run("verify", *IDENTITY, "--public-key", str(public_key), "--file", str(demo)).stdout
    store = str(work / "records" / "log")
    deploy = ["track", "deploy", *IDENTITY, "--public-key", str(public_key), "--entitlement", str(demo), "--store", store,
              "--strict"]
    run(*deploy, "--host", "node-1")
    run(*deploy, "--host", "node-2", expect=3)
    run("track", "release", "--product", PRODUCT, "--subject", SUBJECT, "--entitlement-id", "lab-a-demo-001",
        "--host", "node-1", "--store", store)
    run(*deploy, "--host", "node-2")
    checkpoint = str(secrets / "log.entitle-checkpoint")
    run("checkpoint", "create", *with_key, "--store", store, "--output", checkpoint)
    run("checkpoint", "verify", "--public-key", str(public_key), "--store", store, "--checkpoint", checkpoint)

    # The example application ships with the public key only and unlocks exactly what was granted.
    shown = subprocess.run([sys.executable, str(installed / "examples" / "protected_app_example.py")],
                           capture_output=True, text=True, timeout=120, cwd=work)
    assert shown.returncode == 0, shown.stderr
    assert "Modification rights verified." in shown.stdout and "Fork locked" in shown.stdout

    # Revoked through a signed list that travels to the lab like the entitlement did.
    run("revoke", "revoke", "--entitlement-id", "lab-a-demo-001", "--issuer", ISSUER, "--store", store)
    run("revoke", "publish", "--issuer", ISSUER, *with_key, "--store", store,
        "--output", str(installed / "entitlements" / "revoked.entitle-crl"))
    shown = subprocess.run([sys.executable, str(installed / "examples" / "protected_app_example.py")],
                           capture_output=True, text=True, timeout=120, cwd=work)
    assert "Reason: entitlement_revoked" in shown.stdout and "rights verified" not in shown.stdout


def test_racing_run_py_processes_never_exceed_the_deployment_limit(tmp_path):
    installed = _install(tmp_path)
    entitlement = tmp_path / "lab.entitle"
    store = tmp_path / "records" / "entitle_records.log"
    issued = run_entitle("issue", *IDENTITY, "--entitlement-id", "lab-1", "--master-key", MASTER_KEY,
                         "--deployment-limit", "2", "--output", str(entitlement), root=installed)
    assert issued.returncode == 0, issued.stderr
    command = [sys.executable, str(installed / "run.py"), "track", "deploy", *IDENTITY, "--master-key", MASTER_KEY,
               "--entitlement", str(entitlement), "--store", str(store)]
    processes = [subprocess.Popen(command + ["--host", f"node-{n}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for n in range(6)]
    outcomes = []
    for process in processes:
        out, err = process.communicate(timeout=180)
        assert process.returncode == 0, err
        outcomes.append(json.loads(out))
    assert sorted(o["recorded"] for o in outcomes) == [False] * 4 + [True] * 2
    assert {o["reason"] for o in outcomes if not o["recorded"]} == {"deployment_limit_reached"}
    chain = RecordStore(store).verify_chain()
    assert (chain.valid, chain.record_count) == (True, 2)
