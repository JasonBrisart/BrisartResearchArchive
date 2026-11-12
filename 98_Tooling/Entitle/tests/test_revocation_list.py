"""
File: tests/test_revocation_list.py

Purpose
-------
Verify entitle/revocation_list.py: a published list holds exactly the entitlements currently
  revoked for the issuer, its sequence grows with the log, it verifies only with the issuer's key
  and for the issuer it names, and any change to it is refused.

Communication / relationships
-----------------------------
Imports entitle/records.py, entitle/revoke.py, entitle/revocation_list.py, entitle/signing.py and
  tests/support.py (make_keys). Run by pytest; nothing imports it.

Settings / parameters
---------------------
One key pair per module; each test has its own record log under pytest's tmp_path.

Edge cases
----------
Covers reinstated IDs (left out), revocations recorded for another issuer (left out) or for no
  issuer (included), an empty list, a list for another issuer, an untrusted key, a modified file,
  and a signed document of the right kind that is not a revocation list.

Known limitations
-----------------
How verification uses a list is tested in tests/test_entitlements.py.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_revocation_list.py
"""
import pytest

from entitle.records import RecordStore
from entitle.revocation_list import KIND, load_revocation_list, publish_revocation_list
from entitle.revoke import reinstate, revoke
from entitle.signing import SignatureRejected, sign_document
from support import ISSUER, make_keys


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    return make_keys(tmp_path_factory.mktemp("keys"))


def _publish(store, keys, tmp_path, issuer=ISSUER):
    output = tmp_path / "revoked.entitle-crl"
    return publish_revocation_list(store, keys[0], issuer=issuer, output=output), output


def test_the_list_holds_what_is_revoked_now_for_this_issuer(store_path, keys, tmp_path):
    store = RecordStore(store_path)
    revoke(store, "a", issuer_id=ISSUER, reason="compromise")
    revoke(store, "b", reason="no issuer recorded")
    revoke(store, "c", issuer_id="SomeoneElse")
    revoke(store, "d", issuer_id=ISSUER)
    reinstate(store, "d", issuer_id=ISSUER)
    payload, output = _publish(store, keys, tmp_path)
    assert [entry["entitlement_id"] for entry in payload["revoked"]] == ["a", "b"]
    assert payload["sequence"] == 5 and payload["revoked"][0]["reason"] == "compromise"
    listing = load_revocation_list(output, [keys[1]], issuer=ISSUER)
    assert set(listing.revoked) == {"a", "b"} and listing.sequence == 5 and listing.key_id == keys[1].key_id
    assert listing.reason_for("a") == "compromise" and listing.reason_for("zzz") is None


def test_an_empty_list_is_valid_and_the_sequence_grows_with_the_log(store_path, keys, tmp_path):
    store = RecordStore(store_path)
    first, output = _publish(store, keys, tmp_path)
    assert first["revoked"] == [] and first["sequence"] == 0
    revoke(store, "a")
    reinstate(store, "a")
    second, _ = _publish(store, keys, tmp_path)
    assert second["revoked"] == [] and second["sequence"] == 2


def test_a_list_for_another_issuer_or_from_another_key_is_refused(store_path, keys, tmp_path):
    _, output = _publish(RecordStore(store_path), keys, tmp_path, issuer="SomeoneElse")
    with pytest.raises(SignatureRejected) as caught:
        load_revocation_list(output, [keys[1]], issuer=ISSUER)
    assert caught.value.reason == "wrong_issuer"
    stranger = make_keys(tmp_path / "stranger", name="Stranger")
    with pytest.raises(SignatureRejected) as caught:
        load_revocation_list(output, [stranger[1]], issuer="SomeoneElse")
    assert caught.value.reason == "unknown_signing_key"


def test_a_modified_list_is_refused(store_path, keys, tmp_path):
    store = RecordStore(store_path)
    revoke(store, "a")
    _, output = _publish(store, keys, tmp_path)
    lines = output.read_text(encoding="utf-8").split("\n")
    body = lines.index("") + 1
    lines[body] = ("A" if lines[body][0] != "A" else "B") + lines[body][1:]
    output.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(SignatureRejected) as caught:
        load_revocation_list(output, [keys[1]], issuer=ISSUER)
    assert caught.value.reason in ("signature_invalid", "not_signed_document")


def test_a_signed_document_that_is_not_a_revocation_list_is_refused(keys, tmp_path):
    output = tmp_path / "odd.entitle-crl"
    output.write_text(sign_document(KIND, {"format": "something.else", "issuer_id": ISSUER}, keys[0]), encoding="utf-8")
    with pytest.raises(SignatureRejected) as caught:
        load_revocation_list(output, [keys[1]], issuer=ISSUER)
    assert caught.value.reason == "payload_invalid"
