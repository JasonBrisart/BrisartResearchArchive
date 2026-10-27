"""
File: crypto/attempt_store.py

Purpose
-------
Shared persistence adapter between crypto.throttle.AttemptLimiter (pure
in-memory backoff/lockout math) and the on-disk JSON containers that actually
hold unlock state for this ecosystem: vault.json (vault/store/ vault_file.py)
and the biometrics keyring.json (biometrics/identity/ keyring_access.py).
AttemptLimiter itself has no opinion about where its state lives -- its own
docstring says state is "caller-persisted, not held in memory" -- and until
this module existed, no caller in this repository actually persisted it
anywhere. This module is that missing wiring: a thin adapter that reads/writes
a single well-known field (ATTEMPT_STATE_FIELD) on whatever JSON-shaped dict a
caller already has open, so every unlock path in the ecosystem stores its
throttle state the same way instead of each inventing its own container shape.

Public interface:
- check_and_get_state(container, limiter=None) -- Raise AttemptLockedOut if an
  unlock attempt is not allowed yet.
- record_failure(container, limiter=None) -- Return updated attempt state after
  a failed unlock attempt.
- record_success(container, limiter=None) -- Return cleared attempt state after
  a successful unlock attempt.
- status(container, limiter=None) -- Report attempt state for display; never
  raises AttemptLockedOut. A stored state that is not an object is rejected
  with Bsr2IntegrationError.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.throttle (crypto/throttle.py)
Standard library: none.
Imported by:
- biometrics/identity/keyring_access.py
- vault/store/vault_service.py
Covered by tests: biometrics/tests/test_keyring_access.py,
crypto/tests/test_attempt_store.py, vault/tests/test_unlock_throttle.py.

Settings / parameters
---------------------
- ATTEMPT_STATE_FIELD = "unlock_attempts"
- _DEFAULT_LIMITER = AttemptLimiter()

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
Call shapes only, not a runnable script: container stands for a value the
caller supplies.

::

    from crypto.attempt_store import (
        check_and_get_state,
        record_failure,
        record_success,
    )
    check_and_get_state(container)
    record_failure(container)
    record_success(container)
"""

from crypto.throttle import AttemptLimiter

ATTEMPT_STATE_FIELD = "unlock_attempts"

_DEFAULT_LIMITER = AttemptLimiter()


def check_and_get_state(container: dict, limiter: AttemptLimiter = None) -> dict:
    """Raise AttemptLockedOut if an unlock attempt is not allowed yet.

    Returns the normalized attempt state on success (mirroring
    AttemptLimiter.check()'s own return value); callers are not required to
    use the return value, since record_failure()/record_success() each
    re-normalize the state themselves.
    """
    active_limiter = limiter or _DEFAULT_LIMITER
    return active_limiter.check(container.get(ATTEMPT_STATE_FIELD))


def record_failure(container: dict, limiter: AttemptLimiter = None) -> dict:
    """Return updated attempt state after a failed unlock attempt.

    Does not mutate or persist `container`; the caller assigns the return
    value to container[ATTEMPT_STATE_FIELD] and saves `container` itself.
    """
    active_limiter = limiter or _DEFAULT_LIMITER
    return active_limiter.record_failure(container.get(ATTEMPT_STATE_FIELD))


def record_success(container: dict, limiter: AttemptLimiter = None) -> dict:
    """Return cleared attempt state after a successful unlock attempt."""
    active_limiter = limiter or _DEFAULT_LIMITER
    return active_limiter.record_success(container.get(ATTEMPT_STATE_FIELD))


def status(container: dict, limiter: AttemptLimiter = None) -> dict:
    """Report attempt state for display; never raises AttemptLockedOut.

    A stored state that is not an object is rejected with Bsr2IntegrationError.
    """
    active_limiter = limiter or _DEFAULT_LIMITER
    return active_limiter.status(container.get(ATTEMPT_STATE_FIELD))


__all__ = [
    "ATTEMPT_STATE_FIELD",
    "check_and_get_state",
    "record_failure",
    "record_success",
    "status",
]




