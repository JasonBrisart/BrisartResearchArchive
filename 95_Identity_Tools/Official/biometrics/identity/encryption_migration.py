"""
File: biometrics/identity/encryption_migration.py

Purpose
-------
Moves a biometrics data directory -- its keyring file and every identity record
in its store -- from the previous encryption to the current Brisart Encryption
formats. The CLI (``biometrics migrate``) and the GUI's migration prompt both
call this module.

Public interface:
- needs_migration(keyring, store) -- Report, without unlocking, whether the
  keyring or any sealed template or attachment still uses the previous
  encryption.
- migrate(keyring, keyring_path, store, passphrase) -- Unlock through
  keyring_access.migrate_with_passphrase(), then re-encrypt every legacy
  template and attachment and re-bind a legacy device binding. Returns a
  report dict (see Settings / parameters).

Design notes:

Order matters for resumability. The keyring is migrated and written first; the
master key it protects never changes, so every identity record stays openable
whatever happens next. Each identity record is then rewritten on its own, with
one atomic write per file, and only if something in it changed. An interrupted
migration therefore leaves a mix of migrated and legacy records, all readable,
and running migrate() again finishes the rest.

What is re-encrypted, and under which context:
- templates[modality] -- crypto.context.template_context(identity_id, modality)
- attachments[filename]["payload"] --
  crypto.context.attachment_context(identity_id, filename). Bulk attachment
  manifests and chunks are ordinary attachments, so they are covered.
- device_binding -- a keyed binding of this machine's fingerprint, not a sealed
  payload. A legacy binding can only be re-bound by someone who can reproduce
  the fingerprint, so it is re-bound when it verifies against the current
  machine and left as it is otherwise. Because a binding from another machine
  can never be migrated here, legacy device bindings do not count towards
  needs_migration(); otherwise the migration prompt would come back on every
  unlock. They are migrated whenever migrate() runs on the machine that
  recorded them, and reported when it runs anywhere else.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.identity.device_key (biometrics/identity/device_key.py)
- biometrics.identity.identity_store (biometrics/identity/identity_store.py)
- biometrics.identity.keyring_access (biometrics/identity/keyring_access.py)
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.factors (crypto/factors.py)
- crypto.rng (crypto/rng.py)
Standard library: pathlib.
Imported by:
- biometrics/app.py
- gui/tabs/tab_biometrics.py
Covered by tests: biometrics/tests/test_encryption_migration.py.

Settings / parameters
---------------------
migrate() returns:
- recovery_code -- the newly issued recovery code, or None when the keyring's
  recovery wrapper was already current. Show it once; it replaces the old one.
- identities_migrated -- identity ids whose record file was rewritten.
- payloads_migrated -- templates and attachments re-encrypted.
- not_migrated -- "<identity_id>: <item>" strings for items left in the
  previous encryption: a payload that failed to authenticate, or a device
  binding recorded on a different machine.

Edge cases
----------
- A wrong or throttled passphrase raises KeyringAccessError from
  keyring_access and changes nothing but the recorded attempt.
- An identity record the store cannot load is skipped by list_records(), so it
  is neither migrated nor reported; needs_migration() skips it the same way.
- EncryptionNotFoundError propagates when Brisart Encryption is not linked.

Known limitations
-----------------
- Records are rewritten in place; no copy of the previous files is kept.
  Migrated records cannot be opened by Official 1.9.2, LTS-2028 1.3.10, or
  earlier.
- A device binding recorded on another machine stays legacy until migrate()
  runs on that machine, so the legacy verifier cannot be removed while such
  bindings exist.

Examples
--------
Call shapes only: keyring, keyring_path, store, and passphrase stand for values
the caller supplies.

::

    from biometrics.identity import encryption_migration
    if encryption_migration.needs_migration(keyring, store):
        report = encryption_migration.migrate(keyring, keyring_path, store, passphrase)
"""

from pathlib import Path

from biometrics.identity import device_key, keyring_access
from biometrics.identity.identity_store import IdentityStore
from crypto.context import attachment_context, template_context
from crypto.envelope import is_legacy, reseal
from crypto.errors import Bsr2IntegrationError
from crypto.factors import is_legacy_binding
from crypto.rng import new_generator


def _has_legacy_payload(record: dict) -> bool:
    return any(is_legacy(envelope) for envelope in record.get("templates", {}).values()) or any(
        is_legacy(entry.get("payload")) for entry in record.get("attachments", {}).values()
    )


def needs_migration(keyring, store: IdentityStore) -> bool:
    """Report whether the keyring or any identity record is still legacy."""
    return keyring.needs_migration or any(
        _has_legacy_payload(record) for record in store.list_records()
    )


def _migrate_record(record: dict, master_key: bytes, rng, report: dict) -> bool:
    """Re-encrypt the legacy parts of one record in place; return whether
    anything changed."""
    identity_id = record["identity_id"]
    changed = False
    sealed_items = [
        (record["templates"], modality, template_context(identity_id, modality), f"template {modality}")
        for modality in record.get("templates", {})
    ] + [
        (entry, "payload", attachment_context(identity_id, filename), f"attachment {filename}")
        for filename, entry in record.get("attachments", {}).items()
    ]
    for holder, key, context, description in sealed_items:
        if not is_legacy(holder[key]):
            continue
        try:
            holder[key] = reseal(master_key, holder[key], context, rng)
        except Bsr2IntegrationError:
            report["not_migrated"].append(f"{identity_id}: {description}")
            continue
        report["payloads_migrated"] += 1
        changed = True
    if is_legacy_binding(record.get("device_binding")):
        if device_key.verify_device(master_key, record["device_binding"]):
            record["device_binding"] = device_key.bind_device(master_key)
            changed = True
        else:
            report["not_migrated"].append(f"{identity_id}: device binding (recorded on another device)")
    return changed


def migrate(keyring, keyring_path: Path, store: IdentityStore, passphrase: str) -> dict:
    """Migrate the keyring, then every identity record, to the current
    encryption. See Settings / parameters for the returned report."""
    recovery_code = keyring_access.migrate_with_passphrase(keyring, Path(keyring_path), passphrase)
    master_key = keyring.master_key
    rng = new_generator("biometrics-migrate")
    report = {
        "recovery_code": recovery_code,
        "identities_migrated": [],
        "payloads_migrated": 0,
        "not_migrated": [],
    }
    for record in store.list_records():
        needs = _has_legacy_payload(record) or is_legacy_binding(record.get("device_binding"))
        if needs and _migrate_record(record, master_key, rng, report):
            store.save(record)
            report["identities_migrated"].append(record["identity_id"])
    return report


__all__ = ["migrate", "needs_migration"]
