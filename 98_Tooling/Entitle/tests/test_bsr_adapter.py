import pytest

from entitle.bsr_adapter import (
    EntitleBSRError,
    load_protected_entitlement,
    make_context,
    open_entitlement_envelope,
    protect_entitlement_payload,
    save_protected_entitlement,
    verify_protected_entitlement,
)
from entitle.core import make_entitlement_payload

MASTER_KEY = b"change-this-master-key-change-this-master-key!"
DRBG_SEED = b"a" * 64
DRBG_PERSONALIZATION = b"EntitleTestPersonalization"


def _sample_payload(**overrides):
    payload = make_entitlement_payload(
        issuer_id="JasonBrisart",
        subject_id="ResearchLabA",
        product_id="EntitleDemo",
        entitlement_id="ent-1",
        rights={"can_run": True, "deployment_limit": 1},
        issued_at="2026-01-01T00:00:00Z",
    )
    payload.update(overrides)
    return payload


class TestMakeContext:
    def test_context_is_deterministic_for_same_inputs(self):
        first = make_context("EntitleDemo", "JasonBrisart", "ResearchLabA")
        second = make_context("EntitleDemo", "JasonBrisart", "ResearchLabA")
        assert first == second

    def test_context_changes_with_any_field(self):
        base = make_context("EntitleDemo", "JasonBrisart", "ResearchLabA")
        different_product = make_context("OtherProduct", "JasonBrisart", "ResearchLabA")
        different_issuer = make_context("EntitleDemo", "OtherIssuer", "ResearchLabA")
        different_subject = make_context("EntitleDemo", "JasonBrisart", "OtherLab")
        assert base != different_product
        assert base != different_issuer
        assert base != different_subject


class TestProtectAndOpenEnvelope:
    def test_round_trip_recovers_original_payload(self):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload,
            master_key=MASTER_KEY,
            drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        recovered = open_entitlement_envelope(
            envelope=envelope,
            master_key=MASTER_KEY,
            expected_product_id="EntitleDemo",
            issuer_id="JasonBrisart",
            subject_id="ResearchLabA",
        )
        assert recovered == payload

    def test_wrong_master_key_returns_none(self):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        wrong_key = b"wrong-key-wrong-key-wrong-key-wrong-key!!!!"
        recovered = open_entitlement_envelope(
            envelope=envelope, master_key=wrong_key,
            expected_product_id="EntitleDemo", issuer_id="JasonBrisart", subject_id="ResearchLabA",
        )
        assert recovered is None

    def test_wrong_context_fields_return_none(self):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        recovered = open_entitlement_envelope(
            envelope=envelope, master_key=MASTER_KEY,
            expected_product_id="WrongProduct", issuer_id="JasonBrisart", subject_id="ResearchLabA",
        )
        assert recovered is None

    def test_tampered_envelope_returns_none_not_an_exception(self):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        tampered = dict(envelope)
        tampered["ciphertext"] = ("0" * len(tampered["ciphertext"]))
        recovered = open_entitlement_envelope(
            envelope=tampered, master_key=MASTER_KEY,
            expected_product_id="EntitleDemo", issuer_id="JasonBrisart", subject_id="ResearchLabA",
        )
        assert recovered is None


class TestFileRoundTrip:
    def test_save_and_load_protected_entitlement(self, tmp_path):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        out_path = tmp_path / "entitlements" / "lab_a.entitle"
        save_protected_entitlement(envelope, out_path)
        assert out_path.exists()
        loaded = load_protected_entitlement(out_path)
        assert loaded == envelope

    def test_verify_protected_entitlement_end_to_end(self, tmp_path):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        out_path = tmp_path / "lab_a.entitle"
        save_protected_entitlement(envelope, out_path)
        result = verify_protected_entitlement(
            path=out_path,
            master_key=MASTER_KEY,
            expected_product_id="EntitleDemo",
            issuer_id="JasonBrisart",
            subject_id="ResearchLabA",
        )
        assert result.allowed is True
        assert result.has_right("can_run") is True

    def test_verify_protected_entitlement_denies_on_bsr_failure(self, tmp_path):
        payload = _sample_payload()
        envelope = protect_entitlement_payload(
            payload=payload, master_key=MASTER_KEY, drbg_seed=DRBG_SEED,
            drbg_personalization=DRBG_PERSONALIZATION,
        )
        out_path = tmp_path / "lab_a.entitle"
        save_protected_entitlement(envelope, out_path)
        wrong_key = b"wrong-key-wrong-key-wrong-key-wrong-key!!!!"
        result = verify_protected_entitlement(
            path=out_path,
            master_key=wrong_key,
            expected_product_id="EntitleDemo",
            issuer_id="JasonBrisart",
            subject_id="ResearchLabA",
        )
        assert result.allowed is False
        assert result.reason == "bsr_verification_failed"


class TestEncryptionFailureWrapping:
    def test_protect_entitlement_payload_wraps_bsr_failures(self):
        payload = _sample_payload()
        with pytest.raises(EntitleBSRError):
            protect_entitlement_payload(
                payload=payload,
                master_key=b"too-short",  # BSR2 requires >= 32 bytes
                drbg_seed=DRBG_SEED,
                drbg_personalization=DRBG_PERSONALIZATION,
            )
