"""
File: crypto/keyring.py

Purpose
-------
BSR2 keyring: a random master key wrapped under a passphrase and, separately,
under an offline recovery code. Everything else in the project (vault records,
biometric templates) is sealed under the master key, never directly under a
passphrase-derived key.

Public interface:
- generate_recovery_code() -- Generate a fresh 40-character recovery code (200
  bits) from a 32-symbol alphabet.
- format_recovery_code(code) -- Normalize a recovery code and format it as
  eight hyphen-separated groups of five for display or printing.
- class Keyring -- A master key wrapped under a passphrase and a recovery code.
- Keyring(state) -- Wrap an existing keyring state dict. Checks its structure
  only; the keyring starts locked.
- Keyring.create(passphrase, iterations=KDF_ITERATIONS, recovery_code=None) --
  Classmethod. Build a new keyring around a fresh random master key. Returns
  (keyring, recovery_code); the keyring comes back already unlocked.
- Keyring.unlock_with_passphrase(passphrase) -- Unwrap the master key, cache
  it, and return it.
- Keyring.unlock_with_recovery_code(recovery_code) -- Same, using the recovery
  code.
- Keyring.is_unlocked -- Property. True while the master key is cached.
- Keyring.master_key -- Property. The cached master key, or KeyringLockedError.
- Keyring.lock() -- Drop the cached master key.
- Keyring.change_passphrase(new_passphrase) -- Re-wrap the master key under a
  new passphrase. Requires an unlocked keyring.
- Keyring.rotate_recovery_code() -- Issue a new recovery code and return it,
  formatted. Requires an unlocked keyring.
- Keyring.to_state() -- The storable, JSON-serialisable state dict.
- Keyring.public_summary() -- Non-secret metadata for status output.

Design notes:

The design problem this solves: BSR2's derive_password_key is genuinely
expensive in pure Python (measured at roughly 70 seconds at its own enforced
minimum of 10,000 iterations, and around 14 minutes at its 120,000 default).
Deriving a key from the passphrase for every operation would be unusable, and
lowering the iteration count below BSR2's floor is not permitted by BSR2
itself.

The answer is standard key wrapping, which is what full-disk encryption has
always done for the same reason:

- The data is encrypted under a random 32-byte **master key**, never directly
  under a passphrase-derived key.
- The master key is sealed twice, once under a key derived from the passphrase
  and once under a key derived from an offline **recovery code**.
- Unlocking derives one KDF result, unwraps the master key, and holds it for
  the session. Every subsequent seal and open is fast.

Consequences that follow from this, and are deliberate:

- Changing the passphrase re-wraps the master key. It does not re-encrypt any
  data, because the master key does not change.
- The recovery code is a second full-strength path to the master key. Anyone
  holding it has the same access the passphrase gives. That is the price of
  recoverability, and it is why the code is shown exactly once and never
  stored.
- Losing both the passphrase and the recovery code is unrecoverable. There is
  no third path by design.

Cost model. Every key derivation costs the same. create() runs two (one per
wrapper); unlocking, change_passphrase(), and rotate_recovery_code() run one
each. At the 10,000-iteration floor that is on the order of a minute per
derivation, so create() takes a few minutes and an unlock about one. Once the
keyring is unlocked, sealing and opening data is fast.

Failed unlocks are deliberately uninformative. A wrong passphrase, a wrong but
well-formed recovery code, and a modified keyring all raise the same
KeyringAuthenticationError, so the caller learns that the unlock failed and
not why. A failed unlock does not change state: a keyring that was already
unlocked stays unlocked.

Where the state lives. A Keyring holds the state dict it is given, not a copy,
and to_state() returns that same live dict. change_passphrase() and
rotate_recovery_code() modify it in place and write nothing to disk, so the
caller must persist to_state() afterwards (vault/store/vault_file.py does this
for the vault). Until that happens, the file on disk still has the old
passphrase or recovery code.

Where attempt limiting lives. This class limits nothing about how often an
unlock may be tried. The KDF cost makes each offline guess slow, and the
throttle in crypto/throttle.py limits online guessing; it is applied by
biometrics/identity/keyring_access.py and vault/store/vault_service.py, not
here. The recovery code gets no extra protection from either: it relies on
being 200 bits long.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.rng (crypto/rng.py)
- crypto.vendor (crypto/vendor.py)
Standard library: secrets, typing, unicodedata.
Imported by:
- biometrics/app.py
- biometrics/identity/keyring_access.py
- gui/tabs/tab_biometrics.py
- vault/store/vault_file.py
- vault/store/vault_service.py
Covered by tests: biometrics/tests/test_keyring_access.py,
crypto/tests/test_keyring.py.

Settings / parameters
---------------------
- MASTER_KEY_BYTES = 32 -- Length of the master key and of every derived
  wrapping key (256 bits).
- KDF_SALT_BYTES = 32 -- Length of the random salt stored with each wrapper. A
  new salt is drawn whenever a wrapper is rebuilt.
- KDF_ITERATIONS = 10_000 -- Default iteration count, and BSR2's enforced
  minimum. It is the strongest setting that still lets an unlock finish in
  under a couple of minutes at roughly 7 ms per iteration. The count is stored
  in each keyring, so a different default would not invalidate existing ones.
- MAXIMUM_KDF_ITERATIONS = 1_000_000 -- Ceiling, checked by create() and when a
  state is loaded. Legitimate keyrings sit between 10,000 and 120,000; a
  tampered header with an astronomical count would otherwise make an unlock
  run for years before it could fail. Mirrors
  crypto.factors.MAXIMUM_ITERATIONS.
- RECOVERY_CODE_GROUPS = 8 -- Number of groups in a recovery code.
- RECOVERY_CODE_GROUP_SIZE = 5 -- Characters per group: 8 x 5 = 40 characters.
- _RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ" -- Crockford base32
  without I, L, O, U: no ambiguity when transcribed by hand.
- _CONFUSABLE_CHARACTERS = {"I": "1", "L": "1", "O": "0", "U": "V"} -- The
  characters excluded from the alphabet, mapped to their visual equivalents, so
  a code transcribed by hand still resolves.
- KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v1" -- Stored in every
  state; loading any other value raises KeyringFormatError.
- _WRAPPER_PASSPHRASE = "passphrase" -- Name of the passphrase wrapper section
  in the state, also bound into that wrapper's envelope via keyring_context().
- _WRAPPER_RECOVERY = "recovery" -- The same for the recovery wrapper.
- Keyring.create(iterations=KDF_ITERATIONS) -- Must be an exact int between
  10,000 and MAXIMUM_KDF_ITERATIONS.
- Keyring.create(recovery_code=None) -- Supply your own code instead of a
  generated one. It is normalized, and the code returned is its formatted form.

Edge cases
----------
All errors derive from Bsr2IntegrationError: KeyringFormatError (bad stored
state), KeyringAuthenticationError (unlock failed), and KeyringLockedError
(operation needs an unlocked keyring).

Input handling:
- Recovery codes are forgiving: hyphens and whitespace are stripped, case is
  folded, and I and L read as 1, O as 0, and U as V.
- Passphrases are normalized with NFKC, so the same text typed on another
  platform derives the same key. Surrounding whitespace is kept and counts.
- Argument problems (empty passphrase, malformed recovery code, iteration count
  out of range) fail immediately, before any key derivation runs.
- Keyring.create(iterations=True) or a float such as 10000.0 raises
  KeyringFormatError, not Bsr2IntegrationError, because the check is shared
  with state validation and accepts only an exact int.

Errors, in the order the code raises them:
- _normalize_recovery_code() raises Bsr2IntegrationError: "recovery code must
  be a string."
- _normalize_recovery_code() raises Bsr2IntegrationError: "recovery code
  contains characters outside its alphabet."
- _normalize_recovery_code() raises Bsr2IntegrationError: "recovery code must
  contain {...} characters, got {...}."
- _normalize_passphrase() raises Bsr2IntegrationError: "passphrase must be a
  string."
- _normalize_passphrase() raises Bsr2IntegrationError: "passphrase cannot be
  empty."
- _require_int() raises KeyringFormatError: "keyring {...} must be an integer."
- Keyring.create() raises Bsr2IntegrationError: "iteration count is below the
  BSR2 research minimum of 10,000."
- Keyring.create() raises Bsr2IntegrationError: "iteration count is above the
  {...} maximum."
- Keyring._validate() raises KeyringFormatError: "keyring state must be an
  object."
- Keyring._validate() raises KeyringFormatError: "unsupported keyring format."
- Keyring._validate() raises KeyringFormatError: "unsupported keyring KDF."
- Keyring._validate() raises KeyringFormatError: "keyring iteration count is
  below the BSR2 minimum."
- Keyring._validate() raises KeyringFormatError: "keyring iteration count is
  above the supported maximum."
- Keyring._validate() raises KeyringFormatError: "keyring {...} section must be
  an object."
- Keyring._validate() raises KeyringFormatError: "keyring {...} salt must be
  hexadecimal text."
- Keyring._validate() raises KeyringFormatError: "keyring {...} salt is not
  valid hexadecimal."
- Keyring._validate() raises KeyringFormatError: "keyring {...} salt has an
  invalid length."
- Keyring._validate() raises KeyringFormatError: "keyring {...} wrapper is not
  a BSR2 envelope."
- Keyring._validate() raises KeyringFormatError: "keyring master key check must
  be text."
- Keyring._validate() raises KeyringFormatError: "keyring master key check has
  an invalid length."
- Keyring._validate() raises KeyringFormatError: "keyring master key check is
  not valid hexadecimal."
- Keyring._unwrap() raises KeyringAuthenticationError: "unlock failed:
  incorrect secret or modified keyring."
- Keyring._unwrap() raises KeyringFormatError: "unwrapped master key has an
  invalid length."
- Keyring._unwrap() raises KeyringFormatError: "unwrapped master key does not
  match the keyring check value." This is raised after authentication has
  succeeded, and means the two wrappers hold different master keys.
- Keyring.master_key raises KeyringLockedError: "keyring is locked; unlock it
  before using the master key."
- Keyring.change_passphrase() raises KeyringLockedError: "unlock the keyring
  before changing its passphrase."
- Keyring.rotate_recovery_code() raises KeyringLockedError: "unlock the keyring
  before rotating its recovery code."

Translated errors:
- Keyring._unwrap(): translates (BrisartEnvelopeError, Bsr2IntegrationError)
  into KeyringAuthenticationError, so callers only need to handle this module's
  own error type.
- Keyring._validate(): translates BrisartPrimitiveError into
  KeyringFormatError, so callers only need to handle this module's own error
  type.

Loading is structural only: a keyring whose envelopes were modified still
loads, and fails with KeyringAuthenticationError only when unlocked.

Known limitations
-----------------
- Slow by design. Each unlock costs one key derivation (about a minute at the
  floor) and create() costs two. It cannot be made faster without going below
  BSR2's minimum iteration count, which BSR2 does not allow.
- No way to raise the iteration count of an existing keyring. The count is
  stored per keyring, but no method here changes it, and create() always draws
  a new master key, so strengthening a keyring means starting a new one.
- change_passphrase() does not ask for the old passphrase. Being unlocked is
  the only check, so whoever holds an unlocked Keyring object can change it.
- rotate_recovery_code() invalidates the old code only for the state it
  modifies. Any earlier copy of the keyring (a backup, a synced file) still
  opens with the old recovery code, and with the old passphrase after
  change_passphrase().
- lock() is best effort. It drops the cached reference, but Python cannot
  guarantee the bytes leave process memory, and any copy a caller kept from
  unlock_with_*() or master_key survives it.
- No attempt limiting or lockout in this class (see Design notes).
- No password strength check: any non-empty string is accepted as a passphrase.
- public_summary() always reports recovery_code_available as True. It is a
  constant, not read from the state.
- Not thread-safe. The state and the cached key are plain mutable attributes
  with no locking, so share one Keyring between threads only with your own
  synchronization.
- The 10,000 floor is written as a literal in both create() and _validate(),
  not as a shared constant, so the two must be changed together.
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Run from the repository root. The default iteration count makes create() and
each unlock slow (see Design notes).

::

    from crypto.keyring import (
        Keyring,
        format_recovery_code,
        generate_recovery_code,
    )

    # Create: two key derivations. The recovery code is returned only here.
    keyring, recovery_code = Keyring.create("correct horse battery staple")
    print(recovery_code)            # store it offline; it is never saved
    state = keyring.to_state()      # JSON-serialisable; persist this

    # Reopen later: validates structure, then one derivation to unlock.
    keyring = Keyring(state)
    keyring.unlock_with_passphrase("correct horse battery staple")
    master_key = keyring.master_key
    keyring.lock()

    # Recovery path. Case, spaces, and hyphens do not matter.
    keyring.unlock_with_recovery_code(recovery_code.lower())

    # The state is changed in place and not saved for you: persist it again.
    keyring.change_passphrase("a new passphrase")
    state = keyring.to_state()

    # Generate and format a standalone code.
    code = generate_recovery_code()
    print(format_recovery_code(code))
"""

import secrets
import unicodedata
from typing import Optional

from crypto.context import keyring_context
from crypto.envelope import is_envelope, open_bytes, seal_bytes
from crypto.errors import (
    Bsr2IntegrationError,
    KeyringAuthenticationError,
    KeyringFormatError,
    KeyringLockedError,
)
from crypto.rng import new_generator
from crypto.vendor import (
    BrisartEnvelopeError,
    BrisartPrimitiveError,
    constant_time_equal,
    derive_password_key,
    hex_decode,
    hex_encode,
    keyed_mac,
)

MASTER_KEY_BYTES = 32
KDF_SALT_BYTES = 32

# BSR2 enforces a 10,000 floor and defaults to 120,000. At roughly 7 ms per
# iteration in pure Python, the floor already costs about 70 seconds per
# derivation. That is the value used here: it is the strongest setting BSR2
# permits that still allows an unlock to complete in under a couple of minutes,
# and because unlocking happens once per session rather than per operation, the
# cost is paid once. Recorded per keyring so it can be raised later without
# invalidating existing keyrings.
KDF_ITERATIONS = 10_000

# Upper bound mirroring crypto.factors.MAXIMUM_ITERATIONS. Legitimate
# keyrings sit at 10,000..120,000; a tampered header carrying an astronomical
# count would otherwise make an unlock derive for years before it can fail.
MAXIMUM_KDF_ITERATIONS = 1_000_000

RECOVERY_CODE_GROUPS = 8
RECOVERY_CODE_GROUP_SIZE = 5

# Crockford base32 without I, L, O, U: no ambiguity when transcribed by hand.
_RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# The characters excluded from the alphabet, mapped to their visual equivalents,
# so a code transcribed by hand still resolves.
_CONFUSABLE_CHARACTERS = {"I": "1", "L": "1", "O": "0", "U": "V"}

KEYRING_FORMAT = "brisart-identity-tools/bsr2-keyring/v1"

_WRAPPER_PASSPHRASE = "passphrase"
_WRAPPER_RECOVERY = "recovery"


def generate_recovery_code() -> str:
    """Generate a fresh recovery code.

    Forty characters from a 32-symbol alphabet is 200 bits, drawn from
    ``secrets.choice``. Well beyond any brute-force reach, which matters because
    this code is a direct path to the master key and gets no attempt limiting
    once an attacker has the keyring file.
    """
    characters = [
        secrets.choice(_RECOVERY_ALPHABET)
        for _ in range(RECOVERY_CODE_GROUPS * RECOVERY_CODE_GROUP_SIZE)
    ]
    return "".join(characters)


def format_recovery_code(code: str) -> str:
    """Format a recovery code in readable groups for display or printing."""
    normalized = _normalize_recovery_code(code)
    return "-".join(
        normalized[index:index + RECOVERY_CODE_GROUP_SIZE]
        for index in range(0, len(normalized), RECOVERY_CODE_GROUP_SIZE)
    )


def _normalize_recovery_code(code: str) -> str:
    """Normalise a typed recovery code.

    Hyphens and spaces are stripped, case is folded, and the characters excluded
    from the alphabet are mapped to their visual equivalents, so a code
    transcribed by hand still works.
    """
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
    # NFKC so a passphrase typed on a different platform or keyboard layout does
    # not derive a different key purely through Unicode composition.
    return unicodedata.normalize("NFKC", passphrase)


def _derive_wrapping_key(secret_text: str, salt: bytes, iterations: int) -> bytes:
    """Derive a wrapping key from a passphrase or recovery code using BSR2."""
    return derive_password_key(
        secret_text,
        salt,
        iterations=iterations,
        output_bytes=MASTER_KEY_BYTES,
    )


def _require_int(value, name: str) -> int:
    if type(value) is not int:
        raise KeyringFormatError(f"keyring {name} must be an integer.")
    return value


class Keyring:
    """A master key wrapped under a passphrase and a recovery code.

    ``state`` is a plain JSON-serialisable dict, so it can live inside a vault
    header or a standalone file. It contains no plaintext key material: only
    salts, iteration counts, and two BSR2 envelopes.
    """

    def __init__(self, state: dict):
        self._state = self._validate(state)
        self._master_key = None

    # ---------------------------------------------------------------- creation
    @classmethod
    def create(
        cls,
        passphrase: str,
        iterations: int = KDF_ITERATIONS,
        recovery_code: Optional[str] = None,
    ):
        """Build a new keyring around a fresh random master key.

        Returns ``(keyring, recovery_code)``. The recovery code is returned only
        here and never stored in recoverable form, so a caller that discards it
        cannot get it back.
        """
        passphrase_text = _normalize_passphrase(passphrase)
        iterations = _require_int(iterations, "iterations")
        if iterations < 10_000:
            # Mirrors BSR2's own floor. Stated explicitly so the failure names
            # the real constraint rather than surfacing a primitive error.
            raise Bsr2IntegrationError(
                "iteration count is below the BSR2 research minimum of 10,000."
            )
        if iterations > MAXIMUM_KDF_ITERATIONS:
            raise Bsr2IntegrationError(
                f"iteration count is above the {MAXIMUM_KDF_ITERATIONS} maximum."
            )
        if recovery_code is None:
            recovery_text = generate_recovery_code()
        else:
            recovery_text = _normalize_recovery_code(recovery_code)
        master_key = secrets.token_bytes(MASTER_KEY_BYTES)
        rng = new_generator("keyring-create")
        passphrase_salt = secrets.token_bytes(KDF_SALT_BYTES)
        recovery_salt = secrets.token_bytes(KDF_SALT_BYTES)
        passphrase_key = _derive_wrapping_key(
            passphrase_text, passphrase_salt, iterations
        )
        recovery_key = _derive_wrapping_key(
            recovery_text, recovery_salt, iterations
        )
        state = {
            "format": KEYRING_FORMAT,
            "kdf": "BSR2/derive_password_key",
            "iterations": iterations,
            "passphrase": {
                "salt": hex_encode(passphrase_salt),
                "wrapped_master_key": seal_bytes(
                    passphrase_key,
                    master_key,
                    keyring_context(_WRAPPER_PASSPHRASE),
                    rng,
                ),
            },
            "recovery": {
                "salt": hex_encode(recovery_salt),
                "wrapped_master_key": seal_bytes(
                    recovery_key,
                    master_key,
                    keyring_context(_WRAPPER_RECOVERY),
                    rng,
                ),
            },
            "master_key_check": hex_encode(cls._check_value(master_key)),
        }
        keyring = cls(state)
        keyring._master_key = master_key
        return keyring, format_recovery_code(recovery_text)

    # -------------------------------------------------------------- validation
    @staticmethod
    def _validate(state: dict) -> dict:
        if not isinstance(state, dict):
            raise KeyringFormatError("keyring state must be an object.")
        if state.get("format") != KEYRING_FORMAT:
            raise KeyringFormatError("unsupported keyring format.")
        if state.get("kdf") != "BSR2/derive_password_key":
            raise KeyringFormatError("unsupported keyring KDF.")
        iterations = _require_int(state.get("iterations"), "iterations")
        if iterations < 10_000:
            # A tampered keyring header could otherwise request a cheap
            # derivation and make the KDF trivially brute-forceable.
            raise KeyringFormatError(
                "keyring iteration count is below the BSR2 minimum."
            )
        if iterations > MAXIMUM_KDF_ITERATIONS:
            # The opposite tamper: an astronomical count that turns unlock into
            # a years-long hang before authentication can fail.
            raise KeyringFormatError(
                "keyring iteration count is above the supported maximum."
            )
        for wrapper in (_WRAPPER_PASSPHRASE, _WRAPPER_RECOVERY):
            section = state.get(wrapper)
            if not isinstance(section, dict):
                raise KeyringFormatError(
                    f"keyring {wrapper} section must be an object."
                )
            salt_text = section.get("salt")
            if not isinstance(salt_text, str):
                raise KeyringFormatError(
                    f"keyring {wrapper} salt must be hexadecimal text."
                )
            try:
                salt = hex_decode(salt_text)
            except BrisartPrimitiveError as exc:
                raise KeyringFormatError(
                    f"keyring {wrapper} salt is not valid hexadecimal."
                ) from exc
            if len(salt) != KDF_SALT_BYTES:
                raise KeyringFormatError(
                    f"keyring {wrapper} salt has an invalid length."
                )
            if not is_envelope(section.get("wrapped_master_key")):
                raise KeyringFormatError(
                    f"keyring {wrapper} wrapper is not a BSR2 envelope."
                )
        check = state.get("master_key_check")
        if not isinstance(check, str):
            raise KeyringFormatError("keyring master key check must be text.")
        try:
            if len(hex_decode(check)) != 32:
                raise KeyringFormatError(
                    "keyring master key check has an invalid length."
                )
        except BrisartPrimitiveError as exc:
            raise KeyringFormatError(
                "keyring master key check is not valid hexadecimal."
            ) from exc
        return state

    @staticmethod
    def _check_value(master_key: bytes) -> bytes:
        """A MAC over a fixed string, used to confirm an unwrap produced the
        expected master key.

        The BSR2 tag already authenticates each wrapper, so this is a redundancy
        check: it catches a keyring whose two wrappers hold *different* master
        keys, which would otherwise show up much later as unopenable data.
        """
        return keyed_mac(
            master_key,
            b"BrisartIdentityTools/keyring/master-key-check/v1",
            32,
        )

    # ------------------------------------------------------------------ unlock
    def _unwrap(self, wrapper: str, secret_text: str) -> bytes:
        section = self._state[wrapper]
        salt = hex_decode(section["salt"])
        wrapping_key = _derive_wrapping_key(
            secret_text, salt, self._state["iterations"]
        )
        try:
            master_key = open_bytes(
                wrapping_key,
                section["wrapped_master_key"],
                keyring_context(wrapper),
            )
        except (BrisartEnvelopeError, Bsr2IntegrationError) as exc:
            # Deliberately uniform: the caller learns the unlock failed, not
            # whether the envelope was structurally valid.
            raise KeyringAuthenticationError(
                "unlock failed: incorrect secret or modified keyring."
            ) from exc
        if len(master_key) != MASTER_KEY_BYTES:
            raise KeyringFormatError("unwrapped master key has an invalid length.")
        if not constant_time_equal(
            self._check_value(master_key), hex_decode(self._state["master_key_check"])
        ):
            raise KeyringFormatError(
                "unwrapped master key does not match the keyring check value."
            )
        return master_key

    def unlock_with_passphrase(self, passphrase: str) -> bytes:
        """Unwrap and cache the master key using the passphrase."""
        master_key = self._unwrap(
            _WRAPPER_PASSPHRASE, _normalize_passphrase(passphrase)
        )
        self._master_key = master_key
        return master_key

    def unlock_with_recovery_code(self, recovery_code: str) -> bytes:
        """Unwrap and cache the master key using the recovery code."""
        master_key = self._unwrap(
            _WRAPPER_RECOVERY, _normalize_recovery_code(recovery_code)
        )
        self._master_key = master_key
        return master_key

    @property
    def is_unlocked(self) -> bool:
        return self._master_key is not None

    @property
    def master_key(self) -> bytes:
        if self._master_key is None:
            raise KeyringLockedError(
                "keyring is locked; unlock it before using the master key."
            )
        return self._master_key

    def lock(self) -> None:
        """Drop the cached master key.

        Python cannot guarantee the bytes leave process memory, so this reduces
        exposure rather than eliminating it. Claiming otherwise would be false.
        """
        self._master_key = None

    # ----------------------------------------------------------- modification
    def change_passphrase(self, new_passphrase: str) -> None:
        """Re-wrap the master key under a new passphrase.

        Requires the keyring to be unlocked. No stored data is re-encrypted,
        because the master key itself does not change.
        """
        if self._master_key is None:
            raise KeyringLockedError(
                "unlock the keyring before changing its passphrase."
            )
        passphrase_text = _normalize_passphrase(new_passphrase)
        salt = secrets.token_bytes(KDF_SALT_BYTES)
        wrapping_key = _derive_wrapping_key(
            passphrase_text, salt, self._state["iterations"]
        )
        rng = new_generator("keyring-rewrap")
        self._state["passphrase"] = {
            "salt": hex_encode(salt),
            "wrapped_master_key": seal_bytes(
                wrapping_key,
                self._master_key,
                keyring_context(_WRAPPER_PASSPHRASE),
                rng,
            ),
        }

    def rotate_recovery_code(self) -> str:
        """Issue a new recovery code, invalidating the previous one.

        Returns the new code formatted for display. Requires an unlocked keyring.
        """
        if self._master_key is None:
            raise KeyringLockedError(
                "unlock the keyring before rotating its recovery code."
            )
        recovery_text = generate_recovery_code()
        salt = secrets.token_bytes(KDF_SALT_BYTES)
        wrapping_key = _derive_wrapping_key(
            recovery_text, salt, self._state["iterations"]
        )
        rng = new_generator("keyring-rotate")
        self._state["recovery"] = {
            "salt": hex_encode(salt),
            "wrapped_master_key": seal_bytes(
                wrapping_key,
                self._master_key,
                keyring_context(_WRAPPER_RECOVERY),
                rng,
            ),
        }
        return format_recovery_code(recovery_text)

    # ------------------------------------------------------------------ export
    def to_state(self) -> dict:
        """Return the storable keyring state.

        Contains no plaintext key material, so it is safe to write to disk
        alongside the data it protects.
        """
        return self._state

    def public_summary(self) -> dict:
        """Non-secret keyring metadata, for status output."""
        return {
            "format": self._state["format"],
            "kdf": self._state["kdf"],
            "iterations": self._state["iterations"],
            "recovery_code_available": True,
            "unlocked": self.is_unlocked,
        }




