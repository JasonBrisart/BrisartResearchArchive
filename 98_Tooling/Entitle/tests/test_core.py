import datetime

import pytest

from entitle.core import (
    EntitleError,
    EntitlementDenied,
    EntitlementResult,
    canonical_json,
    evaluate_payload,
    load_entitlement_payload,
    make_entitlement_payload,
    parse_iso_datetime,
)


def _future_iso():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()


def _past_iso():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()


class TestCanonicalJson:
    def test_round_trip_matches_load(self):
        payload = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
        encoded = canonical_json(payload)
        assert load_entitlement_payload(encoded) == payload

    def test_output_is_deterministic_key_order(self):
        first = canonical_json({"b": 1, "a": 2})
        second = canonical_json({"a": 2, "b": 1})
        assert first == second

    def test_load_invalid_bytes_raises_entitle_error(self):
        with pytest.raises(EntitleError):
            load_entitlement_payload(b"{not-json")


class TestParseIsoDatetime:
    def test_none_or_empty_returns_none(self):
        assert parse_iso_datetime(None) is None
        assert parse_iso_datetime("") is None

    def test_z_suffix_is_normalized_to_utc_offset(self):
        parsed = parse_iso_datetime("2026-01-01T00:00:00Z")
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == datetime.timedelta(0)

    def test_naive_datetime_is_assumed_utc(self):
        parsed = parse_iso_datetime("2026-01-01T00:00:00")
        assert parsed.tzinfo is not None


class TestMakeEntitlementPayload:
    def test_defaults_rights_and_metadata_to_empty_dict(self):
        payload = make_entitlement_payload(
            issuer_id="issuer",
            subject_id="subject",
            product_id="product",
            entitlement_id="ent-1",
            rights=None,
            issued_at="2026-01-01T00:00:00Z",
        )
        assert payload["rights"] == {}
        assert payload["metadata"] == {}
        assert payload["format"] == "entitle.entitlement.v1"

    def test_expires_at_defaults_to_none(self):
        payload = make_entitlement_payload(
            issuer_id="i", subject_id="s", product_id="p",
            entitlement_id="e", rights={}, issued_at="2026-01-01T00:00:00Z",
        )
        assert payload["expires_at"] is None


class TestEvaluatePayload:
    def _valid_payload(self, **overrides):
        payload = make_entitlement_payload(
            issuer_id="issuer",
            subject_id="subject",
            product_id="EntitleDemo",
            entitlement_id="ent-1",
            rights={"can_run": True},
            issued_at="2026-01-01T00:00:00Z",
        )
        payload.update(overrides)
        return payload

    def test_valid_payload_is_allowed(self):
        result = evaluate_payload(self._valid_payload(), expected_product_id="EntitleDemo")
        assert result.allowed is True
        assert result.reason == "verified"

    def test_wrong_format_is_denied(self):
        payload = self._valid_payload(format="wrong.format")
        result = evaluate_payload(payload, expected_product_id="EntitleDemo")
        assert result.allowed is False
        assert result.reason == "unsupported_entitlement_format"

    def test_wrong_product_id_is_denied(self):
        result = evaluate_payload(self._valid_payload(), expected_product_id="OtherProduct")
        assert result.allowed is False
        assert result.reason == "wrong_product"

    def test_no_expected_product_id_skips_product_check(self):
        result = evaluate_payload(self._valid_payload(), expected_product_id=None)
        assert result.allowed is True

    def test_expired_entitlement_is_denied(self):
        payload = self._valid_payload(expires_at=_past_iso())
        result = evaluate_payload(payload, expected_product_id="EntitleDemo")
        assert result.allowed is False
        assert result.reason == "entitlement_expired"

    def test_future_expiration_is_allowed(self):
        payload = self._valid_payload(expires_at=_future_iso())
        result = evaluate_payload(payload, expected_product_id="EntitleDemo")
        assert result.allowed is True

    def test_invalid_expiration_timestamp_is_denied(self):
        payload = self._valid_payload(expires_at="not-a-timestamp")
        result = evaluate_payload(payload, expected_product_id="EntitleDemo")
        assert result.allowed is False
        assert result.reason == "invalid_expiration_timestamp"


class TestEntitlementResult:
    def test_denied_result_has_no_rights(self):
        result = EntitlementResult.denied_result("some_reason")
        assert result.allowed is False
        assert result.rights == {}
        assert result.has_right("can_run") is False

    def test_allowed_result_exposes_rights(self):
        payload = {"rights": {"can_run": True, "deployment_limit": 2}}
        result = EntitlementResult.allowed_result(payload)
        assert result.has_right("can_run") is True
        assert result.get_limit("deployment_limit") == 2
        assert result.get_limit("missing_limit", default=99) == 99

    def test_require_right_raises_when_denied(self):
        result = EntitlementResult.denied_result("denied_reason")
        with pytest.raises(EntitlementDenied):
            result.require_right("can_run")

    def test_require_right_raises_when_right_missing(self):
        result = EntitlementResult.allowed_result({"rights": {"can_run": True}})
        with pytest.raises(EntitlementDenied):
            result.require_right("can_modify")

    def test_require_right_passes_when_granted(self):
        result = EntitlementResult.allowed_result({"rights": {"can_modify": True}})
        assert result.require_right("can_modify") is True

    def test_to_dict_contains_expected_fields(self):
        payload = {
            "issuer_id": "issuer", "subject_id": "subject",
            "product_id": "product", "entitlement_id": "ent-1",
            "rights": {"can_run": True},
        }
        result = EntitlementResult.allowed_result(payload)
        as_dict = result.to_dict()
        assert as_dict["issuer_id"] == "issuer"
        assert as_dict["rights"] == {"can_run": True}
        assert as_dict["allowed"] is True
