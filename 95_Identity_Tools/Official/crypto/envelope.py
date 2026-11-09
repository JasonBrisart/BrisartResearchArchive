"""
File: crypto/envelope.py

Purpose
-------
Sealed payloads for everything Identity Tools stores: vault records, biometric
templates, attachments, keyring wrappers, and package parts. New payloads are
sealed with BSR2's sealed-message format v3 (``BSR2-S64-SIV``)
or, above its size limit, its chunked stream format (``BSR-STREAM-1``).
Payloads sealed before the encryption migration with the legacy v2 JSON envelope
(``BSR2-ARX-SPONGE-ETM``) still open so they can be migrated; nothing writes
them any more.

Public interface:
- SEALED_FORMAT = "BSR2-S64-SIV/3", STREAM_FORMAT = "BSR-STREAM-1" -- the
  ``format`` values of the two sealed shapes this module writes.
- is_envelope(value) -- Report whether ``value`` is a sealed payload in any
  format this module opens.
- is_legacy(value) -- Report whether ``value`` is a legacy v2 envelope, the
  format the encryption migration replaces.
- reseal(master_key, envelope, context, rng) -- Re-encrypt a legacy envelope in
  the current format under the same key and context; return any other sealed
  payload unchanged.
- seal_bytes(master_key, plaintext, context, rng) -- Seal bytes of any size.
- open_bytes(master_key, envelope, context) -- Verify and decrypt a sealed
  payload of any supported format.
- seal_json(master_key, payload, context, rng) -- Seal a JSON object.
- open_json(master_key, envelope, context) -- Open a payload sealed by
  seal_json().

Design notes:

**Stored shape.** Payloads live inside JSON files, so a sealed payload is a
two-field object: ``{"format": SEALED_FORMAT | STREAM_FORMAT, "data":
<base64 of the BSR2 output>}``. The legacy shape is the
six-field v2 envelope (algorithm, version, salt, nonce, ciphertext, tag).
open_bytes() dispatches on shape, so callers never ask which format they hold.

**Which format is written.** Plaintext up to the sealed-message limit
(``aead.MAX_PLAINTEXT_BYTES``, 16 MiB) is sealed as one v3 message; anything
larger goes through BSR-STREAM-1, which authenticates each 64 KiB chunk with its
index and a final-chunk flag. There is no size cap here: the 16 MiB limit of
the legacy envelope is gone, and large payloads cost only memory.

**Migration.** reseal() is the one operation every store's encryption
migration uses: open with whatever format the payload is in, seal the same
bytes in the current format under the same key and context. Because seal_json()
seals canonical JSON bytes, resealing raw bytes keeps JSON payloads openable
with open_json().

**Padding.** v3 messages use BSR2's ``block`` padding (256-byte
buckets), so a short credential and a long recovery note are not told apart by
ciphertext size. This is the same bucket size the legacy envelope was padded
to by hand here. Stream payloads are not padded; at that size the bucket would
reveal nothing extra.

**Canonical JSON.** Objects are serialised with sorted keys and no incidental
whitespace, so resealing identical content produces identical plaintext.

**Legacy padding.** Legacy v2 plaintexts carry this module's old 8-byte length
prefix and zero padding; _unpad_legacy() strips them after the tag verifies.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py) -- aead, stream, and the legacy
  envelope module, resolved at call time.
- crypto.errors (crypto/errors.py)
Standard library: base64, binascii, json.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/enrollment.py
- biometrics/engine/verification.py
- biometrics/identity/identity_record.py
- crypto/keyring.py
- packages/ciphers.py
- vault/records/record_model.py
- vault/store/vault_service.py
Also called for reseal() by vault/store/vault_service.py,
biometrics/identity/encryption_migration.py, and packages/package.py.
Covered by tests: crypto/tests/test_envelope.py,
crypto/tests/test_encryption_link.py (legacy payloads sealed by 1.9.2).

Settings / parameters
---------------------
- SEALED_FORMAT = "BSR2-S64-SIV/3"
- STREAM_FORMAT = "BSR-STREAM-1"
- _PADDING = "block" -- v3 padding policy (256-byte buckets).
- _LEGACY_FIELDS -- the six field names of a legacy v2 envelope.
- _LEGACY_LENGTH_PREFIX_BYTES = 8 -- legacy plaintext length prefix.

Edge cases
----------
- Every public function raises EncryptionNotFoundError when BSR2 is not linked, including is_envelope(): without the linked format
  constants a legacy envelope cannot be recognised, and guessing "not an
  envelope" would let callers treat ciphertext as plaintext.
- seal_bytes() raises Bsr2IntegrationError: "plaintext must be bytes."
- open_bytes() raises Bsr2IntegrationError: "value is not a sealed payload."
  for anything is_envelope() rejects, and "sealed payload data is not valid
  base64." for a corrupt ``data`` field.
- open_bytes() raises EnvelopeAuthenticationError: "sealed payload failed
  authentication: wrong key, wrong context, or modified ciphertext." for any
  failure inside BSR2, in every format. The original error is
  kept as ``__cause__``.
- _unpad_legacy() raises Bsr2IntegrationError for a legacy plaintext that is
  truncated or declares a length beyond its own data.
- seal_json() raises Bsr2IntegrationError: "payload must be an object." /
  "payload is not JSON-serialisable."
- open_json() raises Bsr2IntegrationError: "decrypted payload is not valid
  JSON." / "decrypted payload must be an object."

Known limitations
-----------------
- Whole payloads are held in memory while sealing and opening, stream format
  included; very large attachments need that much free memory.
- Existing legacy payloads stay in the legacy format until their store is
  migrated or they are written again; this module never rewrites data on read.
- BSR2 is custom research cryptography with no independent review (see
  docs/SECURITY.md); do not treat it as a replacement for vetted, audited
  cryptography.

Examples
--------
Call shapes only: master_key, plaintext, context, and rng stand for values the
caller supplies.

::

    from crypto.envelope import open_bytes, seal_bytes
    sealed = seal_bytes(master_key, plaintext, context, rng)
    sealed["format"]                     # "BSR2-S64-SIV/3"
    open_bytes(master_key, sealed, context) == plaintext
"""

import base64
import binascii
import json

from crypto import encryption
from crypto.errors import Bsr2IntegrationError, EnvelopeAuthenticationError

SEALED_FORMAT = "BSR2-S64-SIV/3"
STREAM_FORMAT = "BSR-STREAM-1"
_FORMATS = frozenset({SEALED_FORMAT, STREAM_FORMAT})
_PADDING = "block"

_LEGACY_FIELDS = frozenset({"algorithm", "version", "salt", "nonce", "ciphertext", "tag"})
_LEGACY_LENGTH_PREFIX_BYTES = 8


def _is_legacy(bsr2, value) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _LEGACY_FIELDS
        and value.get("algorithm") == bsr2.envelope.ALGORITHM
        and value.get("version") == bsr2.envelope.VERSION
    )


def _is_current(value) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"format", "data"}
        and value.get("format") in _FORMATS
        and isinstance(value.get("data"), str)
    )


def is_envelope(value) -> bool:
    """Report whether ``value`` is a sealed payload this module can open."""
    bsr2 = encryption.require()
    return _is_current(value) or _is_legacy(bsr2, value)


def is_legacy(value) -> bool:
    """Report whether ``value`` is a legacy v2 envelope awaiting migration."""
    return _is_legacy(encryption.require(), value)


def reseal(master_key: bytes, envelope: dict, context: str, rng) -> dict:
    """Return ``envelope`` re-encrypted in the current format when it is
    legacy, or unchanged otherwise. Authentication failures propagate as
    EnvelopeAuthenticationError, so a wrong key or context never produces a
    resealed payload."""
    if not is_legacy(envelope):
        return envelope
    return seal_bytes(master_key, open_bytes(master_key, envelope, context), context, rng)


def _unpad_legacy(padded: bytes) -> bytes:
    if len(padded) < _LEGACY_LENGTH_PREFIX_BYTES:
        raise Bsr2IntegrationError("decrypted payload is truncated.")
    declared = int.from_bytes(padded[:_LEGACY_LENGTH_PREFIX_BYTES], "big")
    if declared > len(padded) - _LEGACY_LENGTH_PREFIX_BYTES:
        raise Bsr2IntegrationError(
            "decrypted payload declares a length beyond its own data."
        )
    return padded[_LEGACY_LENGTH_PREFIX_BYTES:_LEGACY_LENGTH_PREFIX_BYTES + declared]


def seal_bytes(master_key: bytes, plaintext: bytes, context: str, rng) -> dict:
    """Seal ``plaintext`` of any size as a v3 message or, above the v3 limit,
    a BSR-STREAM-1 payload."""
    bsr2 = encryption.require()
    if not isinstance(plaintext, (bytes, bytearray)):
        raise Bsr2IntegrationError("plaintext must be bytes.")
    plaintext = bytes(plaintext)
    key = bytes(master_key)
    if len(plaintext) <= bsr2.aead.MAX_PLAINTEXT_BYTES:
        sealed_format = SEALED_FORMAT
        data = bsr2.aead.seal(key, plaintext, context, rng=rng, padding=_PADDING)
    else:
        sealed_format = STREAM_FORMAT
        data = bsr2.stream.encrypt_bytes(key, plaintext, context=context, rng=rng)
    return {"format": sealed_format, "data": base64.b64encode(data).decode("ascii")}


def open_bytes(master_key: bytes, envelope: dict, context: str) -> bytes:
    """Verify and decrypt a sealed payload in any supported format.

    Every failure inside BSR2 is re-raised as
    EnvelopeAuthenticationError: wrong key, wrong context, and modified data
    are indistinguishable to the verifier and are reported as one outcome.
    """
    bsr2 = encryption.require()
    key = bytes(master_key)
    if _is_legacy(bsr2, envelope):
        try:
            padded = bsr2.envelope.decrypt(key, envelope, context)
        except bsr2.envelope.BrisartEnvelopeError as exc:
            raise _authentication_failed() from exc
        return _unpad_legacy(padded)
    if not _is_current(envelope):
        raise Bsr2IntegrationError("value is not a sealed payload.")
    try:
        data = base64.b64decode(envelope["data"].encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise Bsr2IntegrationError("sealed payload data is not valid base64.") from exc
    try:
        if envelope["format"] == SEALED_FORMAT:
            return bsr2.aead.unseal(key, data, context)
        return bsr2.stream.decrypt_bytes(key, data, context=context)
    except (bsr2.aead.BrisartSealError, bsr2.stream.BrisartStreamError) as exc:
        raise _authentication_failed() from exc


def _authentication_failed() -> EnvelopeAuthenticationError:
    return EnvelopeAuthenticationError(
        "sealed payload failed authentication: wrong key, wrong context, "
        "or modified ciphertext."
    )


def seal_json(master_key: bytes, payload: dict, context: str, rng) -> dict:
    """Seal a JSON-serialisable object."""
    encryption.require()
    if not isinstance(payload, dict):
        raise Bsr2IntegrationError("payload must be an object.")
    try:
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Bsr2IntegrationError("payload is not JSON-serialisable.") from exc
    return seal_bytes(master_key, serialized, context, rng)


def open_json(master_key: bytes, envelope: dict, context: str) -> dict:
    """Open a payload sealed by seal_json()."""
    plaintext = open_bytes(master_key, envelope, context)
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # Reached only after authentication, so this is corruption at sealing
        # time rather than tampering.
        raise Bsr2IntegrationError("decrypted payload is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise Bsr2IntegrationError("decrypted payload must be an object.")
    return payload


__all__ = [
    "SEALED_FORMAT",
    "STREAM_FORMAT",
    "is_envelope",
    "is_legacy",
    "open_bytes",
    "open_json",
    "reseal",
    "seal_bytes",
    "seal_json",
]
