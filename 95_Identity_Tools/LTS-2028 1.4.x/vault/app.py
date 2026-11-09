"""
File: vault/app.py

Purpose
-------
Vault command-line interface: init, upsert, batch-upsert, get, list, delete,
encrypt-file/decrypt-file for arbitrary binary files of any kind, extension,
or lack thereof, and encrypt-paths/restore-paths for bundles of files,
folders, or drives.

Public interface:
- class AppError(ValueError)
- command_init(args)
- command_migrate(args) -- Re-encrypt the vault with the current encryption
  after confirmation.
- command_upsert(args)
- command_batch_upsert(args)
- command_encrypt_file(args) -- Encrypt an arbitrary local file -- any
  extension, or no extension at all -- into the vault, sealing its exact raw
  bytes. The file's contents are never inspected, parsed, or assumed to be any
  particular format.
- command_decrypt_file(args) -- Decrypt a previously encrypted file record
  straight back to disk, byte-for-byte identical to what was originally
  encrypted.
- command_encrypt_paths(args) -- Encrypt any combination of files, folders,
  and/or drive roots -- all given as separate positional arguments -- as ONE
  bundle, stored as fixed-size sealed chunks plus a manifest and reassembled
  on restore.
- command_restore_paths(args) -- Decrypt and unzip a bundle created by
  encrypt-paths back into a real directory tree at the given output directory.
- command_get(args)
- command_list(args)
- command_delete(args)
- build_parser()
- main(argv=None)

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py) -- MIGRATION_NOTICE
- crypto.errors (crypto/errors.py)
- vault.config.settings (vault/config/settings.py)
- vault.store.vault_file (vault/store/vault_file.py)
- vault.store.vault_service (vault/store/vault_service.py)
- vault.store.bulk_file_service (vault/store/bulk_file_service.py)
Standard library: argparse, getpass, json, pathlib, sys.
Imported by:
- cli.py
Covered by tests: tests/test_cli_dispatcher.py.

Settings / parameters
---------------------
- MAX_CHUNK_MB = 15

Options shared by every command:
- --vault: path to the vault file; when omitted, the default from
  vault/config/settings.py (data/vault/vault.json) is used.

Commands (each takes the options listed under it):
- upsert -- create or update one JSON-payload record.
  - label: record label.
  - --kind: required; free-text record kind, for example credential or note.
  - --payload (required): JSON object string.
  - --record-id: optional; omit to have the vault generate an id, or give an
    existing id to replace that record's contents.
- batch-upsert -- create or update many JSON-payload records from a JSON file.
  - items_file (positional): path to a JSON array of items.
- encrypt-file -- encrypt any local file into the vault, any extension or none
  at all.
  - file_path (positional): path to the file to encrypt.
  - --label: defaults to the file's own name.
  - --record-id: optional; omit to have the vault generate an id, or give an
    existing id to replace that record's contents.
- decrypt-file -- decrypt a file record back to disk, byte-for-byte.
  - record_id: id of the record.
  - output_path (positional).
- encrypt-paths -- encrypt any combination of files/folders/drive roots as one
  bundle (stored as fixed-size sealed chunks).
  - paths (positional, one or more): one or more file, folder, or drive root
    paths.
  - --label: defaults to the first path's own name.
  - --record-id: optional; omit to have the vault generate an id, or give an
    existing id to replace that record's contents.
  - --chunk-mb (int): chunk size in MiB (default 8; must be 1..15).
- restore-paths -- decrypt and unzip a bundle back into a real directory tree.
  - record_id: id of the record.
  - output_dir (positional).
- get -- retrieve and decrypt one JSON record's payload.
  - record_id: id of the record.
- delete -- delete one record.
  - record_id: id of the record.
- init -- create a new vault.
  - no options of its own.
- migrate -- re-encrypt a vault still in the previous encryption with the
  current BSR2 formats, after showing
  crypto.encryption.MIGRATION_NOTICE and asking for confirmation.
  - --yes: skip the confirmation prompt.
- list -- list all records (no unlock required).
  - no options of its own.

Edge cases
----------
- main() returns 3 and prints "error: Encryption not found: ..." when a
  command needs encryption and BSR2 is not linked.
- _unlock() raises AppError. After a successful unlock it prints a one-line
  notice to stderr when the vault still needs encryption migration; the
  command itself carries on with the previous encryption.
- command_migrate() returns 1 without changing anything when the operator
  declines, and prints "vault already uses the current encryption." and
  returns 0 when there is nothing to migrate.
- command_init() raises AppError: "a vault already exists at {...}."
- command_init() raises AppError: "passphrases did not match."
- command_upsert() raises AppError: "--payload must be valid JSON: {...}"
- command_upsert() raises AppError: "--payload must be a JSON object."
- command_upsert() raises AppError.
- command_batch_upsert() raises AppError: "could not read --items-file: {...}"
- command_batch_upsert() raises AppError: "--items-file must contain a JSON
  array of items."
- command_batch_upsert() raises AppError.
- command_encrypt_file() raises AppError.
- command_decrypt_file() raises AppError.
- command_encrypt_paths() raises AppError: "--chunk-mb must be between 1 and
  {...}."
- command_encrypt_paths() raises AppError.
- command_restore_paths() raises AppError.
- command_get() raises AppError.
- Run as a script, the process exit status is main()'s return value (via
  ``raise SystemExit(main())``).
- _unlock(), command_decrypt_file(), command_get(): translates
  VaultServiceError into AppError; other exceptions may still propagate.
- command_batch_upsert(): translates (OSError, json.JSONDecodeError) into
  AppError; other exceptions may still propagate.
- command_batch_upsert(), command_encrypt_file(), command_upsert(): translates
  (VaultServiceError, VaultFileError) into AppError; other exceptions may still propagate.
- command_encrypt_paths(): translates (BulkFileServiceError, VaultServiceError,
  VaultFileError) into AppError; other exceptions may still propagate.
- command_restore_paths(): translates (BulkFileServiceError, VaultServiceError)
  into AppError; other exceptions may still propagate.
- command_upsert(): translates json.JSONDecodeError into AppError; other
  exceptions may still propagate.
- main(): catches AppError and handles it in place; it does not propagate to
  the caller.

Known limitations
-----------------
- No test runs this module's commands; tests/test_cli_dispatcher.py imports it
  only to check exit-status pass-through with main() replaced. Verify changes
  by running it manually.

Examples
--------
::

    python -m vault.app --help
    python -m vault.app init --help
    python -m vault.app upsert --help
    python -m vault.app batch-upsert --help
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

from crypto import encryption
from crypto.errors import EncryptionNotFoundError
from vault.config import settings
from vault.store.vault_file import VaultFileError, vault_exists
from vault.store.vault_service import VaultService, VaultServiceError, needs_encryption_migration
from vault.store.bulk_file_service import BulkFileService, BulkFileServiceError


# The largest --chunk-mb the bulk path will accept. Each chunk is sealed and
# written as one vault record held whole in memory; 15 MiB keeps every chunk a
# single v3 sealed message (limit 16 MiB) and bounds that per-record cost.
MAX_CHUNK_MB = 15


class AppError(ValueError):
    pass


def _vault_path(args) -> Path:
    return Path(args.vault) if args.vault else settings.VAULT_FILE


def _open_service(args) -> VaultService:
    settings.ensure_data_dirs()
    return VaultService(_vault_path(args), audit_dir=settings.AUDIT_DIR)


def _unlock(service: VaultService) -> None:
    passphrase = getpass.getpass("Vault passphrase: ")
    try:
        service.unlock(passphrase)
    except VaultServiceError as exc:
        raise AppError(str(exc)) from exc
    if needs_encryption_migration(service.path):
        print(
            "note: this vault still uses the previous encryption; run "
            "'vault migrate' to re-encrypt it.",
            file=sys.stderr,
        )


def command_migrate(args) -> int:
    path = _vault_path(args)
    if not vault_exists(path):
        raise AppError(f"no vault file found at {path}.")
    if not needs_encryption_migration(path):
        print("vault already uses the current encryption.")
        return 0
    print(encryption.MIGRATION_NOTICE, file=sys.stderr)
    print(
        "\nIf the vault's recovery code uses the previous encryption, a new one "
        "is issued and shown once; the old code will stop working.",
        file=sys.stderr,
    )
    if not args.yes and input("Migrate now? [y/N] ").strip().lower() not in ("y", "yes"):
        print("migration cancelled; nothing was changed.")
        return 1
    service = _open_service(args)
    passphrase = getpass.getpass("Vault passphrase: ")
    try:
        result = service.migrate_encryption(passphrase)
    except VaultServiceError as exc:
        raise AppError(str(exc)) from exc
    print(f"migrated {result['records_migrated']} record(s) to the current encryption.")
    for record_id in result["records_not_migrated"]:
        print(
            f"warning: record {record_id!r} failed to authenticate and was left "
            "in the previous encryption.",
            file=sys.stderr,
        )
    if result["recovery_code"] is not None:
        print(
            "\nSAVE THIS NEW RECOVERY CODE NOW. It replaces the old one, is shown "
            f"only once, and cannot be recovered later:\n\n    {result['recovery_code']}\n",
            file=sys.stderr,
        )
    return 0


def command_init(args) -> int:
    settings.ensure_data_dirs()
    path = _vault_path(args)
    if vault_exists(path):
        raise AppError(f"a vault already exists at {path}.")
    passphrase = getpass.getpass("Set a new vault passphrase: ")
    confirm = getpass.getpass("Confirm passphrase: ")
    if passphrase != confirm:
        raise AppError("passphrases did not match.")
    _service, recovery_code = VaultService.create(path, passphrase, audit_dir=settings.AUDIT_DIR)
    print(f"vault created at {path}")
    print(
        "\nSAVE THIS RECOVERY CODE NOW. It is shown only once and cannot be "
        f"recovered later:\n\n    {recovery_code}\n",
        file=sys.stderr,
    )
    return 0


def command_upsert(args) -> int:
    service = _open_service(args)
    _unlock(service)
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        raise AppError(f"--payload must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AppError("--payload must be a JSON object.")
    try:
        summary = service.upsert(args.label, args.kind, payload, record_id=args.record_id)
    except (VaultServiceError, VaultFileError) as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def command_batch_upsert(args) -> int:
    service = _open_service(args)
    _unlock(service)
    try:
        with open(args.items_file, "r", encoding="utf-8") as handle:
            items = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(f"could not read --items-file: {exc}") from exc
    if not isinstance(items, list):
        raise AppError("--items-file must contain a JSON array of items.")
    try:
        summaries = service.batch_upsert(items)
    except (VaultServiceError, VaultFileError) as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(summaries, indent=2, sort_keys=True))
    print(f"upserted {len(summaries)} record(s).", file=sys.stderr)
    return 0


def command_encrypt_file(args) -> int:
    """Encrypt an arbitrary local file -- any extension, or no extension at
    all -- into the vault, sealing its exact raw bytes. The file's contents
    are never inspected, parsed, or assumed to be any particular format."""
    service = _open_service(args)
    _unlock(service)
    try:
        summary = service.upsert_file(args.file_path, label=args.label, record_id=args.record_id)
    except (VaultServiceError, VaultFileError) as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def command_decrypt_file(args) -> int:
    """Decrypt a previously encrypted file record straight back to disk,
    byte-for-byte identical to what was originally encrypted."""
    service = _open_service(args)
    _unlock(service)
    try:
        output_path = service.get_file(args.record_id, args.output_path)
    except VaultServiceError as exc:
        raise AppError(str(exc)) from exc
    print(f"decrypted to {output_path}")
    return 0


def command_encrypt_paths(args) -> int:
    """Encrypt any combination of files, folders, and/or drive roots -- all
    given as separate positional arguments -- as ONE bundle. Any single
    file and the zip built from folders/drives are stored as fixed-size
    sealed chunks and reassembled on restore."""
    # Fix 1 (2026-09-09): reject an out-of-range --chunk-mb up front, before
    # any work is done (see MAX_CHUNK_MB).
    if args.chunk_mb < 1 or args.chunk_mb > MAX_CHUNK_MB:
        raise AppError(
            f"--chunk-mb must be between 1 and {MAX_CHUNK_MB}."
        )
    service = _open_service(args)
    _unlock(service)
    bulk = BulkFileService(service, chunk_bytes=args.chunk_mb * 1024 * 1024)
    label = args.label or Path(args.paths[0]).name
    try:
        summary = bulk.upsert_paths(args.paths, label, record_id=args.record_id)
    except (BulkFileServiceError, VaultServiceError, VaultFileError) as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary.get("files_skipped"):
        print(f"warning: {len(summary['files_skipped'])} file(s) could not be read "
             f"and were skipped (see 'files_skipped' above).", file=sys.stderr)
    return 0


def command_restore_paths(args) -> int:
    """Decrypt and unzip a bundle created by encrypt-paths back into a real
    directory tree at the given output directory."""
    service = _open_service(args)
    _unlock(service)
    bulk = BulkFileService(service)
    try:
        result = bulk.restore_paths(args.record_id, args.output_dir)
    except (BulkFileServiceError, VaultServiceError) as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def command_get(args) -> int:
    service = _open_service(args)
    _unlock(service)
    try:
        payload = service.get(args.record_id)
    except VaultServiceError as exc:
        raise AppError(str(exc)) from exc
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_list(args) -> int:
    service = _open_service(args)
    summaries = service.list_records()
    if not summaries:
        print("no records in vault.")
        return 0
    for summary in summaries:
        extra = ""
        if summary["kind"] == "file":
            extra = " (encrypted file record)"
        print(f"{summary['record_id']}: {summary['label']} [{summary['kind']}]{extra} "
              f"(updated {summary['updated_at']})")
    return 0


def command_delete(args) -> int:
    service = _open_service(args)
    if service.delete(args.record_id):
        print(f"deleted {args.record_id!r}.")
        return 0
    print(f"no record found for {args.record_id!r}.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Vault: an encrypted, local, single-file record store.",
    )
    parser.add_argument("--vault", default=None, help="path to the vault file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a new vault.")
    init.set_defaults(handler=command_init)

    migrate = subparsers.add_parser(
        "migrate", help="re-encrypt the vault with the current BSR2 formats.",
    )
    migrate.add_argument("--yes", action="store_true", help="skip the confirmation prompt.")
    migrate.set_defaults(handler=command_migrate)

    upsert = subparsers.add_parser("upsert", help="create or update one JSON-payload record.")
    upsert.add_argument("label")
    upsert.add_argument("--kind", required=True)
    upsert.add_argument("--payload", required=True, help="JSON object string.")
    upsert.add_argument("--record-id", default=None)
    upsert.set_defaults(handler=command_upsert)

    batch_upsert = subparsers.add_parser(
        "batch-upsert", help="create or update many JSON-payload records from a JSON file."
    )
    batch_upsert.add_argument("items_file", help="path to a JSON array of items.")
    batch_upsert.set_defaults(handler=command_batch_upsert)

    encrypt_file = subparsers.add_parser(
        "encrypt-file",
        help="encrypt any local file into the vault, any extension or none at all.",
    )
    encrypt_file.add_argument("file_path", help="path to the file to encrypt.")
    encrypt_file.add_argument("--label", default=None, help="defaults to the file's own name.")
    encrypt_file.add_argument("--record-id", default=None)
    encrypt_file.set_defaults(handler=command_encrypt_file)

    decrypt_file = subparsers.add_parser(
        "decrypt-file", help="decrypt a file record back to disk, byte-for-byte."
    )
    decrypt_file.add_argument("record_id")
    decrypt_file.add_argument("output_path")
    decrypt_file.set_defaults(handler=command_decrypt_file)

    encrypt_paths = subparsers.add_parser(
        "encrypt-paths",
        help="encrypt any combination of files/folders/drive roots as one bundle "
             "(stored as fixed-size sealed chunks).",
    )
    encrypt_paths.add_argument("paths", nargs="+",
                               help="one or more file, folder, or drive root paths.")
    encrypt_paths.add_argument("--label", default=None,
                               help="defaults to the first path's own name.")
    encrypt_paths.add_argument("--record-id", default=None)
    encrypt_paths.add_argument("--chunk-mb", type=int, default=8,
                               help=f"chunk size in MiB (default 8; must be 1..{MAX_CHUNK_MB}).")
    encrypt_paths.set_defaults(handler=command_encrypt_paths)

    restore_paths = subparsers.add_parser(
        "restore-paths", help="decrypt and unzip a bundle back into a real directory tree."
    )
    restore_paths.add_argument("record_id")
    restore_paths.add_argument("output_dir")
    restore_paths.set_defaults(handler=command_restore_paths)

    get = subparsers.add_parser("get", help="retrieve and decrypt one JSON record's payload.")
    get.add_argument("record_id")
    get.set_defaults(handler=command_get)

    list_command = subparsers.add_parser("list", help="list all records (no unlock required).")
    list_command.set_defaults(handler=command_list)

    delete = subparsers.add_parser("delete", help="delete one record.")
    delete.add_argument("record_id")
    delete.set_defaults(handler=command_delete)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return args.handler(args)
    except AppError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except EncryptionNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
