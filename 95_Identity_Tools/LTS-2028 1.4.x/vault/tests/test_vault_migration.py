"""
File: vault/tests/test_vault_migration.py

Purpose
-------
Tests for the vault's encryption migration: a vault holding records in the
previous encryption still opens and reads (backward compatibility), and
VaultService.migrate_encryption() re-encrypts every record, migrates the
keyring, and writes the file once.

Verifies: vault/store/vault_service.py (needs_encryption_migration,
VaultService.migrate_encryption), crypto/envelope.py, crypto/keyring.py.
Contains 8 test case(s) across 2 TestCase class(es).

Design notes:

Legacy vaults are assembled directly in the vault file format: the keyring
from crypto/tests/legacy_fixtures.py and records sealed with its legacy
writers, under exactly the contexts VaultService uses. VaultMigrationTests uses
a keyring whose only legacy part is its check value and patches
crypto.keyring.MEMORY_BLOCKS to 64, so it runs in the fast suite.
LegacyKeyringVaultMigrationTests uses the real v1 keyring fixture, whose
unlock runs the legacy iterated KDF, and is listed as slow in
tests/run_tests.py.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.keyring (crypto/keyring.py)
- crypto.tests.legacy_fixtures (crypto/tests/legacy_fixtures.py)
- vault.core.time_tools (vault/core/time_tools.py)
- vault.records.record_model (vault/records/record_model.py)
- vault.store.vault_file (vault/store/vault_file.py)
- vault.store.vault_service (vault/store/vault_service.py)
Standard library: copy, json, pathlib, tempfile, unittest, unittest.mock.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _PASSPHRASE = "correct horse battery staple"

Edge cases
----------
VaultMigrationTests:
- A legacy vault reports needs_encryption_migration and still unlocks and
  reads every record with the previous encryption.
- migrate_encryption() re-encrypts JSON and file records, migrates the
  keyring check value, keeps every payload byte-identical, and leaves nothing
  needing migration.
- A wrong passphrase raises VaultServiceError and leaves keyring and records
  unchanged.
- A record that fails to authenticate under its stored context is left legacy
  and reported; the others migrate.
- A second run migrates nothing and reports no recovery code.
LegacyKeyringVaultMigrationTests (slow):
- Unlocking and reading a vault on the real v1 keyring, without migrating,
  leaves the file as written apart from attempt state, so Official 1.9.2 and LTS-2028 1.3.10
  can still open it.
- A vault on the real v1 keyring migrates; the new recovery code unlocks it
  and the old one no longer does.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest vault.tests.test_vault_migration -v
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from crypto import keyring as keyring_module
from crypto.context import record_context
from crypto.envelope import is_legacy
from crypto.tests.legacy_fixtures import (
    LEGACY_KEYRING_STATE,
    LEGACY_MASTER_KEY,
    LEGACY_PASSPHRASE,
    LEGACY_RECOVERY_CODE,
    legacy_keyring_state,
    seal_legacy_bytes,
    seal_legacy_json,
)
from vault.core.time_tools import stamp_new_record
from vault.records.record_model import new_record
from vault.store.vault_file import VAULT_FORMAT, save_state
from vault.store.vault_service import VaultService, VaultServiceError, needs_encryption_migration

_PASSPHRASE = "correct horse battery staple"


def _write_legacy_vault(path, keyring_state, master_key):
    records = {}
    for record_id, label, kind, payload in (
        ("rec-json-1", "email password", "credential", {"secret": "hunter2"}),
        ("rec-json-2", "note", "note", {"text": "line one\nline two"}),
    ):
        envelope = seal_legacy_json(master_key, payload, record_context(record_id, kind, label))
        records[record_id] = new_record(record_id, label, kind, envelope, stamp_new_record())
    file_envelope = seal_legacy_bytes(
        master_key, b"\x00binary\xffcontent", record_context("rec-file", "file", "image.bin")
    )
    records["rec-file"] = new_record("rec-file", "image.bin", "file", file_envelope, stamp_new_record())
    save_state(path, {"format": VAULT_FORMAT, "keyring": keyring_state, "records": records})


def _sections(path):
    state = json.loads(Path(path).read_text())
    return json.dumps(state["keyring"], sort_keys=True), json.dumps(state["records"], sort_keys=True)


class VaultMigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "vault.json"
        keyring_state, self.master_key = legacy_keyring_state(_PASSPHRASE)
        _write_legacy_vault(self.path, keyring_state, self.master_key)
        patcher = mock.patch.object(keyring_module, "MEMORY_BLOCKS", 64)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def test_legacy_vault_still_opens_and_reads(self):
        self.assertTrue(needs_encryption_migration(self.path))
        service = VaultService(self.path)
        service.unlock(_PASSPHRASE)
        self.assertEqual(service.get("rec-json-1"), {"secret": "hunter2"})
        self.assertEqual(service.get_file_bytes("rec-file"), b"\x00binary\xffcontent")

    def test_migration_reencrypts_everything_and_keeps_content(self):
        result = VaultService(self.path).migrate_encryption(_PASSPHRASE)
        self.assertEqual(result["records_migrated"], 3)
        self.assertEqual(result["records_not_migrated"], [])
        self.assertIsNone(result["recovery_code"])
        self.assertFalse(needs_encryption_migration(self.path))
        state = json.loads(self.path.read_text())
        self.assertFalse(any(is_legacy(record["payload"]) for record in state["records"].values()))
        service = VaultService(self.path)
        self.assertEqual(service.unlock(_PASSPHRASE), self.master_key)
        self.assertEqual(service.get("rec-json-1"), {"secret": "hunter2"})
        self.assertEqual(service.get("rec-json-2"), {"text": "line one\nline two"})
        self.assertEqual(service.get_file_bytes("rec-file"), b"\x00binary\xffcontent")

    def test_wrong_passphrase_changes_nothing(self):
        before = _sections(self.path)
        with self.assertRaises(VaultServiceError):
            VaultService(self.path).migrate_encryption("wrong passphrase")
        self.assertEqual(_sections(self.path), before)
        self.assertTrue(needs_encryption_migration(self.path))

    def test_unauthenticated_record_is_left_and_reported(self):
        state = json.loads(self.path.read_text())
        state["records"]["rec-json-2"]["label"] = "renamed"  # context no longer matches
        save_state(self.path, state)
        result = VaultService(self.path).migrate_encryption(_PASSPHRASE)
        self.assertEqual(result["records_migrated"], 2)
        self.assertEqual(result["records_not_migrated"], ["rec-json-2"])
        self.assertTrue(is_legacy(json.loads(self.path.read_text())["records"]["rec-json-2"]["payload"]))

    def test_second_run_migrates_nothing(self):
        VaultService(self.path).migrate_encryption(_PASSPHRASE)
        again = VaultService(self.path).migrate_encryption(_PASSPHRASE)
        self.assertEqual(again["records_migrated"], 0)
        self.assertIsNone(again["recovery_code"])


class LegacyKeyringVaultMigrationTests(unittest.TestCase):
    def test_reading_a_v1_vault_keeps_it_readable_by_the_previous_release(self):
        # Declining the migration must leave nothing an older release can't
        # read: unlock and read, then compare everything but attempt state.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vault.json"
            _write_legacy_vault(path, copy.deepcopy(LEGACY_KEYRING_STATE), LEGACY_MASTER_KEY)
            before = json.loads(path.read_text())
            service = VaultService(path)
            service.unlock(LEGACY_PASSPHRASE)
            self.assertEqual(service.get("rec-json-1"), {"secret": "hunter2"})
            after = json.loads(path.read_text())
            after.pop("unlock_attempts", None)
            before.pop("unlock_attempts", None)
            self.assertEqual(after, before)
            self.assertTrue(needs_encryption_migration(path))

    def test_v1_keyring_vault_migrates_with_a_new_recovery_code(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(keyring_module, "MEMORY_BLOCKS", 64):
            path = Path(tmp) / "vault.json"
            _write_legacy_vault(path, copy.deepcopy(LEGACY_KEYRING_STATE), LEGACY_MASTER_KEY)
            result = VaultService(path).migrate_encryption(LEGACY_PASSPHRASE)
            self.assertEqual(result["records_migrated"], 3)
            self.assertIsNotNone(result["recovery_code"])
            self.assertFalse(needs_encryption_migration(path))
            service = VaultService(path)
            self.assertEqual(service.unlock_with_recovery_code(result["recovery_code"]), LEGACY_MASTER_KEY)
            self.assertEqual(service.get("rec-json-1"), {"secret": "hunter2"})
            with self.assertRaises(VaultServiceError):
                VaultService(path).unlock_with_recovery_code(LEGACY_RECOVERY_CODE)


if __name__ == "__main__":
    unittest.main()
