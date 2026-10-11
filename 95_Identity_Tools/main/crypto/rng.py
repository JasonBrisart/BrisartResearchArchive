"""
File: crypto/rng.py

Purpose
-------
DRBG construction for BSR2 envelope operations.

Public interface:
- class ManagedGenerator -- A BSR2 DRBG that reseeds from the operating system
  before its limits. Public methods: generate, destroy.
- new_generator(purpose) -- Build a managed DRBG for a named purpose.

Design notes:

``brisart_security_envelope.encrypt`` requires a caller-supplied generator and
deliberately does not create one.

This module seeds from ``secrets.token_bytes`` at double the minimum, and wraps
the generator so the DRBG's lifecycle limits (100,000 requests, 16 MiB output)
trigger a transparent reseed from fresh operating-system entropy instead of a
hard failure mid-run. Upstream raises ``BrisartDRBGError`` at those limits by
design; a long-lived enrollment process should not crash on record 100,001.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
- crypto.vendor (crypto/vendor.py)
Standard library: secrets.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/enrollment.py
- crypto/keyring.py
- packages/ciphers.py
- vault/store/vault_service.py
Covered by tests: crypto/tests/test_envelope.py, crypto/tests/test_rng.py.

Settings / parameters
---------------------
- SEED_BYTES = max(128, MINIMUM_SEED_BYTES * 2) -- Upstream requires 64.
  Seeding with 128 costs nothing and leaves margin.
- REQUESTS_BEFORE_RESEED = 50_000 -- Reseed before upstream's own limits rather
  than at them.
- BYTES_BEFORE_RESEED = 8 * 1024 * 1024

Edge cases
----------
- ManagedGenerator.__init__() raises Bsr2IntegrationError: "personalization
  must be bytes."
- ManagedGenerator.__init__() raises Bsr2IntegrationError: "personalization
  must contain at least {...} bytes."
- new_generator() raises Bsr2IntegrationError: "generator purpose must be a
  non-empty string."
- ManagedGenerator.generate(): catches BrisartDRBGError and handles it in
  place; it does not propagate to the caller.

Known limitations
-----------------
- That leaves the caller responsible for seeding it correctly, and the seed is
  where a deterministic generator lives or dies: BSR2's DRBG expands seed
  material but cannot create entropy, so a weak seed means weak salts and
  nonces no matter how good the expansion is.
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: personalization, length,
additional_input stand for values the caller supplies.

::

    from crypto.rng import ManagedGenerator
    obj = ManagedGenerator(personalization)
    obj.generate(length, additional_input)
"""

import secrets

from crypto.errors import Bsr2IntegrationError
from crypto.vendor import (
    MINIMUM_PERSONALIZATION_BYTES,
    MINIMUM_SEED_BYTES,
    BrisartDRBG,
    BrisartDRBGError,
)

# Upstream requires 64. Seeding with 128 costs nothing and leaves margin.
SEED_BYTES = max(128, MINIMUM_SEED_BYTES * 2)

# Reseed before upstream's own limits rather than at them.
REQUESTS_BEFORE_RESEED = 50_000
BYTES_BEFORE_RESEED = 8 * 1024 * 1024


class ManagedGenerator:
    """A BSR2 DRBG that reseeds from the operating system before its limits.

    Exposes ``generate(length, additional_input)``, which is the entire
    interface ``brisart_security_envelope.encrypt`` requires.
    """

    def __init__(self, personalization: bytes):
        if not isinstance(personalization, bytes):
            raise Bsr2IntegrationError("personalization must be bytes.")
        if len(personalization) < MINIMUM_PERSONALIZATION_BYTES:
            raise Bsr2IntegrationError(
                "personalization must contain at least "
                f"{MINIMUM_PERSONALIZATION_BYTES} bytes."
            )
        self._personalization = personalization
        self._requests = 0
        self._generated_bytes = 0
        self._drbg = BrisartDRBG(secrets.token_bytes(SEED_BYTES), personalization)

    def _reseed(self) -> None:
        self._drbg.reseed(
            secrets.token_bytes(SEED_BYTES),
            b"BrisartIdentityTools/managed-reseed/" + self._personalization,
        )
        self._requests = 0
        self._generated_bytes = 0

    def generate(self, length: int, additional_input: bytes) -> bytes:
        if (
            self._requests >= REQUESTS_BEFORE_RESEED
            or self._generated_bytes + length >= BYTES_BEFORE_RESEED
        ):
            self._reseed()
        try:
            output = self._drbg.generate(length, additional_input)
        except BrisartDRBGError:
            # Upstream's continuous health check destroys the generator when it
            # sees a repeated block. Rebuilding from fresh entropy is the only
            # correct recovery; retrying the dead instance would raise forever.
            self._drbg = BrisartDRBG(
                secrets.token_bytes(SEED_BYTES), self._personalization
            )
            self._requests = 0
            self._generated_bytes = 0
            output = self._drbg.generate(length, additional_input)
        self._requests += 1
        self._generated_bytes += length
        return output

    def destroy(self) -> None:
        """Zero the underlying DRBG state."""
        self._drbg.destroy()


def new_generator(purpose: str) -> ManagedGenerator:
    """Build a managed DRBG for a named purpose.

    ``purpose`` becomes part of the personalization string, so generators for
    unrelated subsystems do not share a personalization value.
    """
    if not isinstance(purpose, str) or not purpose:
        raise Bsr2IntegrationError("generator purpose must be a non-empty string.")
    personalization = (
        b"BrisartIdentityTools/BSR2/v1/" + purpose.encode("utf-8")
    ).ljust(MINIMUM_PERSONALIZATION_BYTES, b"\x00")
    return ManagedGenerator(personalization)




