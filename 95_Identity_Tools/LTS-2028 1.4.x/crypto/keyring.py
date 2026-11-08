"""
File: crypto/keyring.py

Purpose
-------
The keyring: a random master key wrapped twice, once under a passphrase and
once under an offline recovery code. Everything else Identity Tools stores
(vault records, biometric templates, attachments) is sealed under the master
key, never directly under a passphrase-derived key.

Public interface:
- generate_recovery_code() -- A fresh 40-character recovery code (200 bits)
  from a 32-symbol alphabet.
- format_recovery_code(code) -- Normalize a recovery code and format it as
  eight hyphen-separated groups of five.
- class Keyring -- A master key wrapped under a passphrase and a recovery code.
- Keyring(state) -- Wrap a stored state dict (format v2 or v1). Checks
  structure only and leaves ``state`` unchanged; the keyring starts locked.
- Keyring.create(passphrase, recovery_code=None, memory_blocks=None) --
  Classmethod. Build a keyring around a fresh master key (memory_blocks
  defaults to MEMORY_BLOCKS). Returns
  (keyring, formatted recovery code); the keyring comes back unlocked.
- Keyring.unlock_with_passphrase(passphrase) /
  Keyring.unlock_with_recovery_code(code) -- Unwrap, cache, and return the
  master key.
- Keyring.is_unlocked, Keyring.master_key -- Properties.
- Keyring.lock() -- Drop the cached master key.
- Keyring.change_passphrase(new_passphrase) -- Re-wrap under a new passphrase.
- Keyring.rotate_recovery_code() -- Issue and return a new recovery code.
- Keyring.needs_migration -- Property. True while any wrapper or the check
  value still uses the legacy construction.
- Keyring.migrate(passphrase) -- Unlock with the passphrase and replace every
  legacy part with BSR2-MHF-1 wrappers and a BSR2-S64 check. Returns the new
  recovery code when the recovery wrapper had to be replaced, else None.
- Keyring.to_state() -- The live, JSON-serialisable state dict.
- Keyring.public_summary() -- Non-secret metadata for status output.

Design notes:

**Key wrapping.** Deriving a key from the passphrase is deliberately expensive,
so it happens once per unlock: the derived key opens the wrapped master key,
which is held for the session, and every later seal and open is fast.
Changing the passphrase re-wraps the master key and re-encrypts no data. The
recovery code is a second full-strength path to the master key, shown once and
never stored. Losing both is unrecoverable by design.

**KDF.** New wrappers derive their key with Brisart Encryption's memory-hard
BSR2-MHF-1 (``kdf.derive_key``), 8,192 blocks (1 MiB) and one pass by default,
with the parameters and a 32-byte salt stored per wrapper. Memory-hardness is
what the legacy iterated KDF lacked, and BSR2-MHF-1 at its defaults is also
several times faster to unlock than the legacy 10,000-iteration floor.
Wrapped master keys are sealed with crypto/envelope.py, so new wrappers are v3
sealed messages.

**Format v2 and legacy keyrings.** Each wrapper records its own KDF, so one
keyring can hold an MHF passphrase wrapper and a legacy recovery wrapper at
the same time. That is what happens when a pre-migration keyring changes its
passphrase: the new wrapper is MHF and the untouched one keeps working.

A v1 state passed to Keyring() is read through a v2 view with both wrappers
marked as legacy ``BSR2/derive_password_key`` wrappers, but the stored dict is
left exactly as it was. Unlocking, failing to unlock, and saving the keyring
back with its attempt state therefore keep it readable by the release that
wrote it (Official 1.9.2, LTS-2028 1.3.10). The dict becomes v2 only on the first write that
replaces a wrapper: change_passphrase(), rotate_recovery_code(), or
migrate(). Top-level keys the keyring does not own (the attempt-limiting state
the biometrics keyring file keeps beside it) are kept through that change.

**Migration.** migrate() is the keyring half of every store's encryption
migration. It unlocks with the passphrase first, so a wrong passphrase can
never re-wrap the master key under a secret nobody knows. The passphrase
wrapper is re-derived from that passphrase. The recovery wrapper cannot be: the
recovery code is never stored, so a legacy recovery wrapper is replaced by a
freshly issued recovery code, returned once for display. The old recovery code
stops working for the migrated state. The master key never changes, so no
sealed data has to be re-encrypted because of the keyring.

**Check value.** ``master_key_check`` is a MAC over a fixed string under the
master key. It catches a keyring whose two wrappers hold different master keys,
which would otherwise surface much later as unopenable data. New and rewritten
keyrings use a BSR2-S64 MAC; converted v1 keyrings keep their legacy
``keyed_mac`` check until a wrapper is replaced.

**Failure reporting.** A wrong passphrase, a wrong recovery code, and a
modified wrapper all raise the same KeyringAuthenticationError. A failed unlock
does not change state.

**State ownership.** A Keyring holds the dict it is given; to_state() returns
it. change_passphrase() and rotate_recovery_code() modify it in place and write
nothing, so the caller persists to_state() afterwards (vault/store/vault_file.py
does this for the vault).

**Attempt limiting** lives in crypto/throttle.py and is applied by
biometrics/identity/keyring_access.py and vault/store/vault_service.py; the
recovery code relies on its 200 bits.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.encryption (crypto/encryption.py) -- ``kdf`` for new wrappers,
  ``primitives`` for legacy wrappers, hex, and constant-time comparison,
  ``sponge`` for the check value, ``entropy`` for salts.
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.rng (crypto/rng.py)
Standard library: typing, unicodedata.
Imported by:
- biometrics/app.py
- biometrics/identity/keyring_access.py
- gui/tabs/tab_biometrics.py
- vault/store/vault_file.py
- vault/store/vault_service.py
Covered by tests: crypto/tests/test_keyring.py,
biometrics/tests/test_keyring_access.py.

Settings / parameters
---------------------
- MASTER_KEY_BYTES = 32 -- master key and every wrapping key.
- KDF_SALT_BYTES = 32 -- salt per wrapper, redrawn whenever one is rebuilt.
- KDF = "BSR2-MHF-1", LEGACY_KDF = "BSR2/derive_password_key".
- MEMORY_BLOCKS = 8192, PASSES = 1 -- BSR2-MHF-1 defaults for new keyrings.
  change_passphrase() and rotate_recovery_code() keep the replaced wrapper's
  memory cost when it is already BSR2-MHF-1 and use MEMORY_BLOCKS when it is
  legacy.
- MAXIMUM_MEMORY_BLOCKS = 65536 (8 MiB), MAXIMUM_PASSES = 4 -- ceilings on
  stored parameters, so a tampered header cannot make an unlock run for hours
  before it can fail.
- LEGACY_MINIMUM_ITERATIONS = 10_000, LEGACY_MAXIMUM_ITERATIONS = 1_000_000 --
  accepted range for legacy wrappers; the floor stops a tampered header from
  requesting a trivially cheap derivation.
- RECOVERY_CODE_GROUPS = 8, RECOVERY_CODE_GROUP_SIZE = 5 -- 40 characters.
- _RECOVERY_ALPHABET -- Crockford base32 without I, L, O, U.
- _CONFUSABLE_CHARACTERS = {"I": "1", "L": "1", "O": "0", "U": "V"}.
- KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v2";
  LEGACY_KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v1" (read;
  converted to v2 only when a wrapper is replaced, never written as v1).
- Keyring.create(memory_blocks=...) -- a power of two from 64 to
  MAXIMUM_MEMORY_BLOCKS. MEMORY_BLOCKS is read at call time, so tests can
  lower it for speed with unittest.mock.patch.

Edge cases
----------
All errors derive from Bsr2IntegrationError: KeyringFormatError (bad stored
state or parameters), KeyringAuthenticationError (unlock failed), and
KeyringLockedError (operation needs an unlocked keyring).

Input handling:
- Recovery codes are forgiving: hyphens and whitespace are stripped, case is
  folded, and I and L read as 1, O as 0, and U as V.
- Passphrases are normalized with NFKC; surrounding whitespace counts.
- Argument problems (empty passphrase, malformed recovery code, memory_blocks
  out of range) fail before any key derivation runs.

Errors:
- Bsr2IntegrationError: "recovery code must be a string.", "recovery code
  contains characters outside its alphabet.", "recovery code must contain {...}
  characters, got {...}.", "passphrase must be a string.", "passphrase cannot
  be empty."
- KeyringFormatError from create(): "memory_blocks must be a power of two from
  64 to {...}."
- KeyringFormatError from Keyring(): "keyring state must be an object.",
  "unsupported keyring format.", "keyring {wrapper} section must be an
  object.", "keyring {wrapper} uses an unsupported KDF.", "keyring {wrapper}
  KDF parameters are invalid.", "keyring {wrapper} iteration count is outside
  the supported range.", "keyring {wrapper} salt is invalid.", "keyring
  {wrapper} wrapper is not a sealed payload.", "keyring master key check is
  invalid."
- KeyringAuthenticationError: "unlock failed: incorrect secret or modified
  keyring."
- KeyringFormatError after a successful unwrap: "unwrapped master key has an
  invalid length." or "unwrapped master key does not match the keyring check
  value." (the two wrappers hold different master keys).
- KeyringLockedError: "keyring is locked; unlock it before using the master
  key.", "unlock the keyring before changing its passphrase.", "unlock the
  keyring before rotating its recovery code."
- EncryptionNotFoundError whenever Brisart Encryption is not linked. It is
  never translated, so a missing link is not reported as a wrong passphrase.

Loading is structural only: a keyring whose wrappers were modified still
loads, and fails with KeyringAuthenticationError only when unlocked.

Known limitations
-----------------
- Slow by design: each unlock performs one derivation, create() two.
- Legacy wrappers are not upgraded on unlock; they move to BSR2-MHF-1 through
  migrate(), change_passphrase(), or rotate_recovery_code().
- migrate() replaces a legacy recovery code rather than keeping it, because
  the code is not available to re-derive. A copy of the keyring made before
  migration still opens with the old code.
- change_passphrase() does not ask for the old passphrase; being unlocked is
  the only check.
- Earlier copies of a keyring (backups, synced files) still open with the old
  passphrase or recovery code.
- lock() is best effort: Python cannot guarantee the bytes leave memory.
- No passphrase strength check, and not thread-safe.
- BSR2 is custom research cryptography with no independent review (see
  docs/SECURITY.md); do not treat it as a replacement for vetted, audited
  cryptography.

Examples
--------
Run from the repository root.

::

    from crypto.keyring import Keyring

    keyring, recovery_code = Keyring.create("correct horse battery staple")
    state = keyring.to_state()          # persist this; the code is never saved

    keyring = Keyring(state)
    keyring.unlock_with_passphrase("correct horse battery staple")
    keyring.unlock_with_recovery_code(recovery_code.lower())

    keyring.change_passphrase("a new passphrase")
    state = keyring.to_state()          # changed in place: persist again
"""

import unicodedata
from typing import Optional

from crypto import encryption
from crypto.context import keyring_context
from crypto.envelope import is_envelope, open_bytes, seal_bytes
from crypto.errors import (
    Bsr2IntegrationError,
    KeyringAuthenticationError,
    KeyringFormatError,
    KeyringLockedError,
)
from crypto.rng import new_generator

MASTER_KEY_BYTES = 32
KDF_SALT_BYTES = 32

KDF = "BSR2-MHF-1"
LEGACY_KDF = "BSR2/derive_password_key"
MEMORY_BLOCKS = 8192
PASSES = 1
MAXIMUM_MEMORY_BLOCKS = 65536
MAXIMUM_PASSES = 4
LEGACY_MINIMUM_ITERATIONS = 10_000
LEGACY_MAXIMUM_ITERATIONS = 1_000_000

RECOVERY_CODE_GROUPS = 8
RECOVERY_CODE_GROUP_SIZE = 5
_RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CONFUSABLE_CHARACTERS = {"I": "1", "L": "1", "O": "0", "U": "V"}

KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v2"
LEGACY_KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v1"

_WRAPPER_PASSPHRASE = "passphrase"
_WRAPPER_RECOVERY = "recovery"
_WRAPPERS = (_WRAPPER_PASSPHRASE, _WRAPPER_RECOVERY)

_CHECK_MAC = "mac64"
_LEGACY_CHECK_MAC = "keyed_mac"
_CHECK_DOMAIN = b"BrisartIdentityTools/keyring/master-key-check/v2"
_LEGACY_CHECK_MESSAGE = b"BrisartIdentityTools/keyring/master-key-check/v1"


def generate_recovery_code() -> str:
    """Forty characters from a 32-symbol alphabet: 200 bits of Brisart
    Encryption system entropy, five bits per character, so every character
    is uniform."""
    length = RECOVERY_CODE_GROUPS * RECOVERY_CODE_GROUP_SIZE
    bits = int.from_bytes(encryption.require().entropy.system_entropy(length * 5 // 8), "big")
    return "".join(_RECOVERY_ALPHABET[(bits >> (5 * index)) & 31] for index in range(length))


def format_recovery_code(code: str) -> str:
    """Format a recovery code in readable groups for display or printing."""
    normalized = _normalize_recovery_code(code)
    return "-".join(
        normalized[index:index + RECOVERY_CODE_GROUP_SIZE]
        for index in range(0, len(normalized), RECOVERY_CODE_GROUP_SIZE)
    )


def _normalize_recovery_code(code: str) -> str:
    if not isinstance(code, str):
        raise Bsr2IntegrationError("recovery code must be a string.")
    cleaned = []
    for character in code.strip().upper():
        if character in "- \t\r\n":
            continue
        folded = _CONFUSABLE_CHARACTERS.get(character, character)
        if folded not in _RECOVERY_ALPHABET:
            raise Bsr2IntegrationError(
                "recovery code contains characters outside its alphabet."
            )
        cleaned.append(folded)
    normalized = "".join(cleaned)
    expected = RECOVERY_CODE_GROUPS * RECOVERY_CODE_GROUP_SIZE
    if len(normalized) != expected:
        raise Bsr2IntegrationError(
            f"recovery code must contain {expected} characters, "
            f"got {len(normalized)}."
        )
    return normalized


def _normalize_passphrase(passphrase: str) -> str:
    if not isinstance(passphrase, str):
        raise Bsr2IntegrationError("passphrase must be a string.")
    if not passphrase:
        raise Bsr2IntegrationError("passphrase cannot be empty.")
    return unicodedata.normalize("NFKC", passphrase)


def _decode_params(bsr2, section: dict, wrapper: str):
    try:
        return bsr2.kdf.KdfParams.decode(
            bsr2.primitives.hex_decode(section["params"]),
            max_memory_blocks=MAXIMUM_MEMORY_BLOCKS,
            max_passes=MAXIMUM_PASSES,
        )
    except (KeyError, TypeError, bsr2.kdf.BrisartKdfError, bsr2.primitives.BrisartPrimitiveError) as exc:
        raise KeyringFormatError(f"keyring {wrapper} KDF parameters are invalid.") from exc


def _derive(bsr2, section: dict, wrapper: str, secret_text: str) -> bytes:
    if section["kdf"] == KDF:
        return bsr2.kdf.derive_key(
            secret_text,
            _decode_params(bsr2, section, wrapper),
            MASTER_KEY_BYTES,
            max_memory_blocks=MAXIMUM_MEMORY_BLOCKS,
            max_passes=MAXIMUM_PASSES,
        )
    return bsr2.primitives.derive_password_key(
        secret_text,
        bsr2.primitives.hex_decode(section["salt"]),
        iterations=section["iterations"],
        output_bytes=MASTER_KEY_BYTES,
    )


def _check_value(bsr2, mac: str, master_key: bytes) -> bytes:
    if mac == _CHECK_MAC:
        return bsr2.sponge.mac64(master_key, _CHECK_DOMAIN, output_bytes=32)
    return bsr2.primitives.keyed_mac(master_key, _LEGACY_CHECK_MESSAGE, 32)


def _converted_legacy_state(state: dict) -> dict:
    """The v2 view of a v1 state, as a new dict; ``state`` is not touched.
    Values the v1 shape leaves malformed are carried across and rejected by
    _validate()."""
    iterations = state.get("iterations")
    owned = {"format", "kdf", "iterations", *_WRAPPERS, "master_key_check"}
    if state.get("kdf") != LEGACY_KDF:
        raise KeyringFormatError("keyring passphrase uses an unsupported KDF.")
    converted = {"format": KEYRING_FORMAT}
    for wrapper in _WRAPPERS:
        section = state.get(wrapper)
        if not isinstance(section, dict):
            raise KeyringFormatError(f"keyring {wrapper} section must be an object.")
        converted[wrapper] = {
            "kdf": LEGACY_KDF,
            "iterations": iterations,
            "salt": section.get("salt"),
            "wrapped_master_key": section.get("wrapped_master_key"),
        }
    converted["master_key_check"] = {
        "mac": _LEGACY_CHECK_MAC,
        "value": state.get("master_key_check"),
    }
    converted.update({key: value for key, value in state.items() if key not in owned})
    return converted


def _validate_wrapper(bsr2, state: dict, wrapper: str) -> None:
    section = state.get(wrapper)
    if not isinstance(section, dict):
        raise KeyringFormatError(f"keyring {wrapper} section must be an object.")
    kdf = section.get("kdf")
    if kdf == KDF:
        if set(section) != {"kdf", "params", "wrapped_master_key"}:
            raise KeyringFormatError(f"keyring {wrapper} KDF parameters are invalid.")
        _decode_params(bsr2, section, wrapper)
    elif kdf == LEGACY_KDF:
        iterations = section.get("iterations")
        if (
            type(iterations) is not int
            or not LEGACY_MINIMUM_ITERATIONS <= iterations <= LEGACY_MAXIMUM_ITERATIONS
        ):
            raise KeyringFormatError(
                f"keyring {wrapper} iteration count is outside the supported range."
            )
        try:
            salt = bsr2.primitives.hex_decode(section.get("salt"))
        except (TypeError, AttributeError, bsr2.primitives.BrisartPrimitiveError) as exc:
            raise KeyringFormatError(f"keyring {wrapper} salt is invalid.") from exc
        if len(salt) != KDF_SALT_BYTES:
            raise KeyringFormatError(f"keyring {wrapper} salt is invalid.")
    else:
        raise KeyringFormatError(f"keyring {wrapper} uses an unsupported KDF.")
    if not is_envelope(section.get("wrapped_master_key")):
        raise KeyringFormatError(f"keyring {wrapper} wrapper is not a sealed payload.")


def _validate(state) -> dict:
    """Validate ``state`` and return its v2 view: ``state`` itself when it is
    v2, a converted copy when it is v1. ``state`` is never modified."""
    bsr2 = encryption.require()
    if not isinstance(state, dict):
        raise KeyringFormatError("keyring state must be an object.")
    if state.get("format") == LEGACY_KEYRING_FORMAT:
        state = _converted_legacy_state(state)
    if state.get("format") != KEYRING_FORMAT:
        raise KeyringFormatError("unsupported keyring format.")
    for wrapper in _WRAPPERS:
        _validate_wrapper(bsr2, state, wrapper)
    check = state.get("master_key_check")
    try:
        valid_check = (
            isinstance(check, dict)
            and check.get("mac") in (_CHECK_MAC, _LEGACY_CHECK_MAC)
            and len(bsr2.primitives.hex_decode(check.get("value"))) == 32
        )
    except (TypeError, AttributeError, bsr2.primitives.BrisartPrimitiveError):
        valid_check = False
    if not valid_check:
        raise KeyringFormatError("keyring master key check is invalid.")
    return state


class Keyring:
    """A master key wrapped under a passphrase and a recovery code.

    ``state`` is a plain JSON-serialisable dict holding no plaintext key
    material: KDF parameters and two sealed wrappers.
    """

    def __init__(self, state: dict):
        # _state is the caller's stored dict, written back by to_state();
        # _view is its v2 form, which every read uses. They are the same dict
        # except for a v1 keyring, which stays exactly as stored -- readable by
        # the release that wrote it -- until _wrap() replaces a wrapper.
        self._state = state
        self._view = _validate(state)
        self._master_key = None

    @classmethod
    def create(
        cls,
        passphrase: str,
        recovery_code: Optional[str] = None,
        memory_blocks: Optional[int] = None,
    ):
        """Build a keyring around a fresh master key.

        Returns ``(keyring, recovery_code)``. The recovery code is returned
        only here and never stored.
        """
        bsr2 = encryption.require()
        if memory_blocks is None:
            memory_blocks = MEMORY_BLOCKS
        passphrase_text = _normalize_passphrase(passphrase)
        recovery_text = (
            generate_recovery_code()
            if recovery_code is None
            else _normalize_recovery_code(recovery_code)
        )
        if (
            type(memory_blocks) is not int
            or not 64 <= memory_blocks <= MAXIMUM_MEMORY_BLOCKS
            or memory_blocks & (memory_blocks - 1)
        ):
            raise KeyringFormatError(
                f"memory_blocks must be a power of two from 64 to {MAXIMUM_MEMORY_BLOCKS}."
            )
        master_key = bsr2.entropy.system_entropy(MASTER_KEY_BYTES)
        keyring = cls.__new__(cls)
        keyring._master_key = master_key
        keyring._state = keyring._view = {"format": KEYRING_FORMAT}
        keyring._wrap(_WRAPPER_PASSPHRASE, passphrase_text, memory_blocks, "keyring-create")
        keyring._wrap(_WRAPPER_RECOVERY, recovery_text, memory_blocks, "keyring-create")
        _validate(keyring._state)
        return keyring, format_recovery_code(recovery_text)

    def _wrap(self, wrapper: str, secret_text: str, memory_blocks: int, purpose: str) -> None:
        """Seal the cached master key under a fresh BSR2-MHF-1 key for
        ``wrapper`` and refresh the check value."""
        bsr2 = encryption.require()
        if self._view is not self._state:
            # First write to a v1 keyring: from here on it is stored as v2.
            self._state.clear()
            self._state.update(self._view)
            self._view = self._state
        params = bsr2.kdf.new_params(
            memory_blocks=memory_blocks,
            passes=PASSES,
            salt=bsr2.entropy.system_entropy(KDF_SALT_BYTES),
        )
        section = {
            "kdf": KDF,
            "params": bsr2.primitives.hex_encode(params.encode()),
        }
        wrapping_key = _derive(bsr2, section, wrapper, secret_text)
        section["wrapped_master_key"] = seal_bytes(
            wrapping_key, self._master_key, keyring_context(wrapper), new_generator(purpose)
        )
        self._state[wrapper] = section
        self._state["master_key_check"] = {
            "mac": _CHECK_MAC,
            "value": bsr2.primitives.hex_encode(
                _check_value(bsr2, _CHECK_MAC, self._master_key)
            ),
        }

    def _unwrap(self, wrapper: str, secret_text: str) -> bytes:
        bsr2 = encryption.require()
        section = self._view[wrapper]
        wrapping_key = _derive(bsr2, section, wrapper, secret_text)
        try:
            master_key = open_bytes(
                wrapping_key, section["wrapped_master_key"], keyring_context(wrapper)
            )
        except Bsr2IntegrationError as exc:
            raise KeyringAuthenticationError(
                "unlock failed: incorrect secret or modified keyring."
            ) from exc
        if len(master_key) != MASTER_KEY_BYTES:
            raise KeyringFormatError("unwrapped master key has an invalid length.")
        check = self._view["master_key_check"]
        if not bsr2.primitives.constant_time_equal(
            _check_value(bsr2, check["mac"], master_key),
            bsr2.primitives.hex_decode(check["value"]),
        ):
            raise KeyringFormatError(
                "unwrapped master key does not match the keyring check value."
            )
        return master_key

    def unlock_with_passphrase(self, passphrase: str) -> bytes:
        """Unwrap and cache the master key using the passphrase."""
        self._master_key = self._unwrap(_WRAPPER_PASSPHRASE, _normalize_passphrase(passphrase))
        return self._master_key

    def unlock_with_recovery_code(self, recovery_code: str) -> bytes:
        """Unwrap and cache the master key using the recovery code."""
        self._master_key = self._unwrap(_WRAPPER_RECOVERY, _normalize_recovery_code(recovery_code))
        return self._master_key

    @property
    def is_unlocked(self) -> bool:
        return self._master_key is not None

    @property
    def master_key(self) -> bytes:
        if self._master_key is None:
            raise KeyringLockedError("keyring is locked; unlock it before using the master key.")
        return self._master_key

    def lock(self) -> None:
        """Drop the cached master key (best effort; see Known limitations)."""
        self._master_key = None

    def _rewrap_memory_blocks(self, wrapper: str) -> int:
        """Memory cost for a replacement wrapper: the wrapper's own when it is
        already BSR2-MHF-1, the default when it is legacy."""
        section = self._view[wrapper]
        if section["kdf"] != KDF:
            return MEMORY_BLOCKS
        return _decode_params(encryption.require(), section, wrapper).memory_blocks

    def change_passphrase(self, new_passphrase: str) -> None:
        """Re-wrap the master key under a new passphrase with BSR2-MHF-1."""
        if self._master_key is None:
            raise KeyringLockedError("unlock the keyring before changing its passphrase.")
        self._wrap(
            _WRAPPER_PASSPHRASE, _normalize_passphrase(new_passphrase),
            self._rewrap_memory_blocks(_WRAPPER_PASSPHRASE), "keyring-rewrap",
        )

    def rotate_recovery_code(self) -> str:
        """Issue a new recovery code, invalidating the previous one in this
        state. Returns it formatted for display."""
        if self._master_key is None:
            raise KeyringLockedError("unlock the keyring before rotating its recovery code.")
        recovery_text = generate_recovery_code()
        self._wrap(
            _WRAPPER_RECOVERY, recovery_text,
            self._rewrap_memory_blocks(_WRAPPER_RECOVERY), "keyring-rotate",
        )
        return format_recovery_code(recovery_text)

    @property
    def needs_migration(self) -> bool:
        """True while any part of the keyring uses the legacy construction."""
        return (
            any(self._view[wrapper]["kdf"] != KDF for wrapper in _WRAPPERS)
            or self._view["master_key_check"]["mac"] != _CHECK_MAC
        )

    def migrate(self, passphrase: str) -> Optional[str]:
        """Unlock with ``passphrase`` and replace every legacy part.

        Returns the new recovery code (formatted) when the recovery wrapper
        was legacy and had to be reissued, else None. Raises
        KeyringAuthenticationError, without changing anything, when the
        passphrase does not unlock the keyring.
        """
        passphrase_text = _normalize_passphrase(passphrase)
        self.unlock_with_passphrase(passphrase_text)
        if self._view[_WRAPPER_PASSPHRASE]["kdf"] != KDF:
            self._wrap(_WRAPPER_PASSPHRASE, passphrase_text, MEMORY_BLOCKS, "keyring-migrate")
        if self._view[_WRAPPER_RECOVERY]["kdf"] != KDF:
            return self.rotate_recovery_code()
        if self._view["master_key_check"]["mac"] != _CHECK_MAC:
            # Both wrappers are already current; only the check value is not.
            self._wrap(
                _WRAPPER_PASSPHRASE, passphrase_text,
                self._rewrap_memory_blocks(_WRAPPER_PASSPHRASE), "keyring-migrate",
            )
        return None

    def to_state(self) -> dict:
        """The live storable state. Holds no plaintext key material. A v1
        keyring is returned exactly as it was loaded until a wrapper is
        replaced."""
        return self._state

    def public_summary(self) -> dict:
        """Non-secret keyring metadata, for status output."""
        bsr2 = encryption.require()
        kdfs = {}
        for wrapper in _WRAPPERS:
            section = self._view[wrapper]
            if section["kdf"] == KDF:
                kdfs[wrapper] = _decode_params(bsr2, section, wrapper).describe()
            else:
                kdfs[wrapper] = f"{LEGACY_KDF} iterations={section['iterations']}"
        return {
            "format": self._state["format"],
            "passphrase_kdf": kdfs[_WRAPPER_PASSPHRASE],
            "recovery_kdf": kdfs[_WRAPPER_RECOVERY],
            "unlocked": self.is_unlocked,
        }


__all__ = [
    "KDF",
    "KEYRING_FORMAT",
    "LEGACY_KDF",
    "LEGACY_KEYRING_FORMAT",
    "MAXIMUM_MEMORY_BLOCKS",
    "MEMORY_BLOCKS",
    "Keyring",
    "format_recovery_code",
    "generate_recovery_code",
]
