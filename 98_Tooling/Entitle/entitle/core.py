"""
Entitle Core

Offline software rights checking for entitlement records.

This module does not perform encryption directly.
It expects protected entitlement containers to be opened through
entitle.bsr_adapter.
"""
import datetime
import json

ENTITLEMENT_FORMAT = "entitle.entitlement.v1"


class EntitleError(Exception):
    """Base Entitle exception."""


class EntitlementDenied(EntitleError):
    """Raised when a required entitlement is unavailable."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_iso_datetime(value):
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def canonical_json(data):
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def load_entitlement_payload(raw_bytes):
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except Exception as exc:
        raise EntitleError("Invalid entitlement payload.") from exc
    return payload


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
    if expected_product_id is not None:
        if payload.get("product_id") != expected_product_id:
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
