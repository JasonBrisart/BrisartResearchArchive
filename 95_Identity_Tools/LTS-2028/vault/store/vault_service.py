"""
File: vault/store/vault_service.py

Purpose
-------
Vault orchestration: unlock/lock, and sealed create/read/update/delete.

Public interface:
- class VaultServiceError(ValueError)
- class VaultService. Public methods: create, unlock,
  unlock_with_recovery_code, lock, is_unlocked, upsert, batch_upsert,
  upsert_file_bytes, upsert_file, get_file_bytes, get_file, delete, get,
  get_summary, list_records, find_by_label, change_passphrase,
  rotate_recovery_code.

Design notes:

This is the vault's application layer -- the single place that ties together
the vault's keyring, its record model, its on-disk file, and its audit log into
the operations the CLI (vault.app) and GUI (gui.tabs.tab_vault) actually call.
It owns no file format details of its own: reading and writing the vault file
is vault.store.vault_file's job, record shape/validation is
vault.records.record_model's job, and the master-key wrapping is
crypto.keyring's job.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.hashing (common/hashing.py)
- crypto.attempt_store (crypto/attempt_store.py)
- crypto.context (crypto/context.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.rng (crypto/rng.py)
- crypto.throttle (crypto/throttle.py)
- vault.core.ids (vault/core/ids.py)
- vault.core.time_tools (vault/core/time_tools.py)
- vault.records.record_model (vault/records/record_model.py)
- vault.reports.audit_log (vault/reports/audit_log.py)
- vault.store.vault_file (vault/store/vault_file.py)
- crypto.keyring (crypto/keyring.py)
Standard library: pathlib.
Imported by:
- gui/tabs/tab_vault.py
- vault/app.py
Covered by tests: gui/tests/test_tab_vault.py,
vault/tests/test_batch_upsert.py, vault/tests/test_bulk_file_service.py,
vault/tests/test_file_records.py, vault/tests/test_label_normalization.py,
vault/tests/test_public_summary_file_metadata.py,
vault/tests/test_sealed_vault.py, vault/tests/test_unlock_throttle.py.

Settings / parameters
---------------------
- FILE_RECORD_KIND = "file"

Edge cases
----------
- VaultService.unlock() raises VaultServiceError: "unlock refused: too many
  recent failed attempts; retry in {...} second(s)."
- VaultService.unlock() raises VaultServiceError: "unlock failed: {...}"
- VaultService.unlock_with_recovery_code() raises VaultServiceError: "unlock
  refused: too many recent failed attempts; retry in {...} second(s)."
- VaultService.unlock_with_recovery_code() raises VaultServiceError: "unlock
  failed: {...}"
- VaultService._require_unlocked() raises VaultServiceError: "vault is locked;
  unlock it before this operation."
- VaultService.batch_upsert() raises VaultServiceError: "each batch item must
  contain 'label', 'kind', and 'payload'."
- VaultService.upsert_file_bytes() raises VaultServiceError: "file_bytes must
  be bytes."
- VaultService.upsert_file() raises VaultServiceError: "no file found at
  {...}."
- VaultService.get_file_bytes() raises VaultServiceError: "no record found for
  {...}."
- VaultService.get_file_bytes() raises VaultServiceError: "record {...} failed
  to authenticate: {...}"
- VaultService.get() raises VaultServiceError: "no record found for {...}."
- VaultService.get() raises VaultServiceError: "record {...} failed to
  authenticate: {...}"
- VaultService.get_summary() raises VaultServiceError: "no record found for
  {...}."
- VaultService.change_passphrase() raises VaultServiceError: "unlock the vault
  before changing its passphrase."
- VaultService.rotate_recovery_code() raises VaultServiceError: "unlock the
  vault before rotating its recovery code."
- VaultService.get(), VaultService.get_file_bytes(), VaultService.unlock(),
  VaultService.unlock_with_recovery_code(): translates Bsr2IntegrationError
  into VaultServiceError, so callers only need to handle this module's own
  error type.
- VaultService.unlock(), VaultService.unlock_with_recovery_code(): translates
  AttemptLockedOut into VaultServiceError, so callers only need to handle this
  module's own error type.

Known limitations
-----------------
- This module only sequences them, holds the unlocked master key for the
  session, and records an audit event for every mutation.
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
::

    from vault.store.vault_service import VaultService
    obj = VaultService(path)
    obj.create(path, passphrase)
"""

from pathlib import Path

from common.hashing import sha256_bytes
from crypto import attempt_store
from crypto.context import record_context
from crypto.envelope import open_bytes, open_json, seal_bytes, seal_json
from crypto.errors import Bsr2IntegrationError
from crypto.rng import new_generator
from crypto.throttle import AttemptLockedOut
from vault.core.ids import new_record_id, validate_record_id
from vault.core.time_tools import stamp_new_record, stamp_updated
from vault.records.record_model import (
    new_record, normalize_label, public_summary, replace_payload, validate_record,
)
from vault.reports import audit_log
from vault.store.vault_file import (
    create_vault_file, load_records, load_state, save_keyring, save_records, save_state,
)

# The vault record "kind" reserved for arbitrary raw-file payloads created by
# upsert_file(). Nothing about this kind is special-cased in
# vault.records.record_model or vault.store.vault_file -- a file record is a
# completely ordinary vault record whose payload happens to have been sealed
# with crypto.envelope.seal_bytes (raw bytes) instead of seal_json (a JSON
# object). Both produce the exact same BSR2 envelope shape, so
# record_model.validate_record's is_envelope() check accepts either without
# modification.
FILE_RECORD_KIND = "file"


class VaultServiceError(ValueError):
    pass


class VaultService:
    def __init__(self, path, audit_dir=None):
        self.path = Path(path)
        self.audit_dir = Path(audit_dir) if audit_dir is not None else None
        self._keyring = None
        self._master_key = None

    @classmethod
    def create(cls, path, passphrase: str, audit_dir=None):
        keyring, recovery_code = create_vault_file(path, passphrase)
        service = cls(path, audit_dir)
        service._keyring = keyring
        service._master_key = keyring.master_key
        service._audit("unlocked")
        return service, recovery_code

    def _audit(self, action, record_id="", label="", kind=""):
        if self.audit_dir is not None:
            audit_log.record_event(self.audit_dir, action, record_id, label, kind)

    def unlock(self, passphrase: str) -> bytes:
        state = load_state(self.path)
        try:
            attempt_store.check_and_get_state(state)
        except AttemptLockedOut as exc:
            raise VaultServiceError(
                "unlock refused: too many recent failed attempts; retry in "
                f"{exc.retry_after_seconds:.0f} second(s)."
            ) from exc
        from crypto.keyring import Keyring
        keyring = Keyring(state["keyring"])
        try:
            master_key = keyring.unlock_with_passphrase(passphrase)
        except Bsr2IntegrationError as exc:
            state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(state)
            save_state(self.path, state)
            raise VaultServiceError(f"unlock failed: {exc}") from exc
        state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_success(state)
        save_state(self.path, state)
        self._keyring = keyring
        self._master_key = master_key
        self._audit("unlocked")
        return master_key

    def unlock_with_recovery_code(self, recovery_code: str) -> bytes:
        state = load_state(self.path)
        try:
            attempt_store.check_and_get_state(state)
        except AttemptLockedOut as exc:
            raise VaultServiceError(
                "unlock refused: too many recent failed attempts; retry in "
                f"{exc.retry_after_seconds:.0f} second(s)."
            ) from exc
        from crypto.keyring import Keyring
        keyring = Keyring(state["keyring"])
        try:
            master_key = keyring.unlock_with_recovery_code(recovery_code)
        except Bsr2IntegrationError as exc:
            state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_failure(state)
            save_state(self.path, state)
            raise VaultServiceError(f"unlock failed: {exc}") from exc
        state[attempt_store.ATTEMPT_STATE_FIELD] = attempt_store.record_success(state)
        save_state(self.path, state)
        self._keyring = keyring
        self._master_key = master_key
        self._audit("unlocked")
        return master_key

    def lock(self) -> None:
        if self._keyring is not None:
            self._keyring.lock()
        self._master_key = None
        self._audit("locked")

    @property
    def is_unlocked(self) -> bool:
        return self._master_key is not None

    def _require_unlocked(self) -> bytes:
        if self._master_key is None:
            raise VaultServiceError("vault is locked; unlock it before this operation.")
        return self._master_key

    def upsert(self, label: str, kind: str, payload: dict, record_id: str = None) -> dict:
        master_key = self._require_unlocked()
        normalized_label = normalize_label(label)
        records = load_records(self.path)
        if record_id is None:
            record_id = new_record_id()
            while record_id in records:
                record_id = new_record_id()
        else:
            validate_record_id(record_id)
        context = record_context(record_id, kind, normalized_label)
        rng = new_generator("vault-upsert")
        envelope = seal_json(master_key, payload, context, rng)
        existing = records.get(record_id)
        if existing is not None:
            existing = validate_record(existing)
            record = replace_payload(existing, envelope, stamp_updated(existing["created_at"]))
            action = "updated"
        else:
            record = new_record(record_id, normalized_label, kind, envelope, stamp_new_record())
            action = "created"
        records[record_id] = record
        save_records(self.path, records)
        self._audit(action, record_id, normalized_label, kind)
        return public_summary(record)

    def batch_upsert(self, items: list) -> list:
        master_key = self._require_unlocked()
        records = load_records(self.path)
        summaries = []
        events = []
        for item in items:
            if "label" not in item or "kind" not in item or "payload" not in item:
                raise VaultServiceError("each batch item must contain 'label', 'kind', and 'payload'.")
            normalized_label = normalize_label(item["label"])
            record_id = item.get("record_id")
            if record_id is None:
                record_id = new_record_id()
                while record_id in records:
                    record_id = new_record_id()
            else:
                validate_record_id(record_id)
            context = record_context(record_id, item["kind"], normalized_label)
            rng = new_generator("vault-batch-upsert")
            envelope = seal_json(master_key, item["payload"], context, rng)
            existing = records.get(record_id)
            if existing is not None:
                existing = validate_record(existing)
                record = replace_payload(existing, envelope, stamp_updated(existing["created_at"]))
                action = "updated"
            else:
                record = new_record(record_id, normalized_label, item["kind"], envelope, stamp_new_record())
                action = "created"
            records[record_id] = record
            summaries.append(public_summary(record))
            events.append((action, record_id, normalized_label, item["kind"]))
        save_records(self.path, records)
        for action, record_id, normalized_label, kind in events:
            self._audit(action, record_id, normalized_label, kind)
        return summaries

    def upsert_file_bytes(self, label: str, file_bytes: bytes, original_filename: str = "",
                          record_id: str = None, kind: str = FILE_RECORD_KIND) -> dict:
        """Seal arbitrary raw bytes as a vault record, with NO assumption
        about what the bytes are: any extension, no extension, binary
        content that isn't valid text/JSON at all -- an executable, an
        archive, an image, a database file, anything. This is what makes
        this genuinely "any file, no matter what it is" rather than the
        JSON-object-only path `upsert()` provides: the content is sealed
        with crypto.envelope.seal_bytes (raw bytes in, raw bytes out) rather
        than seal_json, so nothing about the payload is ever parsed,
        decoded, or interpreted as JSON at any point in this round trip.

        `kind` defaults to FILE_RECORD_KIND ("file") for a genuinely
        standalone file, but callers that are storing an internal PIECE of
        a larger construct -- e.g. BulkFileService's chunked bundle
        chunks -- should pass a distinct kind (BUNDLE_CHUNK_KIND) so those
        internal records can be told apart from a real standalone
        single-file record later.

        `original_filename` is stored in the clear as a normal, non-secret
        field on the record (vault record shells -- label, kind, timestamps
        -- are already readable by design; see vault/README.md's "What is
        readable while locked" section). A SHA-256 of the ORIGINAL
        plaintext bytes is also stored in the clear, purely so a caller can
        verify integrity after a future decrypt without needing to unlock
        the vault just to check "does this look like the same file" --
        this is an integrity fingerprint only, not a secret, exactly the
        same non-secret role common.hashing.sha256_bytes already plays
        everywhere else in this codebase.
        """
        if not isinstance(file_bytes, (bytes, bytearray)):
            raise VaultServiceError("file_bytes must be bytes.")
        master_key = self._require_unlocked()
        normalized_label = normalize_label(label)
        records = load_records(self.path)
        if record_id is None:
            record_id = new_record_id()
            while record_id in records:
                record_id = new_record_id()
        else:
            validate_record_id(record_id)
        context = record_context(record_id, kind, normalized_label)
        rng = new_generator("vault-upsert-file")
        envelope = seal_bytes(master_key, bytes(file_bytes), context, rng)
        existing = records.get(record_id)
        if existing is not None:
            existing = validate_record(existing)
            record = replace_payload(existing, envelope, stamp_updated(existing["created_at"]))
            action = "updated"
        else:
            record = new_record(record_id, normalized_label, kind, envelope, stamp_new_record())
            action = "created"
        record["original_filename"] = original_filename
        record["file_size_bytes"] = len(file_bytes)
        record["file_sha256"] = sha256_bytes(bytes(file_bytes))
        records[record_id] = record
        save_records(self.path, records)
        self._audit(action, record_id, normalized_label, kind)
        # public_summary() only returns the fields every vault record kind
        # shares (record_id/label/kind/timestamps); the file-specific
        # plaintext metadata is merged in here so a caller can immediately
        # see the original filename/size/hash without a second lookup.
        return {
            **public_summary(record),
            "original_filename": record["original_filename"],
            "file_size_bytes": record["file_size_bytes"],
            "file_sha256": record["file_sha256"],
        }

    def upsert_file(self, path, label: str = None, record_id: str = None, kind: str = FILE_RECORD_KIND) -> dict:
        """Convenience wrapper around upsert_file_bytes(): reads a real file
        from disk (any name, any extension, or no extension at all -- the
        file's own name is never inspected to decide how to handle it) and
        seals its exact raw bytes. `label` defaults to the file's own name
        if not supplied.
        """
        resolved = Path(path)
        if not resolved.is_file():
            raise VaultServiceError(f"no file found at {resolved}.")
        file_bytes = resolved.read_bytes()
        return self.upsert_file_bytes(
            label or resolved.name, file_bytes, original_filename=resolved.name, record_id=record_id, kind=kind,
        )

    def get_file_bytes(self, record_id: str) -> bytes:
        """Open a file record, returning the exact original bytes -- the
        precise inverse of upsert_file_bytes(). Uses open_bytes (never
        open_json), so the result is never parsed or decoded as anything;
        whatever bytes were sealed are exactly the bytes returned, byte for
        byte, regardless of what they actually represent.
        """
        master_key = self._require_unlocked()
        records = load_records(self.path)
        record = records.get(record_id)
        if record is None:
            raise VaultServiceError(f"no record found for {record_id!r}.")
        record = validate_record(record)
        context = record_context(record_id, record["kind"], record["label"])
        try:
            return open_bytes(master_key, record["payload"], context)
        except Bsr2IntegrationError as exc:
            raise VaultServiceError(f"record {record_id!r} failed to authenticate: {exc}") from exc

    def get_file(self, record_id: str, output_path) -> Path:
        """Decrypt a file record straight to disk at `output_path`. Returns
        the resolved output path. The exact original bytes are written --
        no assumption is made about what extension `output_path` should
        have; that is entirely up to the caller.
        """
        file_bytes = self.get_file_bytes(record_id)
        resolved_output = Path(output_path)
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        resolved_output.write_bytes(file_bytes)
        return resolved_output

    def delete(self, record_id: str) -> bool:
        records = load_records(self.path)
        record = records.pop(record_id, None)
        if record is None:
            return False
        save_records(self.path, records)
        self._audit("deleted", record_id, record.get("label", ""), record.get("kind", ""))
        return True

    def get(self, record_id: str) -> dict:
        master_key = self._require_unlocked()
        records = load_records(self.path)
        record = records.get(record_id)
        if record is None:
            raise VaultServiceError(f"no record found for {record_id!r}.")
        record = validate_record(record)
        context = record_context(record_id, record["kind"], record["label"])
        try:
            return open_json(master_key, record["payload"], context)
        except Bsr2IntegrationError as exc:
            raise VaultServiceError(f"record {record_id!r} failed to authenticate: {exc}") from exc

    def get_summary(self, record_id: str) -> dict:
        records = load_records(self.path)
        record = records.get(record_id)
        if record is None:
            raise VaultServiceError(f"no record found for {record_id!r}.")
        return public_summary(validate_record(record))

    def list_records(self) -> list:
        records = load_records(self.path)
        summaries = [public_summary(validate_record(record)) for record in records.values()]
        return sorted(summaries, key=lambda summary: (summary["label"], summary["record_id"]))

    def find_by_label(self, label: str) -> list:
        target = normalize_label(label)
        return [summary for summary in self.list_records() if summary["label"] == target]

    def change_passphrase(self, new_passphrase: str) -> None:
        if self._keyring is None:
            raise VaultServiceError("unlock the vault before changing its passphrase.")
        self._keyring.change_passphrase(new_passphrase)
        save_keyring(self.path, self._keyring)

    def rotate_recovery_code(self) -> str:
        if self._keyring is None:
            raise VaultServiceError("unlock the vault before rotating its recovery code.")
        new_code = self._keyring.rotate_recovery_code()
        save_keyring(self.path, self._keyring)
        return new_code




