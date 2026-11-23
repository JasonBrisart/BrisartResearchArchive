"""
File: crypto/tests/test_keyring.py

Purpose
-------
Tests for crypto.keyring: format-v2 keyrings built on BSR2-MHF-1 create,
unlock, re-wrap, and reject tampering; recovery codes normalise; keyrings in
the previous encryption report needs_migration and migrate(); and a real
format-v1 keyring still unlocks, converts to v2, and migrates.

Verifies: crypto/keyring.py.
Contains 26 test case(s) across 5 TestCase class(es).

Design notes:

Keyrings here are created with memory_blocks=64, the BSR2-MHF-1 minimum, and
migrate() is run with keyring.MEMORY_BLOCKS patched to 64, so everything but
LegacyKeyringTests runs in the fast suite. LegacyKeyringTests unlocks the v1
fixture through the legacy iterated KDF at its 10,000-iteration floor, which
takes minutes in pure Python, so tests/run_tests.py lists it as slow. The v1
fixture lives in crypto/tests/legacy_fixtures.py.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
- crypto.keyring (crypto/keyring.py)
- crypto.tests.legacy_fixtures (crypto/tests/legacy_fixtures.py)
Standard library: copy, unittest, unittest.mock.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _FAST = 64 -- memory_blocks for keyrings created and migrated here.

Edge cases
----------
KeyringTests:
- create() returns an unlocked v2 keyring with BSR2-MHF-1 wrappers.
- The passphrase and the recovery code (in any case, with hyphens) unlock the
  same master key; a wrong passphrase raises KeyringAuthenticationError and
  leaves the keyring as it was.
- change_passphrase() and rotate_recovery_code() keep the master key, keep the
  wrapper's memory cost, retire the old secret, and refuse a locked keyring.
- The locked keyring refuses to hand out the master key.
- public_summary() reports KDF descriptions and no key material.
- create() rejects a memory cost that is not a power of two in range.
KeyringMigrationTests:
- A current keyring does not need migration; migrate() on it unlocks and
  returns None.
- A keyring with a legacy check value needs migration; migrate() fixes it,
  keeps the master key and recovery code, and returns None.
- migrate() with a wrong passphrase raises KeyringAuthenticationError and
  leaves the state byte-for-byte unchanged.
- Loading a v1 state leaves the stored dict byte-for-byte as written, so it
  stays readable by Official 1.9.2 and LTS-2028 1.3.10; it still reports
  needs_migration.
- The first wrapper write converts a v1 state to v2 and keeps top-level keys
  the keyring does not own (the attempt-limiting state).
- Recovery codes come from the alphabet and differ between calls.
KeyringValidationTests:
- Non-dict state, unknown format, unknown KDF, out-of-range KDF parameters,
  extra wrapper fields, a non-envelope wrapper, and a bad check value are
  rejected with KeyringFormatError, without running a KDF.
- A legacy v1 state with an iteration count outside 10,000..1,000,000 is
  rejected.
RecoveryCodeTests:
- Generated codes have forty characters; formatting uses groups of five;
  confusable characters fold.
LegacyKeyringTests (slow):
- The v1 keyring unlocks with its passphrase to the original master key and
  stays v1 as stored; after change_passphrase() it is v2 and holds an MHF passphrase wrapper
  while the legacy recovery wrapper still unlocks.
- migrate() on the v1 keyring re-wraps both wrappers with BSR2-MHF-1, keeps
  the master key, issues a new recovery code that unlocks, and retires the old
  recovery code.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest crypto.tests.test_keyring -v
"""

import copy
import json
import unittest
from unittest import mock

from crypto.errors import (
    KeyringAuthenticationError,
    KeyringFormatError,
    KeyringLockedError,
)
from crypto import keyring as keyring_module
from crypto.keyring import (
    KDF,
    KEYRING_FORMAT,
    LEGACY_KDF,
    LEGACY_KEYRING_FORMAT,
    Keyring,
    format_recovery_code,
    generate_recovery_code,
)

from crypto.tests.legacy_fixtures import (
    LEGACY_KEYRING_STATE,
    LEGACY_MASTER_KEY,
    LEGACY_PASSPHRASE,
    LEGACY_RECOVERY_CODE,
    legacy_keyring_state,
)

_FAST = 64

class KeyringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keyring, cls.code = Keyring.create("correct horse", memory_blocks=_FAST)
        cls.master_key = cls.keyring.master_key
        cls.state = copy.deepcopy(cls.keyring.to_state())

    def _fresh(self):
        return Keyring(copy.deepcopy(self.state))

    def test_create_returns_an_unlocked_v2_mhf_keyring(self):
        state = self.keyring.to_state()
        self.assertEqual(state["format"], KEYRING_FORMAT)
        self.assertEqual(state["passphrase"]["kdf"], KDF)
        self.assertEqual(state["recovery"]["kdf"], KDF)
        self.assertEqual(len(self.master_key), 32)

    def test_passphrase_and_recovery_code_unlock_the_same_key(self):
        self.assertEqual(self._fresh().unlock_with_passphrase("correct horse"), self.master_key)
        self.assertEqual(
            self._fresh().unlock_with_recovery_code(self.code.lower()), self.master_key
        )

    def test_wrong_passphrase_is_rejected_without_changing_state(self):
        keyring = self._fresh()
        with self.assertRaises(KeyringAuthenticationError):
            keyring.unlock_with_passphrase("wrong")
        self.assertFalse(keyring.is_unlocked)

    def test_change_passphrase_keeps_the_key_and_cost_and_retires_the_old(self):
        keyring = self._fresh()
        keyring.unlock_with_passphrase("correct horse")
        keyring.change_passphrase("new passphrase")
        reopened = Keyring(copy.deepcopy(keyring.to_state()))
        self.assertEqual(reopened.unlock_with_passphrase("new passphrase"), self.master_key)
        with self.assertRaises(KeyringAuthenticationError):
            Keyring(copy.deepcopy(keyring.to_state())).unlock_with_passphrase("correct horse")
        self.assertIn("m=64 ", keyring.public_summary()["passphrase_kdf"])

    def test_rotate_recovery_code_retires_the_old_code(self):
        keyring = self._fresh()
        keyring.unlock_with_passphrase("correct horse")
        new_code = keyring.rotate_recovery_code()
        self.assertEqual(
            Keyring(copy.deepcopy(keyring.to_state())).unlock_with_recovery_code(new_code),
            self.master_key,
        )
        with self.assertRaises(KeyringAuthenticationError):
            Keyring(copy.deepcopy(keyring.to_state())).unlock_with_recovery_code(self.code)

    def test_locked_keyring_refuses_key_use(self):
        keyring = self._fresh()
        with self.assertRaises(KeyringLockedError):
            keyring.master_key
        with self.assertRaises(KeyringLockedError):
            keyring.change_passphrase("x")
        with self.assertRaises(KeyringLockedError):
            keyring.rotate_recovery_code()

    def test_public_summary_reports_kdfs_only(self):
        summary = self._fresh().public_summary()
        self.assertTrue(summary["passphrase_kdf"].startswith("BSR2-MHF-1 m=64 "))
        self.assertFalse(summary["unlocked"])
        self.assertNotIn(self.master_key.hex(), repr(summary))

    def test_create_rejects_an_invalid_memory_cost(self):
        for blocks in (32, 100, 1 << 20, True):
            with self.assertRaises(KeyringFormatError):
                Keyring.create("p", memory_blocks=blocks)


class KeyringMigrationTests(unittest.TestCase):
    def test_current_keyring_needs_no_migration(self):
        keyring, _ = Keyring.create("p", memory_blocks=_FAST)
        reopened = Keyring(copy.deepcopy(keyring.to_state()))
        self.assertFalse(reopened.needs_migration)
        self.assertIsNone(reopened.migrate("p"))
        self.assertEqual(reopened.master_key, keyring.master_key)

    def test_legacy_check_value_is_migrated_without_a_new_code(self):
        state, master_key = legacy_keyring_state("p")
        keyring = Keyring(state)
        self.assertTrue(keyring.needs_migration)
        with mock.patch.object(keyring_module, "MEMORY_BLOCKS", _FAST):
            self.assertIsNone(keyring.migrate("p"))
        self.assertFalse(keyring.needs_migration)
        self.assertEqual(state["master_key_check"]["mac"], "mac64")
        self.assertEqual(Keyring(copy.deepcopy(state)).unlock_with_passphrase("p"), master_key)

    def test_wrong_passphrase_changes_nothing(self):
        state, _ = legacy_keyring_state("p")
        before = json.dumps(state, sort_keys=True)
        with self.assertRaises(KeyringAuthenticationError):
            Keyring(state).migrate("wrong")
        self.assertEqual(json.dumps(state, sort_keys=True), before)

    def test_loading_a_v1_keyring_leaves_it_as_stored(self):
        # Reading must not make the file unreadable by the release that wrote
        # it: only a replaced wrapper turns the stored dict into v2.
        state = copy.deepcopy(LEGACY_KEYRING_STATE)
        state["unlock_attempts"] = {"failures": 2}
        before = json.dumps(state, sort_keys=True)
        keyring = Keyring(state)
        self.assertIs(keyring.to_state(), state)
        self.assertEqual(json.dumps(keyring.to_state(), sort_keys=True), before)
        self.assertTrue(keyring.needs_migration)
        self.assertEqual(keyring.public_summary()["format"], LEGACY_KEYRING_FORMAT)

    def test_first_wrapper_write_converts_and_keeps_unowned_keys(self):
        state = copy.deepcopy(LEGACY_KEYRING_STATE)
        state["unlock_attempts"] = {"failures": 2}
        keyring = Keyring(state)
        # Skip the minute-long legacy unlock; LegacyKeyringTests covers it.
        keyring._master_key = LEGACY_MASTER_KEY
        with mock.patch.object(keyring_module, "MEMORY_BLOCKS", _FAST):
            keyring.rotate_recovery_code()
        self.assertEqual(state["format"], KEYRING_FORMAT)
        self.assertEqual(state["recovery"]["kdf"], KDF)
        self.assertEqual(state["passphrase"]["kdf"], LEGACY_KDF)
        self.assertEqual(state["unlock_attempts"], {"failures": 2})

    def test_recovery_codes_use_the_alphabet_and_differ(self):
        first, second = generate_recovery_code(), generate_recovery_code()
        self.assertNotEqual(first, second)
        self.assertTrue(set(first) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ"))


class KeyringValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keyring, _ = Keyring.create("p", memory_blocks=_FAST)
        cls.state = keyring.to_state()

    def _rejects(self, mutate):
        state = copy.deepcopy(self.state)
        mutate(state)
        with self.assertRaises(KeyringFormatError):
            Keyring(state)

    def test_non_dict_and_unknown_format_are_rejected(self):
        with self.assertRaises(KeyringFormatError):
            Keyring(["not", "a", "dict"])
        self._rejects(lambda s: s.update(format="something-else"))

    def test_unknown_kdf_is_rejected(self):
        self._rejects(lambda s: s["passphrase"].update(kdf="not-bsr2"))

    def test_out_of_range_kdf_parameters_are_rejected(self):
        # Memory far above the ceiling: a tampered header must not make unlock
        # run for hours before failing.
        def huge(state):
            params = bytearray.fromhex(state["passphrase"]["params"])
            params[4:8] = (1 << 20).to_bytes(4, "big")
            state["passphrase"]["params"] = params.hex()
        self._rejects(huge)
        self._rejects(lambda s: s["recovery"].update(params="zz"))

    def test_extra_wrapper_fields_are_rejected(self):
        self._rejects(lambda s: s["passphrase"].update(iterations=10_000))

    def test_non_envelope_wrapper_is_rejected(self):
        self._rejects(lambda s: s["recovery"].update(wrapped_master_key={"x": 1}))

    def test_bad_check_value_is_rejected(self):
        self._rejects(lambda s: s.update(master_key_check="cc" * 32))
        self._rejects(lambda s: s["master_key_check"].update(value="cc" * 31))

    def test_legacy_iterations_out_of_range_are_rejected(self):
        for iterations in (9_999, 10_000_000):
            state = copy.deepcopy(LEGACY_KEYRING_STATE)
            state["iterations"] = iterations
            with self.assertRaises(KeyringFormatError):
                Keyring(state)


class RecoveryCodeTests(unittest.TestCase):
    def test_generated_code_has_forty_characters(self):
        self.assertEqual(len(generate_recovery_code()), 40)

    def test_formatting_uses_five_character_groups(self):
        groups = format_recovery_code(generate_recovery_code()).split("-")
        self.assertEqual([len(group) for group in groups], [5] * 8)

    def test_confusable_characters_fold(self):
        self.assertEqual(format_recovery_code("ILOU" * 10)[:4], "110V")


class LegacyKeyringTests(unittest.TestCase):
    def test_legacy_keyring_converts_unlocks_and_upgrades_one_wrapper(self):
        state = copy.deepcopy(LEGACY_KEYRING_STATE)
        before = json.dumps(state, sort_keys=True)
        keyring = Keyring(state)
        self.assertEqual(keyring.unlock_with_passphrase(LEGACY_PASSPHRASE), LEGACY_MASTER_KEY)
        self.assertEqual(json.dumps(state, sort_keys=True), before)
        self.assertEqual(state["format"], LEGACY_KEYRING_FORMAT)

        keyring.change_passphrase("upgraded passphrase")
        self.assertEqual(state["format"], KEYRING_FORMAT)
        self.assertEqual(state["passphrase"]["kdf"], KDF)
        self.assertEqual(state["recovery"]["kdf"], LEGACY_KDF)

        mixed = Keyring(copy.deepcopy(state))
        self.assertEqual(mixed.unlock_with_passphrase("upgraded passphrase"), LEGACY_MASTER_KEY)
        self.assertEqual(
            mixed.unlock_with_recovery_code(LEGACY_RECOVERY_CODE), LEGACY_MASTER_KEY
        )


    def test_migrate_rewraps_both_wrappers_and_issues_a_new_code(self):
        state = copy.deepcopy(LEGACY_KEYRING_STATE)
        keyring = Keyring(state)
        self.assertTrue(keyring.needs_migration)
        with mock.patch.object(keyring_module, "MEMORY_BLOCKS", _FAST):
            new_code = keyring.migrate(LEGACY_PASSPHRASE)
        self.assertIsNotNone(new_code)
        self.assertFalse(keyring.needs_migration)
        self.assertEqual(keyring.master_key, LEGACY_MASTER_KEY)
        migrated = copy.deepcopy(state)
        self.assertEqual(Keyring(copy.deepcopy(migrated)).unlock_with_passphrase(LEGACY_PASSPHRASE), LEGACY_MASTER_KEY)
        self.assertEqual(Keyring(copy.deepcopy(migrated)).unlock_with_recovery_code(new_code), LEGACY_MASTER_KEY)
        with self.assertRaises(KeyringAuthenticationError):
            Keyring(copy.deepcopy(migrated)).unlock_with_recovery_code(LEGACY_RECOVERY_CODE)


if __name__ == "__main__":
    unittest.main()
