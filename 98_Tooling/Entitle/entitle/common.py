"""
File: entitle/common.py

Purpose
-------
Hold what every part of Entitle shares and no single domain owns: the EntitleError base class,
  canonical JSON (the exact bytes that are sealed, signed and hashed), the UTC clock, the check
  that a required text field is not blank, the stricter check for identifiers that are matched
  exactly and can never be corrected once recorded, and the one way Entitle writes a file it
  must never leave half-written. Keeping them in one leaf module means the record log never
  imports the entitlement rules just to raise an error or hash a record.

Communication / relationships
-----------------------------
Imports only the standard library (datetime, json, os, tempfile, pathlib). Imported by the
  modules in entitle/ (rights, encryption, signing, host, entitlements, records, revoke,
  revocation_list, tracking, checkpoints), by cli.py and gui/window.py (EntitleError), and by
  examples/protected_app_example.py (EntitleError). Covered by tests/test_common.py.

Settings / parameters
---------------------
canonical_json(data) returns UTF-8 bytes with sorted keys, no spaces and non-ASCII kept as
  written. Those bytes are what an entitlement payload is sealed or signed as and what every
  record's entry_hash covers, so changing the encoding would break every record chain, sealed
  file and signature. utc_now() returns an aware UTC datetime; utc_now_iso() the same at second
  resolution as ISO text (for example "2026-11-10T22:56:00+00:00"). require_text(**fields) and
  require_identifier(**fields) take keyword arguments named after the fields, so the error names
  the field the operator typed. write_text_atomically(path, text, overwrite=True, private=False)
  writes UTF-8 with a final newline through a uniquely named temporary file in the same folder,
  flushes it to disk and replaces the target in one step.

Edge cases
----------
There is deliberately no entitle/__init__.py: entitle/ is an implicit namespace package, so
  importing entitle.<module> runs that module and what it imports and nothing else. require_text
  raises ValueError (not EntitleError) for the first value that is not a string, is empty or is
  only whitespace, naming the field ("fork name is required."); values are not stripped.
  require_identifier also refuses spaces at either end and control characters, because a
  revocation recorded for " lab-1" would never revoke "lab-1" and records cannot be edited.
  write_text_atomically with overwrite=False raises FileExistsError for an existing file; on
  POSIX a private file is created owner-only (0600) and any other file follows the umask, and
  a failed replacement leaves the old file and no temporary file behind.

Known limitations
-----------------
utc_now reads the local clock; entitle/host.py is what notices a clock wound backwards.
  require_identifier does not fold case, so "Lab-1" and "lab-1" differ. Records written before
  0.7.0 may hold identifiers with spaces at either end; they are read and matched as written.
  write_text_atomically replaces a symbolic link rather than writing through it, and on Windows
  private files take the folder's permissions.

Examples
--------
From the directory containing run.py:

    from entitle.common import EntitleError, canonical_json, require_identifier, require_text

    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")
    try:
        require_text(product="Demo", fork_name="  ")
    except ValueError as exc:
        assert str(exc) == "fork name is required."
    try:
        require_identifier(entitlement_id=" lab-1")
    except ValueError as exc:
        assert "spaces" in str(exc)
    assert issubclass(EntitleError, Exception)
"""

import datetime
import json
import os
import tempfile
from pathlib import Path


class EntitleError(Exception):
    """Base class for every error Entitle raises on purpose."""


def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def utc_now_iso():
    return utc_now().replace(microsecond=0).isoformat()


def require_text(**fields):
    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name.replace('_', ' ')} is required.")


def require_identifier(**fields):
    require_text(**fields)
    for name, value in fields.items():
        label = name.replace("_", " ")
        if value != value.strip():
            raise ValueError(f"{label} must not start or end with spaces: {value!r}")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError(f"{label} must not contain control characters: {value!r}")


def _umask():
    current = os.umask(0o022)
    os.umask(current)
    return current


def write_text_atomically(path, text, *, overwrite=True, private=False):
    """Write text (UTF-8, no byte-order mark) beside path and replace path in one step.

    A failure never leaves a half-written file. overwrite=False refuses an existing path with
    FileExistsError. private=True makes the file readable by its owner only (POSIX).
    """
    path = Path(path)
    if not overwrite and path.exists():
        raise FileExistsError(f"{path} already exists. Choose another path, or overwrite it on purpose.")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        if os.name != "nt":
            os.fchmod(handle, 0o600 if private else 0o666 & ~_umask())
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text if text.endswith("\n") else text + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
