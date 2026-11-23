"""
File: crypto/factors.py

Purpose
-------
Keyed bindings of high-entropy identity factors (device identifiers,
biometric template digests, signature blobs) under the master key, so a stored
record can be checked against a presented value but cannot be tested against
candidate values by anyone without the master key.

Public interface:
- bind_factor(master_key, factor_name, value) -- Bind a factor value under the
  master key and return the encoded record.
- verify_bound_factor(master_key, factor_name, value, encoded) -- Check a
  presented value against a bound record, in constant time.
- is_legacy_binding(encoded) -- Report whether a record uses the legacy
  keyed_mac construction the encryption migration replaces.

Design notes:

New bindings are a BSR2-S64 MAC (``sponge.mac64``) keyed by
the master key over the framed factor name and value, under a domain string of
its own. The factor name is part of the MAC input and is checked against the
record, so a binding made for "device" never verifies in a "fingerprint" slot.

Bindings written before the encryption migration used the legacy construction (a per-name
``primitives.derive_subkey`` then ``primitives.keyed_mac``). They still verify
so they can be migrated; nothing writes them any more. A legacy binding is
migrated by verifying the presented value and binding it again, so only a
caller holding that value can migrate it.

These factors carry far more entropy than any password KDF would add, so they
get a fast keyed MAC rather than a deliberately slow derivation. Identity Tools
stores no low-entropy factor hashes; passphrases only ever unlock the keyring
(crypto/keyring.py).

Encoded forms::

    bsr2$mac64$<factor name>$<digest hex>        written since the migration
    bsr2$keyed_mac$<factor name>$<digest hex>    legacy, verify only

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py) -- ``sponge`` for new bindings,
  ``primitives`` for legacy ones and for hex and constant-time comparison.
- crypto.errors (crypto/errors.py)
Standard library: none.
Imported by:
- biometrics/identity/device_key.py
- biometrics/identity/encryption_migration.py
- packages/package.py
- packages/verification.py
Covered by tests: crypto/tests/test_factors.py,
crypto/tests/test_encryption_link.py (a binding written by 1.9.2).

Settings / parameters
---------------------
- PREFIX = "bsr2"
- MAC_ALGORITHM = "mac64" -- written by bind_factor().
- LEGACY_MAC_ALGORITHM = "keyed_mac" -- accepted by verify_bound_factor().
- DIGEST_BYTES = 32
- _DOMAIN = b"BrisartIdentityTools/factor/v2" -- domain of new bindings.
- _LEGACY_PURPOSE = b"BrisartIdentityTools/factor/v1" -- subkey purpose of
  legacy bindings.

Edge cases
----------
- bind_factor() raises Bsr2IntegrationError: "master key must be at least 32
  bytes.", "factor name must be a non-empty string.", "factor name cannot
  contain '$'." (the encoded form is dollar-delimited), or "factor value must
  be a string."
- verify_bound_factor() never raises for bad input: a malformed record, an
  unknown algorithm, a name mismatch, a non-string value, or a bad key all
  return False, so a corrupted record reads as "does not verify" instead of
  crashing an authentication path.
- Both raise EncryptionNotFoundError when BSR2 is not linked.

Known limitations
-----------------
- Legacy bindings are not rewritten on verify; they move to mac64 only when
  the caller binds the factor again (biometrics/identity/encryption_migration.py,
  packages/package.py).
- BSR2 is custom research cryptography with no independent review (see
  docs/SECURITY.md); do not treat it as a replacement for vetted, audited
  cryptography.

Examples
--------
Call shapes only: master_key stands for a 32-byte key the caller holds.

::

    from crypto.factors import bind_factor, verify_bound_factor
    record = bind_factor(master_key, "device", "device-id-123")
    verify_bound_factor(master_key, "device", "device-id-123", record)  # True
"""

from crypto import encryption
from crypto.errors import Bsr2IntegrationError

PREFIX = "bsr2"
MAC_ALGORITHM = "mac64"
LEGACY_MAC_ALGORITHM = "keyed_mac"
DIGEST_BYTES = 32

_DOMAIN = b"BrisartIdentityTools/factor/v2"
_LEGACY_PURPOSE = b"BrisartIdentityTools/factor/v1"


def _check_inputs(master_key, factor_name, value) -> None:
    if not isinstance(master_key, (bytes, bytearray)) or len(master_key) < 32:
        raise Bsr2IntegrationError("master key must be at least 32 bytes.")
    if not isinstance(factor_name, str) or not factor_name:
        raise Bsr2IntegrationError("factor name must be a non-empty string.")
    if "$" in factor_name:
        raise Bsr2IntegrationError("factor name cannot contain '$'.")
    if not isinstance(value, str):
        raise Bsr2IntegrationError("factor value must be a string.")


def _mac(bsr2, algorithm: str, master_key: bytes, factor_name: str, value: str) -> bytes:
    name = factor_name.encode("utf-8")
    data = value.encode("utf-8")
    if algorithm == MAC_ALGORITHM:
        return bsr2.sponge.mac64(
            bytes(master_key), _DOMAIN, name, data, output_bytes=DIGEST_BYTES
        )
    primitives = bsr2.primitives
    subkey = primitives.derive_subkey(bytes(master_key), name, _LEGACY_PURPOSE, 32)
    return primitives.keyed_mac(
        subkey, primitives.frame(name) + primitives.frame(data), DIGEST_BYTES
    )


def bind_factor(master_key: bytes, factor_name: str, value: str) -> str:
    """Bind a high-entropy factor value under the master key."""
    bsr2 = encryption.require()
    _check_inputs(master_key, factor_name, value)
    digest = _mac(bsr2, MAC_ALGORITHM, master_key, factor_name, value)
    return "$".join(
        (PREFIX, MAC_ALGORITHM, factor_name, bsr2.primitives.hex_encode(digest))
    )


def verify_bound_factor(master_key: bytes, factor_name: str, value, encoded: str) -> bool:
    """Check a high-entropy factor value against a bound record of either
    algorithm. Returns False for anything that does not verify."""
    bsr2 = encryption.require()
    primitives = bsr2.primitives
    if not isinstance(encoded, str):
        return False
    fields = encoded.split("$")
    if len(fields) != 4:
        return False
    prefix, algorithm, stored_name, digest_text = fields
    if prefix != PREFIX or algorithm not in (MAC_ALGORITHM, LEGACY_MAC_ALGORITHM):
        return False
    try:
        _check_inputs(master_key, factor_name, value)
        stored_digest = primitives.hex_decode(digest_text)
        calculated = _mac(bsr2, algorithm, master_key, factor_name, value)
    except (Bsr2IntegrationError, primitives.BrisartPrimitiveError):
        return False
    if len(stored_digest) != DIGEST_BYTES:
        return False
    names_match = primitives.constant_time_equal(
        stored_name.encode("utf-8"), factor_name.encode("utf-8")
    )
    digests_match = primitives.constant_time_equal(calculated, stored_digest)
    return names_match and digests_match


def is_legacy_binding(encoded) -> bool:
    """Report whether ``encoded`` is a legacy keyed_mac binding."""
    return isinstance(encoded, str) and encoded.startswith(
        f"{PREFIX}${LEGACY_MAC_ALGORITHM}$"
    )


__all__ = [
    "DIGEST_BYTES",
    "LEGACY_MAC_ALGORITHM",
    "MAC_ALGORITHM",
    "bind_factor",
    "is_legacy_binding",
    "verify_bound_factor",
]
