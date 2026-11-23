"""
File: biometrics/identity/keyring_access.py

Purpose
-------
Single shared entry point for unlocking the biometrics BSR2 keyring
(data/keyring.json) with online-attempt throttling enforced identically for
every caller. Before this module existed, biometrics/app.py's CLI
(_unlock_keyring()) and gui/tabs/tab_biometrics.py's GUI (_ensure_keyring())
each called crypto.keyring.Keyring. unlock_with_passphrase() directly, and
neither consulted crypto.throttle.AttemptLimiter at all -- an attacker driving
either entry point in a loop against a running process paid no cost beyond
BSR2's own slow KDF, with no backoff and no lockout, and the two interfaces did
not even agree with each other on what (if anything) was enforced. Both entry
points now call unlock_with_passphrase() below instead, so the identical
throttling policy applies no matter which interface is used to reach it.

Public interface:
- class KeyringAccessError(ValueError) -- Raised for a refused or failed
  biometrics keyring unlock attempt, whether refused by the attempt-throttle
  gate or rejected by the underlying BSR2 unwrap itself.
- unlock_with_passphrase(keyring, path, passphrase) -- Unlock `keyring`
  (already constructed from the state stored at `path`) using `passphrase`,
  enforcing crypto.attempt_store throttling state persisted in the same file.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.atomic_io (common/atomic_io.py)
- crypto.attempt_store (crypto/attempt_store.py)
- crypto.errors (crypto/errors.py)
- crypto.keyring (crypto/keyring.py)
- crypto.throttle (crypto/throttle.py)
Standard library: json, pathlib.
Imported by:
- biometrics/app.py
- gui/tabs/tab_biometrics.py
Covered by tests: biometrics/tests/test_keyring_access.py.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
- unlock_with_passphrase() raises KeyringAccessError: "unlock refused: too many
  recent failed attempts; retry in {...} second(s)."
- unlock_with_passphrase() raises KeyringAccessError: "unlock failed: {...}"
- unlock_with_passphrase(): translates AttemptLockedOut into
  KeyringAccessError; other exceptions may still propagate.
- unlock_with_passphrase(): translates Bsr2IntegrationError into
  KeyringAccessError; other exceptions may still propagate.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: keyring, path, passphrase stand for
values the caller supplies.

::

    from biometrics.identity.keyring_access import unlock_with_passphrase
    unlock_with_passphrase(keyring, path, passphrase)
"""

import json
from pathlib import Path

from common.atomic_io import SENSITIVE_FILE_MODE, atomic_write_json
from crypto import attempt_store
from crypto.errors import Bsr2IntegrationError
from crypto.keyring import Keyring
from crypto.throttle import AttemptLockedOut


class KeyringAccessError(ValueError):
    """Raised for a refused or failed biometrics keyring unlock attempt,
    whether refused by the attempt-throttle gate or rejected by the
    underlying BSR2 unwrap itself."""


def _read_raw_state(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_raw_state(path: Path, raw_state: dict) -> None:
    atomic_write_json(path, raw_state, file_mode=SENSITIVE_FILE_MODE)


def unlock_with_passphrase(keyring: Keyring, path: Path, passphrase: str) -> bytes:
    """Unlock `keyring` (already constructed from the state stored at
    `path`) using `passphrase`, enforcing crypto.attempt_store throttling
    state persisted in the same file.

    Raises KeyringAccessError if the attempt budget is currently exhausted
    (before the passphrase is even attempted), or if the passphrase itself
    fails to unlock the keyring. Returns the unlocked master key on success.
    """
    raw_state = _read_raw_state(path)
    try:
        attempt_store.check_and_get_state(raw_state)
    except AttemptLockedOut as exc:
        raise KeyringAccessError(
            "unlock refused: too many recent failed attempts; retry in "
            f"{exc.retry_after_seconds:.0f} second(s)."
        ) from exc
    try:
        master_key = keyring.unlock_with_passphrase(passphrase)
    except Bsr2IntegrationError as exc:
        raw_state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(raw_state)
        _write_raw_state(path, raw_state)
        raise KeyringAccessError(f"unlock failed: {exc}") from exc
    raw_state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_success(raw_state)
    _write_raw_state(path, raw_state)
    return master_key


__all__ = ["KeyringAccessError", "unlock_with_passphrase"]




