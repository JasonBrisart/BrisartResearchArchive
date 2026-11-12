"""
File: tests/test_rights.py

Purpose
-------
Verify the entitlement rules in entitle/rights.py: how a payload and its rights are built, how a
  payload is loaded and judged (format, product, expiry, including an expiry given as a date
  alone; and for signed payloads issuer, subject, not-before, a clock behind the issue time and
  machine binding), and what an EntitlementResult grants and refuses, including that only true
  grants a right.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError) and entitle/rights.py. Needs no files, no encryption
  and no record log. The shared helpers are tested in tests/test_common.py. Run by pytest;
  nothing imports it.

Settings / parameters
---------------------
Expiry tests use timestamps one day either side of now, so they do not depend on the date the
  suite runs. Payloads are built in memory with the demo identity.

Edge cases
----------
Covers an expiry without a zone (read as UTC), a trailing Z, an unparseable expiry, a date-only
  expiry (start of that day, so today's date is already expired), an unsupported format and a
  wrong product, each denied with its own reason; payload bytes that are not JSON or decode to
  something other than an object; and require_right on a denied result and on a right that was
  not granted.

Known limitations
-----------------
Does not cover sealed files (tests/test_entitlements.py) or a machine with a wrong clock.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_rights.py
"""

import datetime

import pytest

from entitle.common import EntitleError
from entitle.rights import (
    EntitlementDenied,
    EntitlementResult,
    evaluate_payload,
    load_entitlement_payload,
    make_entitlement_payload,
    make_rights,
    parse_iso_datetime,
)


def _future_iso():
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()


def _past_iso():
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()


def _today(days=0):
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).date().isoformat()


class TestLoadPayload:
    def test_a_payload_round_trips(self):
        assert load_entitlement_payload(b'{"a": 1}') == {"a": 1}

    def test_load_invalid_bytes_raises_entitle_error(self):
        with pytest.raises(EntitleError):
            load_entitlement_payload(b"{not-json")

    def test_json_that_is_not_an_object_is_not_a_payload(self):
        for raw in (b"[1, 2]", b"42", b'"text"', b"null"):
            with pytest.raises(EntitleError, match="not a JSON object"):
                load_entitlement_payload(raw)


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

    def test_a_date_alone_is_the_start_of_that_day_in_utc(self):
        assert parse_iso_datetime("2026-12-31") == datetime.datetime(2026, 12, 31, tzinfo=datetime.timezone.utc)


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

    def test_a_date_alone_expires_at_the_start_of_that_day(self):
        # Documented behavior, pinned because it surprises people: "2026-12-31" is 00:00 UTC.
        for days, allowed in ((-1, False), (0, False), (1, True)):
            result = evaluate_payload(self._valid_payload(expires_at=_today(days)), expected_product_id="EntitleDemo")
            assert result.allowed is allowed, (days, result.reason)

    def test_a_time_on_the_last_day_includes_the_whole_day(self):
        payload = self._valid_payload(expires_at=_today(1) + "T23:59:59Z")
        assert evaluate_payload(payload, expected_product_id="EntitleDemo").allowed is True


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


class TestMakeRights:
    def test_defaults_grant_only_running(self):
        rights = make_rights()
        assert rights["can_run"] is True
        assert [rights[name] for name in (
            "can_use_enterprise_features", "can_modify", "can_fork", "can_export_source", "can_redistribute",
        )] == [False] * 5
        assert rights["deployment_limit"] == 1
        assert rights["support_tier"] == "standard"

    def test_each_flag_grants_its_right(self):
        rights = make_rights(enterprise=True, modify=True, fork=True, export_source=True, redistribute=True,
                             deployment_limit=None, support_tier="gold")
        assert all(rights[name] for name in (
            "can_use_enterprise_features", "can_modify", "can_fork", "can_export_source", "can_redistribute",
        ))
        assert rights["deployment_limit"] is None and rights["support_tier"] == "gold"


class TestSignedPayloadRules:
    NOW = datetime.datetime(2027, 6, 1, 12, 0, tzinfo=datetime.timezone.utc)

    def _payload(self, **overrides):
        payload = make_entitlement_payload(
            issuer_id="issuer", subject_id="lab", product_id="Demo", entitlement_id="e-1",
            rights=make_rights(modify=True), issued_at="2027-06-01T00:00:00+00:00", signed=True,
        )
        payload.update(overrides)
        return payload

    def _judge(self, payload, **expected):
        return evaluate_payload(payload, expected_product_id="Demo", now=self.NOW, **expected)

    def test_a_signed_payload_is_format_v2_and_is_allowed(self):
        payload = self._payload()
        assert payload["format"] == "entitle.entitlement.v2" and payload["machines"] == []
        assert self._judge(payload, expected_issuer_id="issuer", expected_subject_id="lab").allowed

    def test_the_issuer_and_subject_are_checked_when_expected(self):
        assert self._judge(self._payload(), expected_issuer_id="x").reason == "wrong_issuer"
        assert self._judge(self._payload(), expected_subject_id="x").reason == "wrong_subject"

    def test_not_before_and_a_clock_behind_the_issue_time(self):
        assert self._judge(self._payload(not_before="2027-06-02T00:00:00Z")).reason == "entitlement_not_yet_valid"
        assert self._judge(self._payload(not_before="soon")).reason == "invalid_not_before_timestamp"
        assert self._judge(self._payload(issued_at="2027-06-01T13:00:00Z")).reason == "clock_before_issue_time"
        assert self._judge(self._payload(issued_at="2027-06-01T12:04:00Z")).allowed  # inside the 5 minute skew

    def test_machine_binding(self):
        bound = self._payload(machines=["m1:" + "a" * 32])
        assert self._judge(bound, machine_id="m1:" + "a" * 32).allowed
        assert self._judge(bound, machine_id="m1:" + "b" * 32).reason == "machine_not_authorized"
        assert self._judge(bound).reason == "machine_not_authorized"
        assert self._judge(self._payload(machines="m1:x")).reason == "invalid_machine_binding"

    def test_a_right_is_granted_only_by_true_not_by_anything_truthy(self):
        result = EntitlementResult.allowed_result({"rights": {"can_modify": "yes", "can_fork": 1, "can_run": True}})
        assert not result.has_right("can_modify") and not result.has_right("can_fork") and result.has_right("can_run")
        assert self._judge(self._payload(rights=["can_run"])).reason == "invalid_rights"

    def test_shared_key_payloads_cannot_carry_signed_only_fields(self):
        with pytest.raises(ValueError, match="need a signed entitlement"):
            make_entitlement_payload(issuer_id="i", subject_id="s", product_id="p", entitlement_id="e", rights={},
                                     issued_at="2027-01-01T00:00:00Z", machines=["m1:" + "a" * 32])
