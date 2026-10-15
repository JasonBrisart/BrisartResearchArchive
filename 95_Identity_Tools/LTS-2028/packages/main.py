"""
File: packages/main.py

Purpose
-------
Identity-Bound Packages command-line interface.

Public interface:
- class AppError(ValueError) -- Raised for user-facing CLI failures.
- command_create(args)
- command_add_recipient(args)
- command_remove_recipient(args)
- command_open(args)
- command_list_recipients(args)
- command_verify_custody(args)
- command_demo(_args) -- Run a full create -> add-recipient -> open cycle with
  generated keys.
- build_parser()
- main(argv=None)

Design notes:

Since a package requires an existing recipient's master key to authorize adding
or removing another recipient (see ``package.add_recipient`` /
``package.remove_recipient``), this CLI works against a local JSON file per
package and prompts for whichever master keys an operation needs. A "demo"
command is included that runs a full create -> add-recipient -> open cycle in
one shot with generated keys, useful for a quick end-to-end sanity check with
no setup.

Communication / relationships
-----------------------------
Depends on (project modules):
- packages.package (packages/package.py)
- packages.custody (packages/custody.py)
- packages.identity (packages/identity.py)
- common.atomic_io (common/atomic_io.py)
Standard library: argparse, getpass, hashlib, json, pathlib, secrets, sys.
Imported by:
- cli.py
Covered by tests: tests/test_cli_dispatcher.py.

Settings / parameters
---------------------
- DEFAULT_AUDIT_DIR = Path("data") / "packages" / "audit"

Commands (each takes the options listed under it):
- create -- create a new package.
  - package_file: path to the package JSON file.
  - --package-id: required; id stored in the package and bound into its custody
    chain.
  - --identity-id: required; id of the first recipient, the creator.
  - --label: required; display label for that recipient.
  - --payload (required): JSON object string.
- add-recipient -- add a recipient to an existing package.
  - package_file: path to the package JSON file.
  - --identity-id: required; id of the recipient being added.
  - --label: required; display label for the new recipient.
  - --opener-identity-id: required; an existing recipient who authorizes the
    addition (you are prompted for that recipient's master key text).
- remove-recipient -- remove a recipient from a package.
  - package_file: path to the package JSON file.
  - --identity-id: required; id of the recipient to remove.
  - --opener-identity-id: required; an existing recipient who authorizes the
    removal (you are prompted for their master key text).
- open -- open a package's payload as a recipient.
  - package_file: path to the package JSON file.
  - --identity-id: required; the recipient opening the package (you are
    prompted for that recipient's master key text).
- list-recipients -- list a package's recipients.
  - package_file: path to the package JSON file.
- verify-custody -- verify and print a package's custody chain.
  - package_file: path to the package JSON file.
- demo -- run a full create/add/open cycle with generated keys.
  - no options of its own.

Edge cases
----------
- _load_state() raises AppError: "no package file found at {...}."
- _load_state() raises AppError: "package file could not be read: {...}"
- _load_state() raises AppError: "package file is invalid: {...}"
- command_create() raises AppError: "a package file already exists at {...}."
- command_create() raises AppError: "--payload must be valid JSON: {...}"
- command_create() raises AppError: "--payload must be a JSON object."
- command_create() raises AppError.
- command_add_recipient() raises AppError.
- command_remove_recipient() raises AppError.
- command_open() raises AppError.
- Run as a script, the process exit status is main()'s return value (via
  ``raise SystemExit(main())``).
- _load_state(): translates (OSError, json.JSONDecodeError) into AppError, so
  callers only need to handle this module's own error type.
- _load_state(): translates (PackageError, CustodyError) into AppError, so
  callers only need to handle this module's own error type.
- command_add_recipient(): translates (PackageError, PackageAuthorizationError,
  RecipientIdentityError) into AppError, so callers only need to handle this
  module's own error type.
- command_create(): translates (PackageError, RecipientIdentityError) into
  AppError, so callers only need to handle this module's own error type.
- command_create(): translates json.JSONDecodeError into AppError, so callers
  only need to handle this module's own error type.
- command_open(): translates PackageAuthorizationError into AppError, so
  callers only need to handle this module's own error type.
- command_remove_recipient(): translates (PackageError,
  PackageAuthorizationError) into AppError, so callers only need to handle this
  module's own error type.
- main(): catches AppError and handles it in place; it does not propagate to
  the caller.

Known limitations
-----------------
- Master keys are typed text hashed once. _prompt_master_key() reads text with
  getpass and turns it into a 32-byte key with a single unsalted SHA-256. The
  source comment calls this a CLI-friendly stand-in for a real master key
  source; it is not a password KDF, so the same text always gives the same key
  and a guessable text gives a guessable key. The GUI Packages tab does the
  same.
- _save_state() writes through common.atomic_io.atomic_write_json, so an
  interrupted save leaves the previous package file intact rather than a
  truncated one. It does not lock the file: two processes saving the same
  package at once can still lose one update.
- No test runs this module's commands; tests/test_cli_dispatcher.py imports it
  only to check exit-status pass-through with main() replaced. Verify changes
  by running it manually.

Examples
--------
::

    python -m packages.main --help
    python -m packages.main create --help
    python -m packages.main add-recipient --help
    python -m packages.main remove-recipient --help
"""

import argparse
import getpass
import json
import secrets
import sys
from pathlib import Path

from common.atomic_io import atomic_write_json
from packages import package
from packages.custody import CustodyError
from packages.identity import RecipientIdentityError
from packages.package import PackageAuthorizationError, PackageError

DEFAULT_AUDIT_DIR = Path("data") / "packages" / "audit"


class AppError(ValueError):
    """Raised for user-facing CLI failures."""


def _load_state(path: Path) -> dict:
    if not path.is_file():
        raise AppError(f"no package file found at {path}.")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError(f"package file could not be read: {exc}") from exc
    try:
        return package.validate_package(state)
    except (PackageError, CustodyError) as exc:
        raise AppError(f"package file is invalid: {exc}") from exc


def _save_state(path: Path, state: dict) -> None:
    atomic_write_json(path, state)


def _prompt_master_key(identity_id: str) -> bytes:
    passphrase = getpass.getpass(f"master key material for {identity_id!r} (any text): ")
    # A CLI-friendly stand-in for a real master key source: any text the
    # operator supplies is stretched to a fixed-length key. Production
    # integrations should supply a real 32-byte master key (for example, one
    # unlocked from crypto.keyring.Keyring) instead of typed text.
    import hashlib
    return hashlib.sha256(passphrase.encode("utf-8")).digest()


def command_create(args) -> int:
    path = Path(args.package_file)
    if path.is_file():
        raise AppError(f"a package file already exists at {path}.")
    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        raise AppError(f"--payload must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AppError("--payload must be a JSON object.")

    master_key = _prompt_master_key(args.identity_id)
    recipients = {args.identity_id: (args.label, master_key)}
    try:
        state = package.create_package(
            args.package_id, args.label, payload, recipients, audit_dir=DEFAULT_AUDIT_DIR
        )
    except (PackageError, RecipientIdentityError) as exc:
        raise AppError(str(exc)) from exc
    _save_state(path, state)
    print(f"created package {args.package_id!r} at {path} with recipient {args.identity_id!r}.")
    return 0


def command_add_recipient(args) -> int:
    path = Path(args.package_file)
    state = _load_state(path)
    opener_master_key = _prompt_master_key(args.opener_identity_id)
    new_master_key = _prompt_master_key(args.identity_id)
    try:
        updated = package.add_recipient(
            state,
            args.identity_id,
            args.label,
            new_master_key,
            args.opener_identity_id,
            opener_master_key,
            audit_dir=DEFAULT_AUDIT_DIR,
        )
    except (PackageError, PackageAuthorizationError, RecipientIdentityError) as exc:
        raise AppError(str(exc)) from exc
    _save_state(path, updated)
    print(f"added recipient {args.identity_id!r} to package {state['package_id']!r}.")
    return 0


def command_remove_recipient(args) -> int:
    path = Path(args.package_file)
    state = _load_state(path)
    opener_master_key = _prompt_master_key(args.opener_identity_id)
    try:
        updated = package.remove_recipient(
            state, args.identity_id, args.opener_identity_id, opener_master_key,
            audit_dir=DEFAULT_AUDIT_DIR,
        )
    except (PackageError, PackageAuthorizationError) as exc:
        raise AppError(str(exc)) from exc
    _save_state(path, updated)
    print(f"removed recipient {args.identity_id!r} from package {state['package_id']!r}.")
    return 0


def command_open(args) -> int:
    path = Path(args.package_file)
    state = _load_state(path)
    master_key = _prompt_master_key(args.identity_id)
    try:
        payload, updated = package.open_package(
            state, args.identity_id, master_key, audit_dir=DEFAULT_AUDIT_DIR
        )
    except PackageAuthorizationError as exc:
        raise AppError(str(exc)) from exc
    _save_state(path, updated)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def command_list_recipients(args) -> int:
    state = _load_state(Path(args.package_file))
    for recipient in package.list_recipients(state):
        print(f"{recipient['identity_id']}: {recipient['label']}")
    return 0


def command_verify_custody(args) -> int:
    state = _load_state(Path(args.package_file))
    print(f"custody chain verified: {len(state['custody_chain'])} entries.")
    for entry in package.custody_summary(state):
        print(f"  {entry['recorded_at']}  {entry['action']:<20} {entry['actor_label']}")
    return 0


def command_demo(_args) -> int:
    """Run a full create -> add-recipient -> open cycle with generated keys."""
    package_id = f"demo-{secrets.token_hex(4)}"
    alice_key = secrets.token_bytes(32)
    bob_key = secrets.token_bytes(32)

    print(f"creating package {package_id!r} with recipient 'alice'...")
    state = package.create_package(
        package_id, "Alice", {"message": "hello from the demo package"},
        {"alice": ("Alice", alice_key)},
    )

    print("adding recipient 'bob' (authorized by alice)...")
    state = package.add_recipient(state, "bob", "Bob", bob_key, "alice", alice_key)

    print("opening the package as 'bob'...")
    payload, state = package.open_package(state, "bob", bob_key)
    print(f"bob opened the package and read: {payload!r}")

    print("verifying the custody chain...")
    package.validate_package(state)
    for entry in package.custody_summary(state):
        print(f"  {entry['recorded_at']}  {entry['action']:<20} {entry['actor_label']}")
    print("demo complete: custody chain is intact.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="package",
        description="Identity-Bound Packages: content sealed to specific recipient identities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a new package.")
    create.add_argument("package_file")
    create.add_argument("--package-id", required=True)
    create.add_argument("--identity-id", required=True)
    create.add_argument("--label", required=True)
    create.add_argument("--payload", required=True, help="JSON object string.")
    create.set_defaults(handler=command_create)

    add_recipient = subparsers.add_parser("add-recipient", help="add a recipient to an existing package.")
    add_recipient.add_argument("package_file")
    add_recipient.add_argument("--identity-id", required=True)
    add_recipient.add_argument("--label", required=True)
    add_recipient.add_argument("--opener-identity-id", required=True)
    add_recipient.set_defaults(handler=command_add_recipient)

    remove_recipient = subparsers.add_parser("remove-recipient", help="remove a recipient from a package.")
    remove_recipient.add_argument("package_file")
    remove_recipient.add_argument("--identity-id", required=True)
    remove_recipient.add_argument("--opener-identity-id", required=True)
    remove_recipient.set_defaults(handler=command_remove_recipient)

    open_command = subparsers.add_parser("open", help="open a package's payload as a recipient.")
    open_command.add_argument("package_file")
    open_command.add_argument("--identity-id", required=True)
    open_command.set_defaults(handler=command_open)

    list_recipients = subparsers.add_parser("list-recipients", help="list a package's recipients.")
    list_recipients.add_argument("package_file")
    list_recipients.set_defaults(handler=command_list_recipients)

    verify_custody = subparsers.add_parser("verify-custody", help="verify and print a package's custody chain.")
    verify_custody.add_argument("package_file")
    verify_custody.set_defaults(handler=command_verify_custody)

    demo = subparsers.add_parser("demo", help="run a full create/add/open cycle with generated keys.")
    demo.set_defaults(handler=command_demo)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    try:
        return args.handler(args)
    except AppError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())




