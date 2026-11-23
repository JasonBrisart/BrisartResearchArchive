"""
File: packages/ciphers.py

Purpose
-------
Low-level cryptographic operations for Identity-Bound Packages.

Public interface:
- class CiphersError(ValueError) -- Raised on invalid cipher inputs (not on
  authentication failure -- see :class:`crypto.errors.Bsr2IntegrationError` and
  its subclasses for that).
- new_content_key() -- Generate a fresh random content key for one package,
  from BSR2's system entropy.
- text_master_key(text) -- The 32-byte recipient master key the CLI, GUI, and
  demo derive from typed text: a BSR2-S64 hash.
- legacy_text_master_key(text) -- The unsalted SHA-256 the same interfaces
  used before the encryption migration. Read-only: used to recognise and migrate recipients
  whose key slot was sealed under it.
- wrap_content_key(recipient_master_key, package_id, identity_id, content_key)
  -- Seal ``content_key`` into one recipient's key slot.
- unwrap_content_key(recipient_master_key, package_id, identity_id, wrapped) --
  Recover the content key from one recipient's key slot.
- seal_payload(content_key, package_id, payload) -- Seal a package's payload
  under its content key.
- open_payload(content_key, package_id, sealed_payload) -- Open a package's
  payload using an already-recovered content key.

Design notes:

An IBP separates the secret that protects the *payload* from the secrets that
protect *access to that secret*, the same envelope-around-a-key pattern
:mod:`crypto.keyring` uses for a single master key. Here it is generalised to
many recipients:

- A random 32-byte **content key** seals the actual payload once.
- The content key itself is sealed once per recipient, each under that
  recipient's own master key, in that recipient's own **key slot**.

Consequences that follow from this and are deliberate: adding or removing a
recipient only touches that recipient's key slot -- the payload is never
re-encrypted, and no other recipient's slot is touched. Losing every
recipient's master key makes the package permanently unopenable, by design;
there is no back door.

**Typed-text master keys.** The CLI, GUI, and demo let an operator type any
text in place of a real 32-byte master key. That text becomes a key through
text_master_key(), defined once here so every interface derives the same key.
It is a fast unkeyed hash, not a password KDF: these prompts are demonstration
interfaces, and a real integration supplies a master key unlocked from
crypto.keyring.Keyring. Before the encryption migration the same text was hashed with SHA-256
inside each interface; legacy_text_master_key() keeps that derivation only so
packages sealed under it can still be opened and migrated
(packages/package.py), and goes when the previous encryption is removed.

Named ``ciphers.py`` rather than ``crypto.py`` specifically to avoid colliding
with the top-level ``crypto/`` package this module imports from.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.encryption (crypto/encryption.py) -- entropy and sponge
- crypto.envelope (crypto/envelope.py)
- crypto.rng (crypto/rng.py)
Standard library: hashlib (legacy_text_master_key only).
Imported by:
- gui/tabs/tab_packages.py
- packages/demo.py
- packages/main.py
- packages/package.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- CONTENT_KEY_BYTES = 32
- _TEXT_KEY_DOMAIN = b"BrisartIdentityTools/package-text-key/v1"

Edge cases
----------
- wrap_content_key() raises CiphersError: "content_key must be exactly {...}
  bytes."
- unwrap_content_key() raises CiphersError: "unwrapped content key has an
  invalid length."

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.
- Typed-text keys are only as strong as the typed text: no salt and no work
  factor.
- Covered through packages/tests/test_package_migration.py and the package
  tests that call create/open.

Examples
--------
Call shapes only, not a runnable script: recipient_master_key, package_id,
identity_id, content_key, wrapped stand for values the caller supplies.

::

    from packages.ciphers import (
        new_content_key,
        wrap_content_key,
        unwrap_content_key,
    )
    new_content_key()
    wrap_content_key(
        recipient_master_key,
        package_id,
        identity_id,
        content_key,
    )
    unwrap_content_key(recipient_master_key, package_id, identity_id, wrapped)
"""

import hashlib

from crypto import encryption
from crypto.context import key_slot_context, package_context
from crypto.envelope import open_bytes, open_json, seal_bytes, seal_json
from crypto.rng import new_generator

CONTENT_KEY_BYTES = 32
_TEXT_KEY_DOMAIN = b"BrisartIdentityTools/package-text-key/v1"


class CiphersError(ValueError):
    """Raised on invalid cipher inputs (not on authentication failure --
    see :class:`crypto.errors.Bsr2IntegrationError` and its subclasses for
    that)."""


def new_content_key() -> bytes:
    """Generate a fresh random content key for one package."""
    return encryption.require().entropy.system_entropy(CONTENT_KEY_BYTES)


def text_master_key(text: str) -> bytes:
    """Derive a recipient master key from typed text with BSR2-S64."""
    return encryption.require().sponge.hash64(
        text.encode("utf-8"), _TEXT_KEY_DOMAIN, CONTENT_KEY_BYTES
    )


def legacy_text_master_key(text: str) -> bytes:
    """The pre-migration typed-text derivation; read-only, for migration."""
    return hashlib.sha256(text.encode("utf-8")).digest()


def wrap_content_key(recipient_master_key: bytes, package_id: str, identity_id: str, content_key: bytes) -> dict:
    """Seal ``content_key`` into one recipient's key slot.

    The envelope's context binds both ``package_id`` and ``identity_id``, so
    a key slot sealed for one recipient cannot be moved into another
    recipient's slot in the same package, nor reused in a different package,
    even by an attacker who can edit the stored package file.
    """
    if not isinstance(content_key, (bytes, bytearray)) or len(content_key) != CONTENT_KEY_BYTES:
        raise CiphersError(f"content_key must be exactly {CONTENT_KEY_BYTES} bytes.")
    context = key_slot_context(package_id, identity_id)
    rng = new_generator("package-key-slot")
    return seal_bytes(recipient_master_key, content_key, context, rng)


def unwrap_content_key(recipient_master_key: bytes, package_id: str, identity_id: str, wrapped: dict) -> bytes:
    """Recover the content key from one recipient's key slot.

    Raises :class:`crypto.errors.EnvelopeAuthenticationError` (a
    ``Bsr2IntegrationError``) if the supplied master key does not match the
    slot, or if the slot was sealed under a different package or identity
    context than claimed.
    """
    context = key_slot_context(package_id, identity_id)
    content_key = open_bytes(recipient_master_key, wrapped, context)
    if len(content_key) != CONTENT_KEY_BYTES:
        raise CiphersError("unwrapped content key has an invalid length.")
    return content_key


def seal_payload(content_key: bytes, package_id: str, payload: dict) -> dict:
    """Seal a package's payload under its content key."""
    context = package_context(package_id)
    rng = new_generator("package-payload")
    return seal_json(content_key, payload, context, rng)


def open_payload(content_key: bytes, package_id: str, sealed_payload: dict) -> dict:
    """Open a package's payload using an already-recovered content key."""
    context = package_context(package_id)
    return open_json(content_key, sealed_payload, context)


__all__ = [
    "CONTENT_KEY_BYTES",
    "CiphersError",
    "legacy_text_master_key",
    "new_content_key",
    "open_payload",
    "seal_payload",
    "text_master_key",
    "unwrap_content_key",
    "wrap_content_key",
]
