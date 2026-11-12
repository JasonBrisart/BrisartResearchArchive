"""
File: tests/test_signing.py

Purpose
-------
Verify entitle/signing.py: issuer key pairs and their two files, the passphrase that protects a
  signing key, the guard that keeps a signing key out of a Git working tree, and the signed
  document format shared by entitlements, revocation lists and checkpoints, including every way a
  signed document can be refused and the domain separation that stops a signature made for one
  kind of document being replayed as another.

Communication / relationships
-----------------------------
Imports entitle/signing.py, entitle/common.py (EntitleError) and tests/support.py (make_keys,
  PASSPHRASE). Needs 97_Encryption beside 98_Tooling (Ed25519 for signatures, BSR2 to seal the
  signing key). Run by pytest; nothing imports it.

Settings / parameters
---------------------
One key pair is made per module (scrypt makes each one take a fraction of a second) and a second
  one where a test needs an untrusted key. Files are written under pytest's tmp_path.

Edge cases
----------
Covers a wrong or short passphrase, existing files (refused unless overwrite), the same path for
  both files, a salt that comes from the linked entropy source, a failed entropy health check
  (key generation stops before anything is written), a key inside a Git working tree (refused
  unless allowed), a damaged public key file,
  a signing key file whose seed does not match its public key, a public key presented as a
  signing key, a modified payload or signature, an untrusted key, a document of another kind, a
  signature lifted from one kind of document into another, duplicate or missing headers, invalid
  base64, a payload that is not a JSON object, Windows line endings and an empty trust list.

Known limitations
-----------------
Ed25519 itself is tested against RFC 8032 in 97_Encryption/Official/tests; here it is only used.
  The owner-only permission check runs on POSIX only.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_signing.py
"""
import base64
import json
import os
import stat

import pytest

from entitle import encryption, signing
from entitle.common import EntitleError
from entitle.signing import (
    SignatureRejected,
    generate_key_pair,
    key_id_for,
    load_public_key,
    load_public_keys,
    load_signing_key,
    open_document,
    peek_document,
    sign_document,
)
from support import PASSPHRASE, make_keys


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    return make_keys(tmp_path_factory.mktemp("keys"))


class TestKeyFiles:
    def test_a_key_pair_is_two_files_and_the_public_one_holds_no_secret(self, keys):
        signing_key, public, signing_path, public_path = keys
        assert signing_key.key_id == public.key_id == key_id_for(public.raw) and len(public.key_id) == 32
        published = json.loads(public_path.read_text(encoding="utf-8"))
        assert set(published) == {"format", "name", "key_id", "algorithm", "public_key", "created_at"}
        private = signing_path.read_text(encoding="utf-8")
        assert signing_key.seed.hex() not in private and "sealed_seed" in private

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_the_signing_key_is_readable_by_its_owner_only(self, keys):
        assert stat.S_IMODE(keys[2].stat().st_mode) == 0o600
        assert stat.S_IMODE(keys[3].stat().st_mode) & 0o044  # the public key stays readable

    def test_the_passphrase_opens_the_key_and_anything_else_does_not(self, keys):
        assert load_signing_key(keys[2], PASSPHRASE).seed == keys[0].seed
        with pytest.raises(EntitleError, match="the passphrase does not open"):
            load_signing_key(keys[2], PASSPHRASE + "!")
        with pytest.raises(ValueError, match="protected by a passphrase"):
            load_signing_key(keys[2], None)

    def test_a_short_passphrase_is_refused_before_anything_is_written(self, tmp_path):
        with pytest.raises(ValueError, match="at least 12 bytes"):
            generate_key_pair(name="I", signing_key_path=tmp_path / "s", public_key_path=tmp_path / "p", passphrase="short")
        assert list(tmp_path.iterdir()) == []

    def test_existing_files_are_never_replaced_unless_asked(self, tmp_path):
        make_keys(tmp_path)
        with pytest.raises(FileExistsError):
            make_keys(tmp_path)
        generate_key_pair(name="JasonBrisart", signing_key_path=tmp_path / "JasonBrisart.signing-key",
                          public_key_path=tmp_path / "JasonBrisart.public-key", passphrase=PASSPHRASE, overwrite=True)

    def test_the_two_files_must_be_different(self, tmp_path):
        with pytest.raises(ValueError, match="two different files"):
            generate_key_pair(name="I", signing_key_path=tmp_path / "k", public_key_path=tmp_path / "k", passphrase=PASSPHRASE)

    def test_the_key_file_salt_comes_from_the_linked_entropy_source(self, tmp_path, monkeypatch):
        entropy = encryption.require().entropy
        fixed = bytes(range(16))
        monkeypatch.setattr(entropy, "system_entropy", lambda length: fixed)  # only Entitle looks it up by attribute
        signing_path = tmp_path / "s.signing-key"
        generate_key_pair(name="I", signing_key_path=signing_path, public_key_path=tmp_path / "p", passphrase=PASSPHRASE)
        assert json.loads(signing_path.read_text(encoding="utf-8"))["kdf"]["salt"] == fixed.hex()
        assert load_signing_key(signing_path, PASSPHRASE).key_id

    def test_a_failed_entropy_health_check_stops_key_generation_before_anything_is_written(self, tmp_path, monkeypatch):
        def failing(length):
            raise encryption.require().entropy.BrisartEntropyError("stuck source")

        monkeypatch.setattr(encryption.signatures(), "system_entropy", failing)
        with pytest.raises(ValueError, match="fresh entropy failed while generating a signing key"):
            generate_key_pair(name="I", signing_key_path=tmp_path / "s", public_key_path=tmp_path / "p", passphrase=PASSPHRASE)
        assert list(tmp_path.iterdir()) == []

    def test_a_signing_key_inside_a_git_working_tree_is_refused_unless_allowed(self, tmp_path):
        repository = tmp_path / "repo"
        (repository / ".git").mkdir(parents=True)
        arguments = dict(name="I", signing_key_path=repository / "keys" / "i.signing-key",
                         public_key_path=tmp_path / "i.public-key", passphrase=PASSPHRASE)
        with pytest.raises(ValueError, match="inside the Git working tree repo"):
            generate_key_pair(**arguments)
        assert not (repository / "keys").exists()
        generate_key_pair(**arguments, allow_in_repository=True)

    def test_a_damaged_public_key_file_is_named_not_trusted(self, keys, tmp_path):
        document = json.loads(keys[3].read_text(encoding="utf-8"))
        document["public_key"] = "00" + document["public_key"][2:]
        damaged = tmp_path / "damaged.public-key"
        damaged.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError, match="damaged: its key ID does not match"):
            load_public_key(damaged)
        for content in ("not json", "[1]", json.dumps({"format": "entitle.public-key.v1"})):
            damaged.write_text(content, encoding="utf-8")
            with pytest.raises(ValueError):
                load_public_key(damaged)

    def test_a_signing_key_file_can_serve_as_its_public_key_but_not_the_reverse(self, keys):
        assert load_public_key(keys[2]) == keys[1]
        with pytest.raises(ValueError, match="a public key cannot sign"):
            load_signing_key(keys[3], PASSPHRASE)

    def test_a_signing_key_whose_secret_does_not_match_its_public_key_is_refused(self, keys, tmp_path):
        other = make_keys(tmp_path / "other")
        document = json.loads(keys[2].read_text(encoding="utf-8"))
        swapped = {**json.loads(other[2].read_text(encoding="utf-8")),
                   "name": document["name"], "key_id": document["key_id"], "public_key": document["public_key"]}
        path = tmp_path / "swapped.signing-key"
        path.write_text(json.dumps(swapped), encoding="utf-8")
        with pytest.raises(EntitleError):
            load_signing_key(path, PASSPHRASE)

    def test_a_trust_list_keeps_each_key_once(self, keys):
        assert load_public_keys([keys[3], keys[3], keys[2]]) == [keys[1]]


class TestSignedDocuments:
    def test_round_trip_names_the_key_that_signed(self, keys):
        text = sign_document("checkpoint", {"n": 1, "é": "实"}, keys[0])
        assert text.startswith("-----BEGIN ENTITLE SIGNED CHECKPOINT-----\nAlgorithm: Ed25519\n")
        payload, signer = open_document(text, "checkpoint", [keys[1]])
        assert payload == {"n": 1, "é": "实"} and signer == keys[1]

    def test_signing_is_deterministic(self, keys):
        assert sign_document("checkpoint", {"n": 1}, keys[0]) == sign_document("checkpoint", {"n": 1}, keys[0])

    def _swap_body(self, text, payload_bytes):
        head, _, _ = text.partition("\n\n")
        encoded = base64.b64encode(payload_bytes).decode()
        return head + "\n\n" + encoded + "\n-----END ENTITLE SIGNED CHECKPOINT-----\n"

    def test_a_changed_payload_or_signature_is_signature_invalid(self, keys):
        text = sign_document("checkpoint", {"n": 1}, keys[0])
        with pytest.raises(SignatureRejected) as caught:
            open_document(self._swap_body(text, b'{"n":2}'), "checkpoint", [keys[1]])
        assert caught.value.reason == "signature_invalid"
        lines = text.split("\n")
        signature = bytearray(base64.b64decode(lines[3].split(": ")[1]))
        signature[0] ^= 1
        lines[3] = "Signature: " + base64.b64encode(bytes(signature)).decode()
        with pytest.raises(SignatureRejected) as caught:
            open_document("\n".join(lines), "checkpoint", [keys[1]])
        assert caught.value.reason == "signature_invalid"

    def test_an_untrusted_key_is_refused_by_name(self, keys, tmp_path):
        stranger = make_keys(tmp_path, name="Stranger")
        with pytest.raises(SignatureRejected) as caught:
            open_document(sign_document("checkpoint", {"n": 1}, stranger[0]), "checkpoint", [keys[1]])
        assert caught.value.reason == "unknown_signing_key"
        payload, signer = open_document(sign_document("checkpoint", {"n": 1}, stranger[0]), "checkpoint",
                                        [keys[1], stranger[1]])
        assert signer.name == "Stranger"

    def test_a_signature_cannot_be_replayed_as_another_kind_of_document(self, keys):
        text = sign_document("revocation-list", {"n": 1}, keys[0])
        relabelled = text.replace("REVOCATION LIST", "CHECKPOINT")
        with pytest.raises(SignatureRejected) as caught:
            open_document(relabelled, "checkpoint", [keys[1]])
        assert caught.value.reason == "signature_invalid"
        with pytest.raises(SignatureRejected) as caught:
            open_document(text, "checkpoint", [keys[1]])
        assert caught.value.reason == "not_signed_document"

    @pytest.mark.parametrize("damage", [
        lambda t: t.replace("Algorithm: Ed25519", "Algorithm: RSA"),
        lambda t: t.replace("Algorithm: Ed25519\n", "Algorithm: Ed25519\nAlgorithm: Ed25519\n"),
        lambda t: t.replace("Key-Id", "Key-Name"),
        lambda t: t.replace("\n\n", "\n"),
        lambda t: t.replace("-----END ENTITLE SIGNED CHECKPOINT-----", ""),
        lambda t: t.replace("\n\n", "\n\n!!!!"),
        lambda t: "",
    ])
    def test_damaged_armor_is_not_a_signed_document(self, keys, damage):
        with pytest.raises(SignatureRejected) as caught:
            open_document(damage(sign_document("checkpoint", {"n": 1}, keys[0])), "checkpoint", [keys[1]])
        assert caught.value.reason == "not_signed_document"

    def test_a_signed_payload_that_is_not_an_object_is_payload_invalid(self, keys, monkeypatch):
        monkeypatch.setattr(signing, "canonical_json", lambda payload: b"[1, 2]")
        text = sign_document("checkpoint", {"n": 1}, keys[0])
        monkeypatch.undo()
        with pytest.raises(SignatureRejected) as caught:
            open_document(text, "checkpoint", [keys[1]])
        assert caught.value.reason == "payload_invalid"

    def test_windows_line_endings_still_verify(self, keys):
        text = sign_document("checkpoint", {"n": 1}, keys[0]).replace("\n", "\r\n")
        assert open_document(text, "checkpoint", [keys[1]])[0] == {"n": 1}

    def test_an_empty_trust_list_is_a_usage_error_not_a_denial(self, keys):
        with pytest.raises(ValueError, match="no public key"):
            open_document(sign_document("checkpoint", {"n": 1}, keys[0]), "checkpoint", [])

    def test_peek_shows_the_payload_without_trusting_it(self, keys, tmp_path):
        stranger = make_keys(tmp_path, name="Stranger")
        payload, key_id = peek_document(sign_document("checkpoint", {"n": 1}, stranger[0]), "checkpoint")
        assert payload == {"n": 1} and key_id == stranger[1].key_id
