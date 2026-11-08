"""
File: crypto/errors.py

Purpose
-------
Error types for the BSR2 integration layer.

Public interface:
- class Bsr2IntegrationError(Exception) -- Base class for BSR2 integration
  failures.
- class KeyringFormatError(Bsr2IntegrationError) -- Raised when stored keyring
  material is not well formed.
- class KeyringAuthenticationError(Bsr2IntegrationError) -- Raised when a
  passphrase or recovery code does not unwrap the master key.
- class KeyringLockedError(Bsr2IntegrationError) -- Raised when an operation
  needs a master key that is not unlocked.
- class EnvelopeAuthenticationError(Bsr2IntegrationError) -- Raised when a
  sealed payload fails authentication.

Design notes:

Authentication failure is kept distinct from malformed input. Callers need to
treat "this is not shaped like a keyring" as a data bug and "the tag did not
verify" as a security event, and one shared exception type forces them to
string-match messages to tell those apart.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/verification.py
- biometrics/identity/keyring_access.py
- crypto/context.py
- crypto/envelope.py
- crypto/factors.py
- crypto/keyring.py
- crypto/rng.py
- crypto/throttle.py
- packages/package.py
- packages/verification.py
- vault/store/vault_service.py
Covered by tests: crypto/tests/test_context.py, crypto/tests/test_envelope.py,
crypto/tests/test_factors.py, crypto/tests/test_keyring.py,
crypto/tests/test_rng.py, crypto/tests/test_throttle.py.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
::

    import crypto.errors
"""

class Bsr2IntegrationError(Exception):
    """Base class for BSR2 integration failures."""


class KeyringFormatError(Bsr2IntegrationError):
    """Raised when stored keyring material is not well formed."""


class KeyringAuthenticationError(Bsr2IntegrationError):
    """Raised when a passphrase or recovery code does not unwrap the master key.

    The message deliberately does not say whether the wrapper was structurally
    valid, because that distinction tells an attacker whether a guess was
    partially correct.
    """


class KeyringLockedError(Bsr2IntegrationError):
    """Raised when an operation needs a master key that is not unlocked."""


class EnvelopeAuthenticationError(Bsr2IntegrationError):
    """Raised when a sealed payload fails authentication.

    Wraps the vendored layer's ``BrisartEnvelopeError`` so callers catch a
    single exception family instead of importing vendor exception types. It
    covers a modified ciphertext, the wrong key, and the wrong context alike:
    all three are indistinguishable to the verifier, and treating them as one
    outcome avoids leaking which one occurred.

    The original exception is kept as ``__cause__`` for debugging.
    """




