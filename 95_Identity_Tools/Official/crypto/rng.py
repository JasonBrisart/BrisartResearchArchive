"""
File: crypto/rng.py

Purpose
-------
The generator Identity Tools passes to every Brisart Encryption seal: a
Brisart Encryption DRBG, seeded from Brisart Encryption's health-checked
operating-system entropy and reseeded before its own lifecycle limits.

Public interface:
- class ManagedGenerator -- A Brisart Encryption DRBG that reseeds before its
  limits. Public methods: generate, destroy.
- new_generator(purpose) -- Build a managed generator for a named purpose.

Design notes:

The v3 sealed format and BSR-STREAM-1 always draw their 32-byte randomizer from
fresh system entropy and XOR in the caller's generator output when one is
given. Passing this generator therefore adds an independent second source: a
randomizer repeats only if both the operating system and the DRBG repeat.

Seeds come from ``entropy.system_entropy``, which rejects all-zero and
repeated-block output from the operating system before it reaches the DRBG.
The DRBG's lifecycle limits (100,000 requests, 16 MiB output) would otherwise
raise ``BrisartDRBGError`` mid-run by design; this wrapper reseeds before
them so a long enrollment does not fail on record 100,001.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py) -- the linked ``drbg`` and
  ``entropy`` modules, resolved when a generator is built.
- crypto.errors (crypto/errors.py)
Standard library: none.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/enrollment.py
- crypto/keyring.py
- packages/ciphers.py
- vault/store/vault_service.py
Covered by tests: crypto/tests/test_rng.py, crypto/tests/test_envelope.py.

Settings / parameters
---------------------
- SEED_BYTES = 128 -- The DRBG requires at least 64; 128 leaves margin. The
  linked DRBG rejects any seed below its own minimum, so a future rise above
  128 fails loudly rather than silently.
- REQUESTS_BEFORE_RESEED = 50_000, BYTES_BEFORE_RESEED = 8 MiB -- reseed
  before the DRBG's own limits rather than at them.

Edge cases
----------
- new_generator() and ManagedGenerator() raise EncryptionNotFoundError when
  Brisart Encryption is not linked. A generator already built keeps the
  library it was built with.
- ManagedGenerator.__init__() raises Bsr2IntegrationError: "personalization
  must be bytes." / "personalization must contain at least {...} bytes."
- new_generator() raises Bsr2IntegrationError: "generator purpose must be a
  non-empty string."
- ManagedGenerator.generate() catches BrisartDRBGError (the DRBG's health
  check destroys the instance when it sees a repeated block) and rebuilds from
  fresh entropy; it does not propagate to the caller.
- BrisartEntropyError from the operating system does propagate: there is no
  safe fallback when the system cannot supply entropy.

Known limitations
-----------------
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

from crypto import encryption
from crypto.errors import Bsr2IntegrationError

SEED_BYTES = 128
REQUESTS_BEFORE_RESEED = 50_000
BYTES_BEFORE_RESEED = 8 * 1024 * 1024


class ManagedGenerator:
    """A Brisart Encryption DRBG that reseeds before its limits.

    Exposes ``generate(length, additional_input)``, the interface Brisart
    Encryption's seal functions accept as ``rng``.
    """

    def __init__(self, personalization: bytes):
        self._bsr2 = encryption.require()
        if not isinstance(personalization, bytes):
            raise Bsr2IntegrationError("personalization must be bytes.")
        minimum = self._bsr2.drbg.MINIMUM_PERSONALIZATION_BYTES
        if len(personalization) < minimum:
            raise Bsr2IntegrationError(
                f"personalization must contain at least {minimum} bytes."
            )
        self._personalization = personalization
        self._drbg = self._new_drbg()

    def _seed(self) -> bytes:
        return self._bsr2.entropy.system_entropy(SEED_BYTES)

    def _new_drbg(self):
        self._requests = 0
        self._generated_bytes = 0
        return self._bsr2.drbg.BrisartDRBG(self._seed(), self._personalization)

    def _reseed(self) -> None:
        self._drbg.reseed(
            self._seed(),
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
        except self._bsr2.drbg.BrisartDRBGError:
            # The health check destroyed the instance; retrying it would raise
            # forever, so rebuild from fresh entropy.
            self._drbg = self._new_drbg()
            output = self._drbg.generate(length, additional_input)
        self._requests += 1
        self._generated_bytes += length
        return output

    def destroy(self) -> None:
        """Zero the underlying DRBG state."""
        self._drbg.destroy()


def new_generator(purpose: str) -> ManagedGenerator:
    """Build a managed generator whose personalization names ``purpose``, so
    generators for unrelated subsystems never share one."""
    bsr2 = encryption.require()
    if not isinstance(purpose, str) or not purpose:
        raise Bsr2IntegrationError("generator purpose must be a non-empty string.")
    personalization = (
        b"BrisartIdentityTools/BSR2/v1/" + purpose.encode("utf-8")
    ).ljust(bsr2.drbg.MINIMUM_PERSONALIZATION_BYTES, b"\x00")
    return ManagedGenerator(personalization)


__all__ = [
    "BYTES_BEFORE_RESEED",
    "REQUESTS_BEFORE_RESEED",
    "SEED_BYTES",
    "ManagedGenerator",
    "new_generator",
]
