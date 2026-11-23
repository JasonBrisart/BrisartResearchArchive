"""
File: packages/tests/test_package_migration.py

Purpose
-------
Tests for the package side of the encryption migration and the typed-text
master keys it depends on: a package in the previous encryption (SHA-256 text
keys, legacy slots, verifiers, and payload) still opens, and
package.migrate_recipient() moves one recipient at a time to the current
encryption without locking out recipients not yet migrated.

Verifies: packages/package.py (recipient_key_from_text,
needs_encryption_migration, migrate_recipient), packages/ciphers.py
(text_master_key, legacy_text_master_key, new_content_key).
Contains 7 test case(s) across 2 TestCase class(es).

Design notes:

The legacy package is assembled the way the pre-migration code built one: the
legacy text key is SHA-256 of the typed text, key slots and the payload are
legacy envelopes from crypto/tests/legacy_fixtures.py, and verifiers are legacy
keyed_mac bindings over the same factor name and marker
packages/verification.py uses. Every operation is a single MAC or seal, so the
module runs in the fast suite.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.factors (crypto/factors.py)
- crypto.tests.legacy_fixtures (crypto/tests/legacy_fixtures.py)
- packages.ciphers (packages/ciphers.py)
- packages.custody (packages/custody.py)
- packages.identity (packages/identity.py)
- packages.package (packages/package.py)
Standard library: hashlib, json, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _ALICE, _BOB -- the two recipients' typed texts.

Edge cases
----------
TextKeyTests:
- text_master_key() is deterministic, 32 bytes, differs per text, and differs
  from the legacy SHA-256 derivation; content keys are 32 bytes and distinct.
- A package created with current text keys needs no migration.
PackageMigrationTests:
- A legacy package opens for each recipient from typed text and reports
  needs_encryption_migration.
- Migrating one recipient reseals the payload and that recipient's slot and
  verifier, records a payload_rewrapped custody entry, and leaves the other
  recipient opening through the legacy slot.
- Migrating both recipients leaves nothing legacy and the payload unchanged.
- Wrong text raises PackageAuthorizationError and changes nothing.
- An identity that is not a recipient does not report a migration.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest packages.tests.test_package_migration -v
"""

import hashlib
import json
import unittest

from crypto.context import key_slot_context, package_context
from crypto.envelope import is_legacy
from crypto.factors import is_legacy_binding
from crypto.tests.legacy_fixtures import legacy_bind_factor, seal_legacy_bytes, seal_legacy_json
from packages import ciphers, custody, package
from packages.identity import new_recipient
from packages.package import PackageAuthorizationError

_ALICE = "alice's typed key text"
_BOB = "bob's typed key text"
_PAYLOAD = {"message": "sealed before the encryption migration"}


def _legacy_package(package_id="legacy-pkg"):
    content_key = ciphers.new_content_key()
    state = {
        "format": package.PACKAGE_FORMAT,
        "package_id": package_id,
        "recipients": {},
        "key_slots": {},
        "payload": seal_legacy_json(content_key, _PAYLOAD, package_context(package_id)),
        "custody_chain": custody.new_chain("Alice", package_id),
    }
    for identity_id, text in (("alice", _ALICE), ("bob", _BOB)):
        key = hashlib.sha256(text.encode("utf-8")).digest()
        state["recipients"][identity_id] = {
            **new_recipient(identity_id, identity_id.title()),
            "verifier": legacy_bind_factor(
                key, f"package-recipient:{identity_id}", "recipient-master-key-bound"
            ),
        }
        state["key_slots"][identity_id] = seal_legacy_bytes(
            key, content_key, key_slot_context(package_id, identity_id)
        )
    return state


def _open(state, identity_id, text):
    key = package.recipient_key_from_text(state, identity_id, text)
    payload, _ = package.open_package(state, identity_id, key)
    return payload


class TextKeyTests(unittest.TestCase):
    def test_text_keys(self):
        key = ciphers.text_master_key(_ALICE)
        self.assertEqual(key, ciphers.text_master_key(_ALICE))
        self.assertEqual(len(key), 32)
        self.assertNotEqual(key, ciphers.text_master_key(_BOB))
        self.assertNotEqual(key, ciphers.legacy_text_master_key(_ALICE))
        self.assertEqual(ciphers.legacy_text_master_key(_ALICE), hashlib.sha256(_ALICE.encode()).digest())
        self.assertEqual(len(ciphers.new_content_key()), 32)
        self.assertNotEqual(ciphers.new_content_key(), ciphers.new_content_key())

    def test_current_package_needs_no_migration(self):
        state = package.create_package(
            "new-pkg", "Alice", _PAYLOAD, {"alice": ("Alice", ciphers.text_master_key(_ALICE))}
        )
        self.assertFalse(package.needs_encryption_migration(state, "alice", _ALICE))
        self.assertEqual(_open(state, "alice", _ALICE), _PAYLOAD)


class PackageMigrationTests(unittest.TestCase):
    def setUp(self):
        self.state = _legacy_package()

    def test_legacy_package_still_opens(self):
        self.assertEqual(_open(self.state, "alice", _ALICE), _PAYLOAD)
        self.assertEqual(_open(self.state, "bob", _BOB), _PAYLOAD)
        self.assertTrue(package.needs_encryption_migration(self.state, "alice", _ALICE))

    def test_migrating_one_recipient_keeps_the_other_working(self):
        migrated = package.migrate_recipient(self.state, "alice", _ALICE)
        self.assertFalse(is_legacy(migrated["payload"]))
        self.assertFalse(is_legacy(migrated["key_slots"]["alice"]))
        self.assertFalse(is_legacy_binding(migrated["recipients"]["alice"]["verifier"]))
        self.assertTrue(is_legacy(migrated["key_slots"]["bob"]))
        self.assertEqual(migrated["custody_chain"][-1]["action"], "payload_rewrapped")
        self.assertEqual(migrated["custody_chain"][-1]["details"]["reason"], "encryption_migration")
        package.validate_package(migrated)
        self.assertEqual(
            package.recipient_key_from_text(migrated, "alice", _ALICE), ciphers.text_master_key(_ALICE)
        )
        self.assertFalse(package.needs_encryption_migration(migrated, "alice", _ALICE))
        self.assertTrue(package.needs_encryption_migration(migrated, "bob", _BOB))
        self.assertEqual(_open(migrated, "alice", _ALICE), _PAYLOAD)
        self.assertEqual(_open(migrated, "bob", _BOB), _PAYLOAD)

    def test_migrating_every_recipient_leaves_nothing_legacy(self):
        state = package.migrate_recipient(self.state, "alice", _ALICE)
        state = package.migrate_recipient(state, "bob", _BOB)
        self.assertFalse(any(is_legacy(slot) for slot in state["key_slots"].values()))
        self.assertFalse(package.needs_encryption_migration(state, "bob", _BOB))
        self.assertEqual(_open(state, "bob", _BOB), _PAYLOAD)

    def test_wrong_text_changes_nothing(self):
        before = json.dumps(self.state, sort_keys=True)
        with self.assertRaises(PackageAuthorizationError):
            package.migrate_recipient(self.state, "alice", "not alice's text")
        self.assertEqual(json.dumps(self.state, sort_keys=True), before)

    def test_non_recipient_reports_no_migration(self):
        self.assertFalse(package.needs_encryption_migration(self.state, "carol", "anything"))


if __name__ == "__main__":
    unittest.main()
