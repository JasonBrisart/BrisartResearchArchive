"""
File: biometrics/identity/identity_store.py

Purpose
-------
Filesystem persistence for identity records.

Public interface:
- class IdentityStoreError(ValueError) -- Raised on invalid identity ids or
  store I/O failures.
- class IdentityStore -- A directory of identity records, one JSON file per
  identity. Public methods: exists, save, load, delete, list_identity_ids,
  list_records.

Design notes:

One record is stored per file, named by its identity id, under the configured
identity directory (see ``biometrics.config.settings``). Writes go through
:mod:`common.atomic_io` so a crash or power loss mid-write cannot leave a
half-written record behind -- the store either has the old file or the new one,
never a truncated one.

Record shape validation is delegated entirely to
:mod:`biometrics.identity.identity_record`, so a record's structural rules live
in exactly one place.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.identity.identity_record (biometrics/identity/identity_record.py)
- common.atomic_io (common/atomic_io.py)
- common.timestamps (common/timestamps.py)
Standard library: json, pathlib.
Imported by:
- biometrics/app.py
- gui/tabs/tab_biometrics.py
Covered by tests: biometrics/tests/test_enrollment_overwrite.py,
biometrics/tests/test_identity_id_validation.py,
biometrics/tests/test_sealed_biometrics_flow.py,
gui/tests/test_tab_biometrics.py.

Settings / parameters
---------------------
- RECORD_SUFFIX = ".json"

Edge cases
----------
- _validate_identity_id() raises IdentityStoreError: "identity_id must be a
  non-empty string."
- _validate_identity_id() raises IdentityStoreError: "identity_id cannot
  contain path separators or '..'."
- _validate_identity_id() raises IdentityStoreError: "identity_id cannot have
  leading or trailing whitespace."
- IdentityStore.load() raises IdentityStoreError: "no identity record found for
  {...}."
- IdentityStore.load() raises IdentityStoreError: "identity record for {...}
  could not be read: {...}"
- IdentityStore.load() raises IdentityStoreError: "identity record file for
  {...} is malformed."
- IdentityStore.list_records(): catches IdentityStoreError and handles it in
  place; it does not propagate to the caller.
- IdentityStore.load(): translates (OSError, json.JSONDecodeError) into
  IdentityStoreError; other exceptions may still propagate.

Known limitations
-----------------
- This module owns file I/O and directory listing only.

Examples
--------
Call shapes only, not a runnable script: identity_dir, identity_id stand for
values the caller supplies.

::

    from biometrics.identity.identity_store import IdentityStore
    obj = IdentityStore(identity_dir)
    obj.exists(identity_id)
"""

import json
from pathlib import Path

from biometrics.identity.identity_record import validate_record
from common.atomic_io import atomic_write_json
from common.timestamps import utc_now_iso

RECORD_SUFFIX = ".json"


class IdentityStoreError(ValueError):
    """Raised on invalid identity ids or store I/O failures."""


def _validate_identity_id(identity_id: str) -> str:
    if not isinstance(identity_id, str) or not identity_id:
        raise IdentityStoreError("identity_id must be a non-empty string.")
    # Reject path separators and traversal sequences outright: identity_id
    # becomes part of a filesystem path below, and a hostile or malformed id
    # containing "../" must not be able to escape the identity directory.
    if "/" in identity_id or "\\" in identity_id or ".." in identity_id:
        raise IdentityStoreError(
            "identity_id cannot contain path separators or '..'."
        )
    if identity_id.strip() != identity_id:
        raise IdentityStoreError("identity_id cannot have leading or trailing whitespace.")
    return identity_id


class IdentityStore:
    """A directory of identity records, one JSON file per identity."""

    def __init__(self, identity_dir):
        self.identity_dir = Path(identity_dir)
        self.identity_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, identity_id: str) -> Path:
        _validate_identity_id(identity_id)
        return self.identity_dir / f"{identity_id}{RECORD_SUFFIX}"

    def exists(self, identity_id: str) -> bool:
        return self._path_for(identity_id).is_file()

    def save(self, record: dict) -> None:
        """Validate and persist a record, overwriting any existing one."""
        validated = validate_record(record)
        path = self._path_for(validated["identity_id"])
        envelope = {
            "record": validated,
            "saved_at": utc_now_iso(),
        }
        atomic_write_json(path, envelope)

    def load(self, identity_id: str) -> dict:
        """Load and validate a record by id.

        Raises :class:`IdentityStoreError` if the identity does not exist or
        its stored file fails validation -- a corrupted record is surfaced
        immediately rather than silently ignored.
        """
        path = self._path_for(identity_id)
        if not path.is_file():
            raise IdentityStoreError(f"no identity record found for {identity_id!r}.")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                envelope = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise IdentityStoreError(
                f"identity record for {identity_id!r} could not be read: {exc}"
            ) from exc
        if not isinstance(envelope, dict) or "record" not in envelope:
            raise IdentityStoreError(
                f"identity record file for {identity_id!r} is malformed."
            )
        return validate_record(envelope["record"])

    def delete(self, identity_id: str) -> bool:
        """Delete a record by id. Returns ``False`` if it did not exist."""
        path = self._path_for(identity_id)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def list_identity_ids(self) -> list:
        """List all identity ids currently in the store, sorted."""
        return sorted(
            path.stem for path in self.identity_dir.glob(f"*{RECORD_SUFFIX}")
        )

    def list_records(self) -> list:
        """Load every record in the store.

        A record that fails validation is skipped rather than aborting the
        whole listing, so one corrupted file does not hide every other
        identity from an inventory or CLI listing command.
        """
        records = []
        for identity_id in self.list_identity_ids():
            try:
                records.append(self.load(identity_id))
            except IdentityStoreError:
                continue
        return records




