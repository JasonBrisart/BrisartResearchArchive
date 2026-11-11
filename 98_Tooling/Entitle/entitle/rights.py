"""
File: entitle/rights.py

Purpose
-------
Define what an entitlement says and how it is judged, independent of how it is stored: the
  payload layout, the rights vocabulary, the denial reasons, and EntitlementResult, the object a
  protected program asks "is this right granted?". Nothing here reads files or touches
  encryption; entitle/entitlements.py opens a .entitle file and hands the payload to
  evaluate_payload.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError, utc_now) and the standard library (datetime, json).
  Imported by entitle/entitlements.py (make_rights, make_entitlement_payload,
  load_entitlement_payload, evaluate_payload, parse_iso_datetime, EntitlementResult,
  ENTITLEMENT_FORMAT) and examples/protected_app_example.py (EntitlementDenied). A program that
  protects its features with Entitle only needs EntitlementResult and EntitlementDenied from here.
  Covered by tests/test_rights.py.

Settings / parameters
---------------------
ENTITLEMENT_FORMAT ("entitle.entitlement.v1") marks every payload and is part of the
  encryption context built in entitle/entitlements.py, so changing it makes every issued
  entitlement fail verification. make_rights builds the rights dictionary: can_run is always
  true; can_use_enterprise_features, can_modify, can_fork, can_export_source and
  can_redistribute default to false; deployment_limit defaults to 1 (None means unlimited);
  support_tier is a free label (default "standard"). A payload carries format, issuer_id,
  subject_id, product_id, entitlement_id, issued_at, expires_at (None means never), rights and
  metadata.

Edge cases
----------
evaluate_payload never raises; it denies with one reason: unsupported_entitlement_format,
  wrong_product (only when expected_product_id is given), invalid_expiration_timestamp or
  entitlement_expired, and otherwise allows with reason "verified". An expiry without a zone is
  read as UTC and a trailing Z is accepted. An expiry given as a date alone ("2026-12-31") means
  00:00 UTC at the start of that day, so the entitlement stops working when that day begins; give
  a time ("2026-12-31T23:59:59Z") to include the whole day. A denied result has no rights, so
  has_right is false for everything and get_limit still reads the payload. require_right raises
  EntitlementDenied for a denied result and for a right that was not granted, with different
  messages. load_entitlement_payload raises EntitleError for bytes that are not UTF-8 JSON or that
  decode to something other than an object.

Known limitations
-----------------
Expiry is judged against the local clock, so a machine with a wrong clock accepts an expired
  entitlement. Rights are plain flags and limits: Entitle does not know which rights a given
  product actually enforces, and only deployment_limit is enforced by Entitle itself (in
  entitle/tracking.py). Revocation is not part of the payload and is not checked here.

Examples
--------
From the directory containing run.py:

    from entitle.rights import (
        EntitlementDenied, evaluate_payload, make_entitlement_payload, make_rights,
    )

    payload = make_entitlement_payload(
        issuer_id="Issuer", subject_id="Lab", product_id="Demo", entitlement_id="e-1",
        issued_at="2026-01-01T00:00:00+00:00", rights=make_rights(modify=True),
    )
    result = evaluate_payload(payload, expected_product_id="Demo")
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
):
    return {
        "format": ENTITLEMENT_FORMAT,
        "issuer_id": issuer_id,
        "subject_id": subject_id,
        "product_id": product_id,
        "entitlement_id": entitlement_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "rights": rights or {},
        "metadata": metadata or {},
    }


class EntitlementResult:
    def __init__(self, allowed, reason, payload=None):
        self.allowed = allowed
        self.reason = reason
        self.payload = payload or {}

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
        return bool(self.rights.get(right_name, False))

    def get_limit(self, limit_name, default=None):
        return self.rights.get(limit_name, default)

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
        }


def evaluate_payload(payload, expected_product_id=None):
    if payload.get("format") != ENTITLEMENT_FORMAT:
        return EntitlementResult.denied_result("unsupported_entitlement_format", payload)
    if expected_product_id is not None and payload.get("product_id") != expected_product_id:
        return EntitlementResult.denied_result("wrong_product", payload)
    expires_at = payload.get("expires_at")
    if expires_at:
        try:
            expiration = parse_iso_datetime(expires_at)
        except Exception:
            return EntitlementResult.denied_result("invalid_expiration_timestamp", payload)
        if utc_now() > expiration:
            return EntitlementResult.denied_result("entitlement_expired", payload)
    return EntitlementResult.allowed_result(payload)
