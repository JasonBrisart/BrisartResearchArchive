"""
File: tests/test_entitlements.py

Purpose
-------
Verify the .entitle file and everything done with one, through entitle/entitlements.py: the
  encryption context is pinned, sealing and opening round-trip in the current format, every
  mismatch or modification is refused without an exception, files are written in one step,
  issuing refuses inputs that could never work, verification denies with the right reason,
  files written by Entitle before 0.5.0 (BSR2 Alpha 3) still verify, and migration keeps the
  entitlement exactly as issued and never damages the original.

Communication / relationships
-----------------------------
Imports the entitle package root (EntitleError, canonical_json), entitle/encryption.py
  (require, EncryptionNotFoundError, EncryptionLink), entitle/entitlements.py, entitle/rights.py
  (make_entitlement_payload) and tests/support.py. Uses
  tests/fixtures/legacy_alpha3_entitlement.json, an envelope sealed with the copy of BSR2 Alpha 3
  that Entitle carried before 0.5.0. Needs 97_Encryption beside 98_Tooling. Run by pytest;
  nothing imports it.

Settings / parameters
---------------------
Files are written to pytest's tmp_path with the demo identity and key from tests/support.py.
  Expiry tests use timestamps a day either side of now. Tests that need a previous-format file
  for a particular payload seal one with the linked library's envelope module.

Edge cases
----------
Covers a wrong key, issuer, subject or product, a modified or truncated file, a payload over
  the 64 KiB cap, a payload that is not a JSON object, text and bytes keys, a key over 1024
  bytes, short keys, seeds and personalizations, every combination of the optional generator
  inputs, a missing file, a file that is neither format, a failed replacement, an unparseable
  expiry, a negative or non-integer limit, a blank ID, a zero limit, an expired entitlement, a
  missing 97_Encryption (an error, never a denial), and migration of a previous-format file, a
  current file, a file that does not open, a copy that does not reopen to the same payload, and
  an expired entitlement.

Known limitations
-----------------
The previous-format fixture stands in for files issued by real installations of Entitle
  before 0.5.0, which this suite does not have. Does not test BSR2 itself, the command line
  (tests/test_cli.py) or deployment rules (tests/test_tracking.py).

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_entitlements.py
"""

import datetime
import json
import shutil
from pathlib import Path

import pytest

from entitle import EntitleError, canonical_json, encryption, entitlements
from entitle.encryption import EncryptionNotFoundError
from entitle.entitlements import (
    ARMOR_BEGIN,
    EntitleBSRError,
    is_previous_encryption,
    issue_entitlement,
    make_context,
    migrate_entitlement,
    open_entitlement,
    read_entitlement_file,
    seal_entitlement,
    uses_previous_encryption,
    verify_entitlement,
    write_entitlement_file,
)
from entitle.rights import make_entitlement_payload
from support import (
    DRBG_PERSONALIZATION, DRBG_SEED, ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PRODUCT, SUBJECT, issue_demo,
)

WRONG_KEY = "wrong-key-wrong-key-wrong-key-wrong-key"


def _verify(path, **overrides):
    args = dict(issuer=ISSUER, subject=SUBJECT, product=PRODUCT, master_key=MASTER_KEY, path=path)
    args.update(overrides)
    return verify_entitlement(**args)


def _iso(days):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).isoformat()


def _payload(**overrides):
    payload = make_entitlement_payload(
        issuer_id=ISSUER,
        subject_id=SUBJECT,
        product_id=PRODUCT,
        entitlement_id="ent-1",
        rights={"can_run": True, "deployment_limit": 1},
        issued_at="2026-01-01T00:00:00Z",
    )
    payload.update(overrides)
    return payload


def _open(text, **overrides):
    args = dict(master_key=MASTER_KEY, issuer=ISSUER, subject=SUBJECT, product=PRODUCT)
    args.update(overrides)
    return open_entitlement(text, **args)


class TestTheFileFormat:
    def test_the_context_changes_with_any_field(self):
        base = make_context("EntitleDemo", "JasonBrisart", "ResearchLabA")
        assert base == make_context("EntitleDemo", "JasonBrisart", "ResearchLabA")
        assert base not in (
            make_context("OtherProduct", "JasonBrisart", "ResearchLabA"),
            make_context("EntitleDemo", "OtherIssuer", "ResearchLabA"),
            make_context("EntitleDemo", "JasonBrisart", "OtherLab"),
        )

    def test_the_context_is_pinned_so_existing_entitlements_keep_verifying(self):
        assert make_context("EntitleDemo", "JasonBrisart", "ResearchLabA") == (
            '{"format":"entitle.entitlement.v1","issuer_id":"JasonBrisart","product_id":"EntitleDemo",'
            '"subject_id":"ResearchLabA","system":"Entitle"}'
        )


class TestSealAndOpen:
    def test_the_round_trip_recovers_the_payload_in_the_current_format(self):
        container = seal_entitlement(_payload(), master_key=MASTER_KEY)
        assert container.startswith(ARMOR_BEGIN) and not is_previous_encryption(container)
        recovered, previous = _open(container)
        assert recovered == _payload() and previous is False

    def test_the_file_is_the_sealed_v3_format_with_block_padding(self):
        bsr2 = encryption.require()
        sealed = bsr2.aead.dearmor(seal_entitlement(_payload(), master_key=MASTER_KEY))
        info = bsr2.aead.inspect_sealed(sealed)
        assert (info["suite"], info["format_version"], info["padding"]) == ("BSR2-S64-SIV", 3, "block")
        assert info["payload_bytes"] % bsr2.aead.PADDING_BLOCK_SIZE == 0

    def test_sealing_the_same_payload_twice_gives_different_files(self):
        first = seal_entitlement(_payload(), master_key=MASTER_KEY)
        assert first != seal_entitlement(_payload(), master_key=MASTER_KEY)

    @pytest.mark.parametrize("override", [
        {"master_key": "wrong-key-wrong-key-wrong-key-wrong-key"},
        {"master_key": "short"},
        {"product": "WrongProduct"},
        {"issuer": "OtherIssuer"},
        {"subject": "OtherLab"},
    ])
    def test_a_wrong_key_or_context_opens_as_none_not_an_exception(self, override):
        container = seal_entitlement(_payload(), master_key=MASTER_KEY)
        assert _open(container, **override)[0] is None

    def test_a_modified_or_truncated_file_opens_as_none(self):
        container = seal_entitlement(_payload(), master_key=MASTER_KEY)
        lines = container.splitlines()
        lines[2] = ("0" if lines[2][0] != "0" else "1") + lines[2][1:]
        assert _open("\n".join(lines))[0] is None
        assert _open("\n".join(lines[:-3] + lines[-2:]))[0] is None

    def test_a_payload_over_the_size_cap_is_refused_without_being_decrypted(self):
        bsr2 = encryption.require()
        big = bsr2.aead.armor(bsr2.aead.seal(
            MASTER_KEY.encode(), b"{" + b" " * (entitlements.MAX_PAYLOAD_BYTES + 1) + b"}",
            make_context(PRODUCT, ISSUER, SUBJECT),
        ))
        assert _open(big)[0] is None

    def test_a_payload_that_is_not_a_json_object_opens_as_none(self):
        bsr2 = encryption.require()
        container = bsr2.aead.armor(bsr2.aead.seal(MASTER_KEY.encode(), b"[1, 2]", make_context(PRODUCT, ISSUER, SUBJECT)))
        assert _open(container)[0] is None

    def test_text_and_bytes_keys_are_interchangeable(self):
        container = seal_entitlement(_payload(), master_key=MASTER_KEY.encode(), drbg_seed=DRBG_SEED.encode(),
            drbg_personalization=DRBG_PERSONALIZATION.encode(),
        )
        assert _open(container, master_key=MASTER_KEY)[0] == _payload()


    def test_a_key_over_the_maximum_is_refused(self):
        with pytest.raises(EntitleBSRError, match="at most 1024 bytes"):
            seal_entitlement(_payload(), master_key="k" * 1025)

    def test_the_generator_options_are_optional_independently_and_both_open(self):
        for options in (
            {},
            {"drbg_seed": DRBG_SEED},
            {"drbg_personalization": DRBG_PERSONALIZATION},
            {"drbg_seed": DRBG_SEED, "drbg_personalization": DRBG_PERSONALIZATION},
            {"drbg_seed": "", "drbg_personalization": ""},
        ):
            container = seal_entitlement(_payload(), master_key=MASTER_KEY, **options)
            assert _open(container)[0] == _payload(), options

class TestFiles:
    def test_save_then_load_round_trips_and_leaves_no_temporary_file(self, tmp_path):
        container = seal_entitlement(_payload(), master_key=MASTER_KEY)
        path = tmp_path / "entitlements" / "lab.entitle"
        write_entitlement_file(container, path)
        assert read_entitlement_file(path) == container.strip()
        assert [p.name for p in path.parent.iterdir()] == ["lab.entitle"]

    def test_saving_replaces_the_old_file_in_one_step(self, tmp_path, monkeypatch):
        path = tmp_path / "lab.entitle"
        path.write_text("old content", encoding="utf-8")
        monkeypatch.setattr(entitlements.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError, match="disk full"):
            write_entitlement_file(ARMOR_BEGIN + "\nnew\n", path)
        assert path.read_text(encoding="utf-8") == "old content"
        assert [p.name for p in tmp_path.iterdir()] == ["lab.entitle"]

    @pytest.mark.parametrize("text", ["this is not an entitlement", "", "[1, 2]", "\x00\x01"])
    def test_a_file_that_is_neither_format_is_a_value_error_naming_it(self, tmp_path, text):
        path = tmp_path / "bad.entitle"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError, match="bad.entitle is not a protected Entitle entitlement file"):
            read_entitlement_file(path)


class TestWithoutTheLink:
    def test_an_unavailable_link_is_an_error_never_a_denied_entitlement(self, monkeypatch):
        unavailable = encryption.EncryptionLink(available=False, location=encryption.ENCRYPTION_DIR, problem="gone")
        monkeypatch.setattr(encryption, "status", lambda: unavailable)
        with pytest.raises(EncryptionNotFoundError):
            _open("{}")
        with pytest.raises(EncryptionNotFoundError):
            seal_entitlement(_payload(), master_key=MASTER_KEY)


class TestRoundTrip:
    def test_issued_rights_and_limits_are_what_verify_reports(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, entitlement_id="lab-1", modify=True, fork=True, deployment_limit=3, support_tier="gold")
        result = _verify(path)
        assert result.allowed and result.reason == "verified"
        assert result.has_right("can_run") and result.has_right("can_modify") and result.has_right("can_fork")
        assert not result.has_right("can_redistribute") and not result.has_right("can_export_source")
        assert result.get_limit("deployment_limit") == 3 and result.rights["support_tier"] == "gold"
        assert (result.payload["entitlement_id"], result.payload["issuer_id"]) == ("lab-1", ISSUER)

    def test_issue_returns_the_plaintext_payload_and_creates_missing_folders(self, tmp_path):
        path = tmp_path / "a" / "b" / "lab.entitle"
        payload = issue_demo(path)
        assert path.is_file() and payload["format"] == "entitle.entitlement.v1"
        assert "ciphertext" not in payload
        text = path.read_text(encoding="utf-8")
        assert text.startswith("-----BEGIN BSR2 SEALED MESSAGE-----\n") and text.endswith("-----END BSR2 SEALED MESSAGE-----\n")
        assert not is_previous_encryption(text)

    def test_the_protected_file_does_not_contain_the_plaintext(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, entitlement_id="visible-only-in-memory-123")
        assert "visible-only-in-memory-123" not in path.read_text(encoding="utf-8")

    def test_issuing_needs_no_generator_options(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_entitlement(issuer=ISSUER, subject=SUBJECT, product=PRODUCT, entitlement_id="e", output=path,
                          master_key=MASTER_KEY)
        assert _verify(path).allowed

    def test_the_payload_records_the_current_protection(self, tmp_path):
        assert issue_demo(tmp_path / "lab.entitle")["metadata"]["protection"] == "BSR2-S64-SIV sealed message"


class TestDenials:
    @pytest.mark.parametrize("override", [
        {"master_key": WRONG_KEY},
        {"issuer": "OtherIssuer"},
        {"subject": "OtherLab"},
        {"product": "OtherProduct"},
    ])
    def test_any_mismatch_is_denied_as_a_failed_verification(self, tmp_path, override):
        path = tmp_path / "lab.entitle"
        issue_demo(path)
        result = _verify(path, **override)
        assert (result.allowed, result.reason) == (False, "bsr_verification_failed")
        assert not result.has_right("can_run")

    def test_a_modified_file_is_denied(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        lines[2] = ("0" if lines[2][0] != "0" else "1") + lines[2][1:]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert _verify(path).reason == "bsr_verification_failed"

    def test_an_expired_entitlement_is_denied_as_expired(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, expires=_iso(-1))
        assert _verify(path).reason == "entitlement_expired"

    def test_a_future_expiry_is_allowed(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, expires=_iso(1))
        assert _verify(path).allowed

    def test_an_entitlement_that_could_never_work_is_refused_before_anything_is_written(self, tmp_path):
        path = tmp_path / "lab.entitle"
        for bad in ({"expires": "next tuesday"}, {"deployment_limit": -1}, {"deployment_limit": "3"},
                    {"deployment_limit": True}, {"entitlement_id": ""}):
            with pytest.raises(ValueError):
                issue_demo(path, **bad)
        assert not path.exists()

    def test_a_zero_limit_verifies_but_permits_no_deployment(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, deployment_limit=0)
        result = _verify(path)
        assert result.allowed and result.get_limit("deployment_limit") == 0


class TestFilesAndMinimums:
    def test_a_missing_file_raises_instead_of_looking_like_a_denial(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _verify(tmp_path / "nope.entitle")

    def test_a_json_file_that_is_not_an_envelope_is_denied(self, tmp_path):
        path = tmp_path / "odd.entitle"
        path.write_text('{"hello": "world"}', encoding="utf-8")
        assert _verify(path).reason == "bsr_verification_failed"

    @pytest.mark.parametrize("override,reason", [
        ({"master_key": "short"}, "master key must contain at least 32 bytes"),
        ({"drbg_seed": "short"}, "seed must contain at least 64 bytes"),
        ({"drbg_personalization": "short"}, "personalization must contain at least 16 bytes"),
    ])
    def test_bsr_minimums_are_reported_with_their_reason(self, tmp_path, override, reason):
        args = dict(issuer=ISSUER, subject=SUBJECT, product=PRODUCT, entitlement_id="e", master_key=MASTER_KEY,
                    drbg_seed=DRBG_SEED, drbg_personalization=DRBG_PERSONALIZATION, output=tmp_path / "x.entitle")
        args.update(override)
        with pytest.raises(EntitleBSRError, match=reason) as caught:
            issue_entitlement(**args)
        assert isinstance(caught.value, EntitleError)
        assert not (tmp_path / "x.entitle").exists()


class TestFilesWrittenByThePreviousEncryption:
    def _copy(self, tmp_path):
        path = tmp_path / "legacy.entitle"
        shutil.copyfile(LEGACY_ENTITLEMENT, path)
        return path

    def test_the_previous_release_file_still_verifies_with_its_rights(self, tmp_path):
        path = self._copy(tmp_path)
        result = _verify(path)
        assert result.allowed
        assert result.payload["entitlement_id"] == "lab-a-demo-001"
        assert result.get_limit("deployment_limit") == 2
        assert result.has_right("can_modify") and result.has_right("can_fork")
        assert uses_previous_encryption(path) is True

    def test_a_file_issued_now_is_not_previous_encryption(self, tmp_path):
        issue_demo(tmp_path / "lab.entitle")
        assert uses_previous_encryption(tmp_path / "lab.entitle") is False

    def test_the_previous_release_file_is_denied_like_any_other_on_a_mismatch(self, tmp_path):
        path = self._copy(tmp_path)
        assert _verify(path, master_key=WRONG_KEY).reason == "bsr_verification_failed"
        assert _verify(path, product="Other").reason == "bsr_verification_failed"
        path.write_text(path.read_text(encoding="utf-8")[:-40], encoding="utf-8")
        assert _verify(path).reason == "bsr_verification_failed"

    def test_the_previous_format_is_the_alpha_3_json_envelope_and_is_recognised(self):
        text = read_entitlement_file(LEGACY_ENTITLEMENT)
        envelope = json.loads(text)
        assert (envelope["algorithm"], envelope["version"]) == ("BSR2-ARX-SPONGE-ETM", 2)
        assert is_previous_encryption(text) and _open(text)[1] is True


class TestMigrate:
    def _migrate(self, path, **overrides):
        args = dict(issuer=ISSUER, subject=SUBJECT, product=PRODUCT, master_key=MASTER_KEY, path=path)
        args.update(overrides)
        return migrate_entitlement(**args)

    def _legacy(self, tmp_path):
        path = tmp_path / "legacy.entitle"
        shutil.copyfile(LEGACY_ENTITLEMENT, path)
        return path

    def test_migrating_reseals_the_same_entitlement_in_the_current_format(self, tmp_path):
        path = self._legacy(tmp_path)
        before = _verify(path).payload
        outcome = self._migrate(path)
        assert outcome == {"migrated": True, "reason": "migrated", "entitlement_id": "lab-a-demo-001"}
        assert uses_previous_encryption(path) is False
        after = _verify(path)
        assert after.allowed and after.payload == before
        assert [p.name for p in tmp_path.iterdir()] == ["legacy.entitle"]

    def test_migrating_keeps_rights_expiry_and_issue_time_exactly(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path, entitlement_id="lab-9", expires=_iso(30), deployment_limit=4, redistribute=True)
        payload = _verify(path).payload
        legacy = tmp_path / "old.entitle"
        legacy.write_text(self._previous_format(payload), encoding="utf-8")
        assert uses_previous_encryption(legacy)
        self._migrate(legacy)
        migrated = _verify(legacy).payload
        assert migrated == payload and migrated["issued_at"] == payload["issued_at"]

    def _previous_format(self, payload):
        bsr2 = encryption.require()
        drbg = bsr2.drbg.BrisartDRBG(DRBG_SEED.encode(), DRBG_PERSONALIZATION.encode())
        envelope = bsr2.envelope.encrypt(
            MASTER_KEY.encode(), canonical_json(payload), make_context(PRODUCT, ISSUER, SUBJECT), drbg
        )
        return json.dumps(envelope, indent=2)

    def test_a_file_already_in_the_current_format_is_left_alone(self, tmp_path):
        path = tmp_path / "lab.entitle"
        issue_demo(path)
        before = path.read_bytes()
        assert self._migrate(path) == {"migrated": False, "reason": "already_current_encryption", "entitlement_id": None}
        assert path.read_bytes() == before

    @pytest.mark.parametrize("override", [{"master_key": WRONG_KEY}, {"issuer": "Other"}, {"subject": "Other"}, {"product": "Other"}])
    def test_a_file_that_does_not_open_for_the_given_values_is_not_touched(self, tmp_path, override):
        path = self._legacy(tmp_path)
        before = path.read_bytes()
        with pytest.raises(EntitleError, match="does not open with this issuer, subject, product and master key"):
            self._migrate(path, **override)
        assert path.read_bytes() == before

    def test_a_failed_replacement_leaves_the_original_file_working(self, tmp_path, monkeypatch):
        path = self._legacy(tmp_path)
        before = path.read_bytes()
        monkeypatch.setattr(entitlements.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError):
            self._migrate(path)
        monkeypatch.undo()
        assert path.read_bytes() == before and _verify(path).allowed

    def test_a_resealed_copy_that_does_not_open_to_the_same_payload_is_never_written(self, tmp_path, monkeypatch):
        path = self._legacy(tmp_path)
        before = path.read_bytes()
        good = entitlements.seal_entitlement
        monkeypatch.setattr(
            entitlements, "seal_entitlement",
            lambda payload, **kwargs: good({**payload, "entitlement_id": "changed"}, **kwargs),
        )
        with pytest.raises(EntitleError, match="did not open to the same entitlement"):
            self._migrate(path)
        assert path.read_bytes() == before

    def test_an_expired_entitlement_migrates_like_any_other(self, tmp_path):
        issued = tmp_path / "lab.entitle"
        issue_demo(issued, expires=_iso(-1))
        legacy = tmp_path / "old.entitle"
        legacy.write_text(self._previous_format(_payload_of(issued)), encoding="utf-8")
        assert self._migrate(legacy)["migrated"] is True
        assert _verify(legacy).reason == "entitlement_expired"


def _payload_of(path):
    bsr2 = encryption.require()
    sealed = bsr2.aead.dearmor(Path(path).read_text(encoding="utf-8"))
    return json.loads(bsr2.aead.unseal(
        MASTER_KEY.encode(), sealed, make_context(PRODUCT, ISSUER, SUBJECT)
    ))
