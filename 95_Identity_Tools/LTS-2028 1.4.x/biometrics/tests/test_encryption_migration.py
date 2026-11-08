"""
File: biometrics/tests/test_encryption_migration.py

Purpose
-------
Tests for biometrics.identity.encryption_migration and the throttled
keyring_access.migrate_with_passphrase(): a biometrics data directory in the
previous encryption still reads (backward compatibility), and migrate()
re-encrypts templates and attachments, re-binds this machine's device binding,
and migrates the keyring file.

Verifies: biometrics/identity/encryption_migration.py,
biometrics/identity/keyring_access.py.
Contains 5 test case(s) across 1 TestCase class(es).

Design notes:

Records are assembled with biometrics.identity.identity_record and the legacy
writers in crypto/tests/legacy_fixtures.py, under the same contexts enrollment
and attachments use. The keyring is a current one whose check value is legacy
(no legacy KDF run) and crypto.keyring.MEMORY_BLOCKS is patched to 64, so the
module runs in the fast suite. The keyring file carries an attempt-limiting
field beside the keyring, as the real one does.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.engine.attachments (biometrics/engine/attachments.py)
- biometrics.identity.device_key (biometrics/identity/device_key.py)
- biometrics.identity.encryption_migration
  (biometrics/identity/encryption_migration.py)
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- biometrics.identity.identity_store (biometrics/identity/identity_store.py)
- biometrics.identity.keyring_access (biometrics/identity/keyring_access.py)
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.factors (crypto/factors.py)
- crypto.keyring (crypto/keyring.py)
- crypto.tests.legacy_fixtures (crypto/tests/legacy_fixtures.py)
Standard library: json, pathlib, tempfile, unittest, unittest.mock.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _PASSPHRASE = "biometrics passphrase"

Edge cases
----------
EncryptionMigrationTests:
- A legacy data directory reports needs_migration, and its legacy template and
  attachment still open with the previous encryption.
- migrate() re-encrypts every template and attachment with content unchanged,
  re-binds this machine's device binding, migrates the keyring check value,
  keeps the keyring file's attempt state, and leaves nothing needing
  migration.
- A device binding recorded on another machine is kept and reported, and does
  not on its own make needs_migration() true.
- A wrong passphrase raises KeyringAccessError and changes no identity record
  and no keyring field except the recorded attempt.
- A second run migrates nothing.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest biometrics.tests.test_encryption_migration -v
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biometrics.engine.attachments import extract_attachment_bytes
from biometrics.identity import device_key, encryption_migration
from biometrics.identity.identity_record import new_record, set_attachment, set_template
from biometrics.identity.identity_store import IdentityStore
from biometrics.identity.keyring_access import KeyringAccessError
from crypto import keyring as keyring_module
from crypto.context import attachment_context, template_context
from crypto.envelope import is_legacy, open_json
from crypto.factors import is_legacy_binding
from crypto.keyring import Keyring
from crypto.tests.legacy_fixtures import (
    legacy_bind_factor,
    legacy_keyring_state,
    seal_legacy_bytes,
    seal_legacy_json,
)

_PASSPHRASE = "biometrics passphrase"


def _legacy_record(identity_id, master_key, fingerprint):
    binding = legacy_bind_factor(master_key, device_key.DEVICE_FACTOR_NAME, fingerprint)
    record = new_record(identity_id, identity_id.title(), binding)
    record = set_template(record, "fingerprint", seal_legacy_json(
        master_key, {"vector": [1, 2, 3]}, template_context(identity_id, "fingerprint"),
    ))
    return set_attachment(record, "notes.txt", seal_legacy_bytes(
        master_key, b"attached notes", attachment_context(identity_id, "notes.txt"),
    ), 14, "0" * 64)


class EncryptionMigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        state, self.master_key = legacy_keyring_state(_PASSPHRASE)
        state["unlock_attempts"] = {"marker": "kept"}
        self.keyring_path = root / "keyring.json"
        self.keyring_path.write_text(json.dumps(state))
        self.store = IdentityStore(root / "identities")
        self.store.save(_legacy_record("alice", self.master_key, device_key.current_device_fingerprint()))
        self.store.save(_legacy_record("bob", self.master_key, "another-machine"))
        patcher = mock.patch.object(keyring_module, "MEMORY_BLOCKS", 64)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _keyring(self):
        return Keyring(json.loads(self.keyring_path.read_text()))

    def test_legacy_data_still_reads(self):
        self.assertTrue(encryption_migration.needs_migration(self._keyring(), self.store))
        alice = self.store.load("alice")
        self.assertEqual(extract_attachment_bytes(alice, "notes.txt", self.master_key), b"attached notes")
        self.assertEqual(
            open_json(self.master_key, alice["templates"]["fingerprint"], template_context("alice", "fingerprint")),
            {"vector": [1, 2, 3]},
        )

    def test_migration_reencrypts_and_rebinds(self):
        report = encryption_migration.migrate(self._keyring(), self.keyring_path, self.store, _PASSPHRASE)
        self.assertEqual(report["payloads_migrated"], 4)
        self.assertEqual(sorted(report["identities_migrated"]), ["alice", "bob"])
        self.assertIsNone(report["recovery_code"])
        alice = self.store.load("alice")
        self.assertFalse(is_legacy(alice["templates"]["fingerprint"]))
        self.assertFalse(is_legacy(alice["attachments"]["notes.txt"]["payload"]))
        self.assertEqual(extract_attachment_bytes(alice, "notes.txt", self.master_key), b"attached notes")
        self.assertFalse(is_legacy_binding(alice["device_binding"]))
        self.assertTrue(device_key.verify_device(self.master_key, alice["device_binding"]))
        keyring_state = json.loads(self.keyring_path.read_text())
        self.assertEqual(keyring_state["master_key_check"]["mac"], "mac64")
        self.assertIn("unlock_attempts", keyring_state)
        self.assertFalse(encryption_migration.needs_migration(self._keyring(), self.store))

    def test_other_device_binding_is_kept_and_reported(self):
        report = encryption_migration.migrate(self._keyring(), self.keyring_path, self.store, _PASSPHRASE)
        self.assertEqual(report["not_migrated"], ["bob: device binding (recorded on another device)"])
        self.assertTrue(is_legacy_binding(self.store.load("bob")["device_binding"]))
        self.assertFalse(encryption_migration.needs_migration(self._keyring(), self.store))

    def test_wrong_passphrase_changes_nothing(self):
        before_records = [json.dumps(r, sort_keys=True) for r in self.store.list_records()]
        before_keyring = json.loads(self.keyring_path.read_text())
        with self.assertRaises(KeyringAccessError):
            encryption_migration.migrate(self._keyring(), self.keyring_path, self.store, "wrong")
        self.assertEqual([json.dumps(r, sort_keys=True) for r in self.store.list_records()], before_records)
        after_keyring = json.loads(self.keyring_path.read_text())
        before_keyring.pop("unlock_attempts")
        after_keyring.pop("unlock_attempts")
        self.assertEqual(after_keyring, before_keyring)

    def test_second_run_migrates_nothing(self):
        encryption_migration.migrate(self._keyring(), self.keyring_path, self.store, _PASSPHRASE)
        again = encryption_migration.migrate(self._keyring(), self.keyring_path, self.store, _PASSPHRASE)
        self.assertEqual(again["payloads_migrated"], 0)
        self.assertEqual(again["identities_migrated"], [])


if __name__ == "__main__":
    unittest.main()
