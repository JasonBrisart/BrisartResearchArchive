"""
File: vault/store/vault_file.py

Purpose
-------
Low-level, single-file persistence for the vault.

Public interface:
- class VaultFileError(ValueError) -- Raised when a vault file cannot be read,
  written, or is malformed.
- vault_exists(path) -- Report whether a vault file already exists at `path`.
- create_vault_file(path, passphrase) -- Create a brand-new vault file
  protected by `passphrase`.
- load_state(path) -- Load and validate the raw vault file structure.
- load_keyring(path) -- Load just the keyring from a vault file, without
  touching records.
- load_records(path) -- Load just the records map from a vault file:
  `{record_id: record}`.
- save_state(path, state) -- Persist the whole vault file structure atomically.
- save_keyring(path, keyring) -- Persist an updated keyring back into an
  existing vault file.
- save_records(path, records) -- Persist an updated records map back into an
  existing vault file.

Design notes:

A vault is one JSON file containing a :mod:`crypto.keyring` state (the wrapped
master key) and a flat map of record id to sealed vault record. This module
owns reading and writing that file only -- it has no opinion about what a valid
record looks like (that is `vault.records.record_model`'s job) or how unlocking
and mutation should be orchestrated (`vault.store.vault_service`'s job).
Keeping this layer thin means the on-disk format can be inspected or repaired
with nothing more than this module and a JSON viewer.

Communication / relationships
-----------------------------
Depends on (project modules):
- common.atomic_io (common/atomic_io.py)
- crypto.keyring (crypto/keyring.py)
Standard library: json, pathlib.
Imported by:
- gui/tabs/tab_vault.py
- vault/app.py
- vault/store/vault_service.py
Covered by tests: gui/tests/test_tab_vault.py,
vault/tests/test_bulk_file_service.py,
vault/tests/test_public_summary_file_metadata.py,
vault/tests/test_sealed_vault.py, vault/tests/test_unlock_throttle.py.

Settings / parameters
---------------------
- VAULT_FORMAT = "brisart-identity-tools/vault-file/v1"

Edge cases
----------
- create_vault_file() raises VaultFileError: "a vault file already exists at
  {...}."
- load_state() raises VaultFileError: "no vault file found at {...}."
- load_state() raises VaultFileError: "vault file could not be read: {...}"
- load_state() raises VaultFileError: "vault file must contain a JSON object."
- load_state() raises VaultFileError: "unsupported vault file format."
- load_state() raises VaultFileError: "vault file is missing a valid keyring
  section."
- load_state() raises VaultFileError: "vault file is missing a valid records
  section."
- save_state() raises VaultFileError: "state does not have the expected vault
  format marker."
- load_state(): translates (OSError, json.JSONDecodeError) into VaultFileError;
  other exceptions may still propagate.

Known limitations
-----------------
- Writes go through :mod:`common.atomic_io` so a crash or power loss mid-write
  cannot leave a half-written vault file behind.
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: path, passphrase stand for values the
caller supplies.

::

    from vault.store.vault_file import (
        vault_exists,
        create_vault_file,
        load_state,
    )
    vault_exists(path)
    create_vault_file(path, passphrase)
    load_state(path)
"""

import json
from pathlib import Path

from common.atomic_io import SENSITIVE_FILE_MODE, atomic_write_json, warn_if_permissive
from crypto.keyring import Keyring

VAULT_FORMAT = "brisart-identity-tools/vault-file/v1"


class VaultFileError(ValueError):
    """Raised when a vault file cannot be read, written, or is malformed."""


def _empty_state(keyring_state: dict) -> dict:
    return {
        "format": VAULT_FORMAT,
        "keyring": keyring_state,
        "records": {},
    }


def vault_exists(path) -> bool:
    """Report whether a vault file already exists at `path`."""
    return Path(path).is_file()


def create_vault_file(path, passphrase: str):
    """Create a brand-new vault file protected by `passphrase`.

    Returns `(keyring, recovery_code)`. Refuses to overwrite an existing
    file, since doing so would silently discard every record already stored
    there. The file is written with owner-only permissions
    (common.atomic_io.SENSITIVE_FILE_MODE) on POSIX platforms, since it holds
    the BSR2-wrapped master key for every record in the vault.
    """
    resolved = Path(path)
    if resolved.is_file():
        raise VaultFileError(f"a vault file already exists at {resolved}.")
    keyring, recovery_code = Keyring.create(passphrase)
    state = _empty_state(keyring.to_state())
    atomic_write_json(resolved, state, file_mode=SENSITIVE_FILE_MODE)
    return keyring, recovery_code


def load_state(path) -> dict:
    """Load and validate the raw vault file structure.

    Returns the whole on-disk dict (`format`, `keyring`, `records`).
    Callers that only need the keyring or only need records should use
    :func:`load_keyring` or :func:`load_records` instead of re-validating
    this themselves.

    After a successful load, this checks the file's on-disk permissions and
    prints an advisory to stderr (via common.atomic_io.warn_if_permissive)
    if they are more permissive than owner-only -- a no-op on Windows and a
    no-op if the file already matches. This never blocks or fails the load;
    it is advisory only, since BSR2's own encryption is the real protection
    for the wrapped master key inside.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise VaultFileError(f"no vault file found at {resolved}.")
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise VaultFileError(f"vault file could not be read: {exc}") from exc
    if not isinstance(state, dict):
        raise VaultFileError("vault file must contain a JSON object.")
    if state.get("format") != VAULT_FORMAT:
        raise VaultFileError("unsupported vault file format.")
    if not isinstance(state.get("keyring"), dict):
        raise VaultFileError("vault file is missing a valid keyring section.")
    if not isinstance(state.get("records"), dict):
        raise VaultFileError("vault file is missing a valid records section.")
    warn_if_permissive(resolved, label="vault file")
    return state


def load_keyring(path) -> Keyring:
    """Load just the keyring from a vault file, without touching records."""
    state = load_state(path)
    return Keyring(state["keyring"])


def load_records(path) -> dict:
    """Load just the records map from a vault file: `{record_id: record}`."""
    return load_state(path)["records"]


def save_state(path, state: dict) -> None:
    """Persist the whole vault file structure atomically.

    Written with owner-only permissions (common.atomic_io.SENSITIVE_FILE_MODE)
    on POSIX platforms, matching create_vault_file, since every write to this
    file re-writes the section holding the BSR2-wrapped master key.
    """
    if state.get("format") != VAULT_FORMAT:
        raise VaultFileError("state does not have the expected vault format marker.")
    atomic_write_json(Path(path), state, file_mode=SENSITIVE_FILE_MODE)


def save_keyring(path, keyring: Keyring) -> None:
    """Persist an updated keyring back into an existing vault file.

    Used after :meth:`crypto.keyring.Keyring.change_passphrase` or
    :meth:`crypto.keyring.Keyring.rotate_recovery_code`, which mutate the
    keyring in memory but do not themselves touch disk.
    """
    state = load_state(path)
    state["keyring"] = keyring.to_state()
    save_state(path, state)


def save_records(path, records: dict) -> None:
    """Persist an updated records map back into an existing vault file."""
    state = load_state(path)
    state["records"] = records
    save_state(path, state)




