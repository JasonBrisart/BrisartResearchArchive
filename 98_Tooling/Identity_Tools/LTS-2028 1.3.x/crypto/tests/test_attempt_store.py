"""
File: crypto/tests/test_attempt_store.py

Purpose
-------
Tests for crypto.attempt_store: the container-field adapter between
crypto.throttle.AttemptLimiter and the on-disk JSON containers (vault.json,
biometrics keyring.json) that persist unlock-attempt state.

Verifies: crypto/attempt_store.py, crypto/throttle.py.
Contains 8 test case(s) across 1 TestCase class(es).

Design notes:

All tests here inject their own AttemptLimiter (with a fake time_source, and
usually a low max_attempts) rather than relying on the shared module-level
default, so lockout/backoff behavior is exercised deterministically and fast --
consistent with crypto/tests/test_throttle.py's own approach. Fast: no KDF
involved anywhere in this file.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.attempt_store (crypto/attempt_store.py)
- crypto.throttle (crypto/throttle.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
- Fresh container has no attempt field.
- Record failure returns state the caller can store.
- Reaching max attempts locks out the container.
- Record success clears a locked out container.
- Status never raises even when locked out.
- Recovery code and passphrase share one counter.
- Default limiter is used when none supplied.
- Attempt state field name is stable.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.
- Passing proves only the 8 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest crypto.tests.test_attempt_store -v
    python tests/run_tests.py
"""

import unittest

from crypto import attempt_store
from crypto.throttle import AttemptLimiter, AttemptLockedOut


class _Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class AttemptStoreTests(unittest.TestCase):
    def setUp(self):
        self.clock = _Clock()
        self.limiter = AttemptLimiter(
            max_attempts=3, base_delay_seconds=1.0, max_delay_seconds=100.0,
            lockout_seconds=60.0, time_source=self.clock,
        )

    def test_fresh_container_has_no_attempt_field(self):
        container = {"format": "x", "records": {}}
        # Must not raise, and must not require the field to pre-exist.
        attempt_store.check_and_get_state(container, limiter=self.limiter)

    def test_record_failure_returns_state_the_caller_can_store(self):
        container = {}
        updated = attempt_store.record_failure(container, limiter=self.limiter)
        self.assertEqual(updated["failed_attempts"], 1)
        container[attempt_store.ATTEMPT_STATE_FIELD] = updated
        self.assertEqual(
            container[attempt_store.ATTEMPT_STATE_FIELD]["failed_attempts"], 1
        )

    def test_reaching_max_attempts_locks_out_the_container(self):
        container = {}
        for _ in range(3):
            container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(
                container, limiter=self.limiter
            )
        with self.assertRaises(AttemptLockedOut):
            attempt_store.check_and_get_state(container, limiter=self.limiter)

    def test_record_success_clears_a_locked_out_container(self):
        container = {}
        for _ in range(3):
            container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(
                container, limiter=self.limiter
            )
        container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_success(
            container, limiter=self.limiter
        )
        # No longer locked out; check_and_get_state must not raise.
        attempt_store.check_and_get_state(container, limiter=self.limiter)

    def test_status_never_raises_even_when_locked_out(self):
        container = {}
        for _ in range(3):
            container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(
                container, limiter=self.limiter
            )
        report = attempt_store.status(container, limiter=self.limiter)
        self.assertTrue(report["locked"])

    def test_recovery_code_and_passphrase_share_one_counter(self):
        # Mirrors vault_service.py's design: both unlock methods read and
        # write the SAME field, so alternating between them does not reset
        # an attacker's attempt budget.
        container = {}
        container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(
            container, limiter=self.limiter
        )  # a failed passphrase attempt
        container[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(
            container, limiter=self.limiter
        )  # a failed recovery-code attempt against the same field
        self.assertEqual(
            container[attempt_store.ATTEMPT_STATE_FIELD]["failed_attempts"], 2
        )

    def test_default_limiter_is_used_when_none_supplied(self):
        # Exercises the production code path (no limiter override) with a
        # single call; must not raise for fresh state.
        container = {}
        attempt_store.check_and_get_state(container)

    def test_attempt_state_field_name_is_stable(self):
        # Regression guard: renaming this constant would silently orphan
        # attempt state already persisted in existing vault/keyring files.
        self.assertEqual(attempt_store.ATTEMPT_STATE_FIELD, "unlock_attempts")


if __name__ == "__main__":
    unittest.main()




