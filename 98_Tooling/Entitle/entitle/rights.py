"""
File: entitle/rights.py

Purpose
-------
Define what an entitlement says and how it is judged, independent of how it is stored or
  authenticated: the payload layout, the rights vocabulary, the denial reasons, and
  EntitlementResult, the object a protected program asks "is this right granted?". Nothing here
  reads files, touches cryptography or reads the clock except through common.utc_now;
  entitle/entitlements.py authenticates a file and hands the payload to evaluate_payload.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError, utc_now) and the standard library (datetime, json).
  Imported by entitle/entitlements.py (payload building, loading and evaluation, the format
  names) and examples/protected_app_example.py (EntitlementDenied). A protected program needs
  only EntitlementResult and EntitlementDenied from here. Covered by tests/test_rights.py.

Settings / parameters
---------------------
ENTITLEMENT_FORMAT ("entitle.entitlement.v1") marks a shared-key payload and is part of its
  encryption context, so it never changes; SIGNED_ENTITLEMENT_FORMAT ("entitle.entitlement.v2")
  marks a signed payload, which adds not_before and machines. make_rights builds the rights:
  can_run is always true; can_use_enterprise_features, can_modify, can_fork, can_export_source
  and can_redistribute default to false; deployment_limit defaults to 1 (None is unlimited);
  support_tier is a free label. CLOCK_SKEW_SECONDS (300) is how far the clock may sit behind the
  issue time. evaluate_payload(payload, expected_product_id, expected_issuer_id=,
  expected_subject_id=, machine_id=, now=) judges at now (default the clock).

Edge cases
----------
evaluate_payload never raises; it denies with one reason, checked in this order:
  unsupported_entitlement_format, wrong_issuer, wrong_subject, wrong_product (each only when
  expected), invalid_rights, clock_before_issue_time (the clock is over five minutes behind the
  issue time, a stateless sign of a clock wound back), invalid_not_before_timestamp,
  entitlement_not_yet_valid, invalid_expiration_timestamp, entitlement_expired,
  invalid_machine_binding, machine_not_authorized; otherwise it allows with reason "verified". An
  expiry without a zone is read as UTC; a date alone ("2026-12-31") is 00:00 UTC at the start of
  that day, so give a time to include the whole day. has_right is true only for a right whose
  value is exactly true, so "yes" or 1 never grants anything. make_entitlement_payload refuses
  not_before or machines on a shared-key payload. load_entitlement_payload raises EntitleError
  for bytes that are not UTF-8 JSON or not an object.

Known limitations
-----------------
Expiry is judged against the clock the caller passes or the local one; HostState in
  entitle/host.py is what remembers time across runs. Rights are flags and limits: Entitle does
  not know which rights a product enforces, and only deployment_limit is enforced by Entitle
  itself (entitle/tracking.py). Revocation is checked by entitle/entitlements.py, not here.

Examples
--------
From the directory containing run.py:

    from entitle.rights import (
        EntitlementDenied, evaluate_payload, make_entitlement_payload, make_rights,
    )

    payload = make_entitlement_payload(
        issuer_id="Issuer", subject_id="Lab", product_id="Demo", entitlement_id="e-1",
        issued_at="2026-01-01T00:00:00+00:00", rights=make_rights(modify=True), signed=True,
    )
    result = evaluate_payload(payload, expected_product_id="Demo", expected_issuer_id="Issuer")
    assert result.allowed and result.has_right("can_modify") and not result.has_right("can_fork")
    assert evaluate_payload(payload, expected_product_id="Other").reason == "wrong_product"
    try:
        result.require_right("can_fork")
    except EntitlementDenied as exc:
        assert str(exc) == "Required right not granted: can_fork"
"""

import datetime
import json

from .common import EntitleError, utc_now

ENTITLEMENT_FORMAT = "entitle.entitlement.v1"
SIGNED_ENTITLEMENT_FORMAT = "entitle.entitlement.v2"
SUPPORTED_FORMATS = (ENTITLEMENT_FORMAT, SIGNED_ENTITLEMENT_FORMAT)
CLOCK_SKEW_SECONDS = 300


class EntitlementDenied(EntitleError):
    """Raised when a required entitlement or right is unavailable."""


def parse_iso_datetime(value):
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def load_entitlement_payload(raw_bytes):
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise EntitleError("Invalid entitlement payload.") from exc
    if not isinstance(payload, dict):
        raise EntitleError("Invalid entitlement payload: not a JSON object.")
    return payload


def make_rights(
    *,
    enterprise=False,
    modify=False,
    fork=False,
    export_source=False,
    redistribute=False,
    deployment_limit=1,
    support_tier="standard",
):
    return {
        "can_run": True,
        "can_use_enterprise_features": enterprise,
        "can_modify": modify,
        "can_fork": fork,
        "can_export_source": export_source,
        "can_redistribute": redistribute,
        "deployment_limit": deployment_limit,
        "support_tier": support_tier,
    }


def make_entitlement_payload(
    *,
    issuer_id,
    subject_id,
    product_id,
    entitlement_id,
    rights,
    issued_at,
    expires_at=None,
    metadata=None,
    signed=False,
    not_before=None,
    machines=None,
):
    payload = {
        "format": SIGNED_ENTITLEMENT_FORMAT if signed else ENTITLEMENT_FORMAT,
        "issuer_id": issuer_id,
        "subject_id": subject_id,
        "product_id": product_id,
        "entitlement_id": entitlement_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "rights": rights or {},
        "metadata": metadata or {},
    }
    if signed:
        payload["not_before"] = not_before
        payload["machines"] = sorted(set(machines or []))
    elif not_before or machines:
        raise ValueError("not-before and machine binding need a signed entitlement (issue it with a signing key).")
    return payload


class EntitlementResult:
    def __init__(self, allowed, reason, payload=None, signed_by=None):
        self.allowed = allowed
        self.reason = reason
        self.payload = payload or {}
        self.signed_by = signed_by

    @classmethod
    def allowed_result(cls, payload):
        return cls(True, "verified", payload)

    @classmethod
    def denied_result(cls, reason, payload=None):
        return cls(False, reason, payload or {})

    @property
    def rights(self):
        return self.payload.get("rights", {})

    def has_right(self, right_name):
        if not self.allowed:
            return False
        return self.rights.get(right_name, False) is True

    def get_limit(self, limit_name, default=None):
        return self.rights.get(limit_name, default) if isinstance(self.rights, dict) else default

    def require_right(self, right_name):
        if not self.allowed:
            raise EntitlementDenied(f"Entitlement denied: {self.reason}")
        if not self.has_right(right_name):
            raise EntitlementDenied(f"Required right not granted: {right_name}")
        return True

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "issuer_id": self.payload.get("issuer_id"),
            "subject_id": self.payload.get("subject_id"),
            "product_id": self.payload.get("product_id"),
            "entitlement_id": self.payload.get("entitlement_id"),
            "rights": self.rights,
            "issued_at": self.payload.get("issued_at"),
            "not_before": self.payload.get("not_before"),
            "expires_at": self.payload.get("expires_at"),
            "machines": self.payload.get("machines") or [],
            "signed_by": self.signed_by,
        }


def _parsed(value):
    try:
        return parse_iso_datetime(value), True
    except (TypeError, ValueError, AttributeError):
        return None, False


def evaluate_payload(
    payload, expected_product_id=None, *, expected_issuer_id=None, expected_subject_id=None, machine_id=None, now=None
):
    """Judge a payload that has already been authenticated. Never raises; denies with one reason."""
    now = now or utc_now()
    deny = EntitlementResult.denied_result
    if payload.get("format") not in SUPPORTED_FORMATS:
        return deny("unsupported_entitlement_format", payload)
    if expected_issuer_id is not None and payload.get("issuer_id") != expected_issuer_id:
        return deny("wrong_issuer", payload)
    if expected_subject_id is not None and payload.get("subject_id") != expected_subject_id:
        return deny("wrong_subject", payload)
    if expected_product_id is not None and payload.get("product_id") != expected_product_id:
        return deny("wrong_product", payload)
    if not isinstance(payload.get("rights"), dict):
        return deny("invalid_rights", payload)
    issued_at, readable = _parsed(payload.get("issued_at"))
    if issued_at and now < issued_at - datetime.timedelta(seconds=CLOCK_SKEW_SECONDS):
        return deny("clock_before_issue_time", payload)
    not_before, readable = _parsed(payload.get("not_before"))
    if not readable:
        return deny("invalid_not_before_timestamp", payload)
    if not_before and now < not_before:
        return deny("entitlement_not_yet_valid", payload)
    expiration, readable = _parsed(payload.get("expires_at"))
    if not readable:
        return deny("invalid_expiration_timestamp", payload)
    if expiration and now > expiration:
        return deny("entitlement_expired", payload)
    machines = payload.get("machines") or []
    if not isinstance(machines, list):
        return deny("invalid_machine_binding", payload)
    if machines and machine_id not in machines:
        return deny("machine_not_authorized", payload)
    return EntitlementResult.allowed_result(payload)
