"""
File: tests/test_example.py

Purpose
-------
Run examples/protected_app_example.py against real signed entitlements and check that it
  guards features the way its documentation says: it holds no secret, only granted rights
  unlock, an entitlement signed by another key or revoked in a revocation list or checked
  under a clock wound back locks everything, a check that cannot run (no signature module, a
  shared-key file, a damaged, empty, UTF-16 or oversized file, an unreadable file) locks
  everything while the base program still starts, and missing files explain how to create them.

Communication / relationships
-----------------------------
Loads examples/protected_app_example.py by path (it is not a package), uses tests/support.py
  (make_keys, issue_signed, issue_demo), entitle/records.py, entitle/revoke.py and
  entitle/revocation_list.py to publish a list, and entitle/encryption.py to simulate a missing
  signature module. Run by pytest; nothing imports it.

Settings / parameters
---------------------
One key pair per module; entitlements, lists and host state are written to pytest's tmp_path
  for the example's demo identity. main() is given every path, so the Entitle folder's
  entitlements/ and keys/ are never touched.

Edge cases
----------
Covers an entitlement that grants one right, one signed by an untrusted key, a shared-key file,
  a revoked entitlement, a host state ahead of the clock, a missing signature module, a file
  that is garbage, empty, UTF-16 or over the size limit, a folder, and an absent file.

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
from support import ENTITLE_ROOT, MASTER_KEY, issue_demo, issue_signed, make_keys


def _load_example():
    spec = importlib.util.spec_from_file_location("protected_app_example", ENTITLE_ROOT / "examples" / "protected_app_example.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    return make_keys(tmp_path_factory.mktemp("keys"))


def _run(tmp_path, path, keys, capsys, **options):
    signing_key, public, signing_path, public_path = keys
    _load_example().main(path, public_key_file=public_path, revocation_list_file=options.get("revocation_list"),
                         host_state_file=options.get("state", tmp_path / "state.json"))
    return capsys.readouterr().out


def test_only_granted_rights_unlock_features(tmp_path, capsys, keys):
    path = tmp_path / "lab.entitle"
    issue_signed(path, keys[0], modify=True)
    out = _run(tmp_path, path, keys, capsys)
    assert "Modification rights verified." in out
    assert "Enterprise locked: Required right not granted: can_use_enterprise_features" in out
    assert "Fork locked" in out and "Source Export locked" in out and "Redistribution locked" in out


def test_the_example_holds_no_secret_only_a_public_key(capsys):
    source = (ENTITLE_ROOT / "examples" / "protected_app_example.py").read_text(encoding="utf-8")
    assert "MASTER_KEY" not in source and "master_key" not in source and "PUBLIC_KEY_FILE" in source


def test_an_entitlement_signed_by_another_key_leaves_every_governed_feature_locked(tmp_path, capsys, keys):
    other = make_keys(tmp_path / "other", name="SomeoneElse")
    path = tmp_path / "forged.entitle"
    issue_signed(path, other[0], modify=True)
    out = _run(tmp_path, path, keys, capsys)
    assert "Reason: unknown_signing_key" in out and "Governed features remain locked." in out
    assert "rights verified" not in out


def test_a_shared_key_file_cannot_unlock_anything_without_the_secret(tmp_path, capsys, keys):
    path = tmp_path / "shared.entitle"
    issue_demo(path, modify=True)
    out = _run(tmp_path, path, keys, capsys)
    assert "Entitlement could not be checked." in out and "shared-key entitlement" in out
    assert "rights verified" not in out


def test_a_revoked_entitlement_is_refused_offline_from_the_revocation_list(tmp_path, capsys, keys):
    from entitle.records import RecordStore
    from entitle.revocation_list import publish_revocation_list
    from entitle.revoke import revoke

    path = tmp_path / "lab.entitle"
    issue_signed(path, keys[0], entitlement_id="lab-9", modify=True)
    store = RecordStore(tmp_path / "r.log")
    revoke(store, "lab-9", reason="key compromise")
    publish_revocation_list(store, keys[0], issuer="JasonBrisart", output=tmp_path / "revoked.entitle-crl")
    out = _run(tmp_path, path, keys, capsys, revocation_list=tmp_path / "revoked.entitle-crl")
    assert "Reason: entitlement_revoked" in out and "rights verified" not in out


def test_a_clock_wound_back_is_refused(tmp_path, capsys, keys):
    import datetime
    import json

    path = tmp_path / "lab.entitle"
    issue_signed(path, keys[0], modify=True)
    future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)).replace(microsecond=0)
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"format": "entitle.host-state.v1", "latest_time": future.isoformat(),
                                 "revocation_sequences": {}}), encoding="utf-8")
    out = _run(tmp_path, path, keys, capsys, state=state)
    assert "Reason: clock_rollback_detected" in out and "rights verified" not in out


def test_a_check_that_cannot_run_keeps_every_governed_feature_locked(tmp_path, capsys, monkeypatch, keys):
    path = tmp_path / "lab.entitle"
    issue_signed(path, keys[0], modify=True)
    unavailable = encryption.EncryptionLink(available=False, location=encryption.ENCRYPTION_DIR, problem="gone",
                                            label="Signatures")
    monkeypatch.setattr(encryption, "signature_status", lambda: unavailable)
    out = _run(tmp_path, path, keys, capsys)
    assert "Entitlement could not be checked." in out and "Reason: Signatures not found: gone" in out
    assert "Base program started." in out and "Governed features remain locked." in out
    assert "rights verified" not in out


@pytest.mark.parametrize("content,reason", [
    (b"this is not an entitlement", "is not a protected Entitle entitlement file"),
    (b"", "is not a protected Entitle entitlement file"),
    (b"\xff\xfe" + "{}".encode("utf-16-le"), "is UTF-16 text"),
    (b"{" + b" " * (entitlements.MAX_FILE_BYTES + 1) + b"}", "is too large to be an entitlement file"),
])
def test_a_file_that_is_not_a_usable_entitlement_locks_everything_but_the_base_program_runs(
    tmp_path, capsys, keys, content, reason
):
    path = tmp_path / "lab.entitle"
    path.write_bytes(content)
    out = _run(tmp_path, path, keys, capsys)
    assert "Entitlement could not be checked." in out and reason in out
    assert "Base program started." in out and "Governed features remain locked." in out
    assert "rights verified" not in out and "unlocked" not in out


def test_a_path_that_cannot_be_read_locks_everything_too(tmp_path, capsys, keys):
    folder = tmp_path / "a_folder.entitle"
    folder.mkdir()
    out = _run(tmp_path, folder, keys, capsys)
    assert "Entitlement could not be checked." in out and "Base program started." in out
    assert "Governed features remain locked." in out


def test_a_missing_file_prints_the_commands_that_create_one(tmp_path, capsys, keys):
    path = tmp_path / "absent.entitle"
    out = _run(tmp_path, path, keys, capsys)
    assert f"Not found: {path}" in out
    assert "python run.py keys generate" in out and "python run.py issue" in out and f"--output {path}" in out
    assert "master-key" not in out and "main.py" not in out
