"""
File: tests/test_example.py

Purpose
-------
Run examples/protected_app_example.py against real entitlements and check that it guards
  features the way its documentation says: only granted rights unlock, a denied entitlement
  locks everything, a check that cannot run (no encryption, a damaged, empty, UTF-16 or oversized
  file, an unreadable file) locks everything while the base program still starts, and a missing
  file explains how to issue one.

Communication / relationships
-----------------------------
Loads examples/protected_app_example.py by path (it is not a package), uses tests/support.py
  to issue entitlements, imports entitle/entitlements.py to issue one with a different key,
  and imports entitle/encryption.py to simulate a missing 97_Encryption. Run by pytest;
  nothing imports it.

Settings / parameters
---------------------
Entitlements are issued into pytest's tmp_path for the example's own demo identity and key.
  main() is given the path, so the Entitle folder's entitlements/ is never touched.

Edge cases
----------
Covers an entitlement that grants one right, a file issued for a different key (denied), a
  check that cannot run because 97_Encryption is not found, a file that is garbage, empty,
  UTF-16 or over the size limit, a path that is a folder (cannot be read), and an absent file.

Known limitations
-----------------
Checks printed text, so a reworded message needs the test updated with it.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_example.py
"""

import importlib.util

import pytest

from entitle import encryption, entitlements
from support import DRBG_PERSONALIZATION, DRBG_SEED, ENTITLE_ROOT, issue_demo


def _load_example():
    spec = importlib.util.spec_from_file_location("protected_app_example", ENTITLE_ROOT / "examples" / "protected_app_example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_granted_rights_unlock_features(tmp_path, capsys):
    path = tmp_path / "lab.entitle"
    issue_demo(path, modify=True)
    _load_example().main(path)
    out = capsys.readouterr().out
    assert "Modification rights verified." in out
    assert "Enterprise locked: Required right not granted: can_use_enterprise_features" in out
    assert "Fork locked" in out and "Source Export locked" in out and "Redistribution locked" in out


def test_a_denied_entitlement_leaves_every_governed_feature_locked(tmp_path, capsys):
    from entitle.entitlements import issue_entitlement

    path = tmp_path / "other_key.entitle"
    issue_entitlement(
        issuer="JasonBrisart", subject="ResearchLabA", product="EntitleDemo", entitlement_id="e", output=path,
        master_key="a-different-master-key-of-enough-length!!", drbg_seed=DRBG_SEED,
        drbg_personalization=DRBG_PERSONALIZATION, modify=True,
    )
    _load_example().main(path)
    out = capsys.readouterr().out
    assert "Reason: bsr_verification_failed" in out and "Governed features remain locked." in out
    assert "rights verified" not in out


def test_a_check_that_cannot_run_keeps_every_governed_feature_locked(tmp_path, capsys, monkeypatch):
    path = tmp_path / "lab.entitle"
    issue_demo(path, modify=True)
    unavailable = encryption.EncryptionLink(available=False, location=encryption.ENCRYPTION_DIR, problem="gone")
    monkeypatch.setattr(encryption, "status", lambda: unavailable)
    _load_example().main(path)
    out = capsys.readouterr().out
    assert "Entitlement could not be checked." in out and "Reason: Encryption not found: gone" in out
    assert "Base program started." in out and "Governed features remain locked." in out
    assert "rights verified" not in out


@pytest.mark.parametrize("content,reason", [
    (b"this is not an entitlement", "is not a protected Entitle entitlement file"),
    (b"", "is not a protected Entitle entitlement file"),
    (b"\xff\xfe" + "{}".encode("utf-16-le"), "is UTF-16 text"),
    (b"{" + b" " * (entitlements.MAX_FILE_BYTES + 1) + b"}", "is too large to be an entitlement file"),
])
def test_a_file_that_is_not_a_usable_entitlement_locks_everything_but_the_base_program_runs(tmp_path, capsys, content, reason):
    # Before 0.6.0 these crashed with a traceback before the base program started, although the
    # example promises that anything short of a verified entitlement leaves governed features locked.
    path = tmp_path / "lab.entitle"
    path.write_bytes(content)
    _load_example().main(path)
    out = capsys.readouterr().out
    assert "Entitlement could not be checked." in out and reason in out
    assert "Base program started." in out and "Governed features remain locked." in out
    assert "rights verified" not in out and "unlocked" not in out


def test_a_path_that_cannot_be_read_locks_everything_too(tmp_path, capsys):
    folder = tmp_path / "a_folder.entitle"
    folder.mkdir()
    _load_example().main(folder)
    out = capsys.readouterr().out
    assert "Entitlement could not be checked." in out and "Base program started." in out
    assert "Governed features remain locked." in out


def test_a_missing_file_prints_the_command_that_issues_one(tmp_path, capsys):
    path = tmp_path / "absent.entitle"
    _load_example().main(path)
    out = capsys.readouterr().out
    assert f"No entitlement file found at: {path}" in out
    assert "python run.py issue" in out and f"--output {path}" in out
    assert "drbg" not in out and "main.py" not in out
