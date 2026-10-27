"""
File: common/atomic_io.py

Purpose
-------
Atomic JSON/text file writes, the single canonical copy.

Public interface:
- class AtomicWriteError(Exception) -- Raised when a file could not be written
  atomically.
- atomic_write_text(path, text, *, fsync_dir=True, make_parents=True,
  file_mode=None) -- Write text to path atomically via a temp file and
  os.replace.
- atomic_write_json(path, data, *, fsync_dir=True, make_parents=True,
  file_mode=None) -- Serialise data (indent=2, sort_keys=True,
  ensure_ascii=False) and write it atomically, matching every existing call
  site's serialisation.
- warn_if_permissive(path, expected_mode=SENSITIVE_FILE_MODE, label="file") --
  Check an on-disk file's permissions and print an advisory if too open.

Design notes:

Replaces the write-to-temp-then-rename dance that existed in three places
(vault_file.save_vault_file, identity_store.save_json, report_writer). Two of
them fsync the containing directory for durability; the report writer did not.
That difference was preserved as the fsync_dir flag rather than silently
unified, because a report is regenerable and a vault is not. No application
caller passes fsync_dir=False today (only tests do), so every production write
attempts directory fsync where supported; failures are best effort.

Communication / relationships
-----------------------------
Standard library: json, os, pathlib, secrets, stat, sys, typing.
Imported by:
- biometrics/app.py
- biometrics/identity/identity_store.py
- biometrics/identity/keyring_access.py
- biometrics/reports/report_writer.py
- common/integrity_ledger.py
- gui/tabs/tab_biometrics.py
- gui/tabs/tab_packages.py
- packages/audit.py
- packages/demo.py
- packages/main.py
- vault/reports/audit_log.py
- vault/store/vault_file.py
Covered by tests: common/tests/test_common_utils.py.

Settings / parameters
---------------------
- SENSITIVE_FILE_MODE = 0o600

Edge cases
----------
- atomic_write_text() raises AtomicWriteError: "unable to write file: {...}"
- atomic_write_json() raises AtomicWriteError: "data to write must be a JSON
  object."
- _apply_file_mode(): ignores OSError from chmod. warn_if_permissive() ignores
  OSError from stat, but failures while printing its warning can propagate.
- _flush_directory(): ignores OSError from opening or fsyncing the directory;
  an OSError from closing its descriptor can propagate.
- atomic_write_text(): catches and ignores an OSError raised while
  deleting its temporary file after a failed write, so cleanup never masks the
  original failure.
- atomic_write_text(): translates OSError into AtomicWriteError; other
  exceptions may still propagate.

Known limitations
-----------------
- Parent-directory creation occurs before the write try/except, so its
  OSError can escape without AtomicWriteError. JSON serialization can raise
  TypeError or ValueError before the atomic write begins.
- Temporary-file permissions follow the process umask; requested POSIX mode
  is tightened only after replacement. This is not secure temporary-file
  creation, a multi-file transaction, or a universal durability guarantee.
- A reader sees either the old file or the fully-written new one, never a half-
  written file: bytes land in a uniquely-named temp file that is os.replace-d
  into position only after being flushed and fsync-ed.
- Behaviour branches on the host operating system (sys.platform / os.name
  checks in the code); verify changes on Windows, macOS, and Linux.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path

    from common.atomic_io import atomic_write_json, atomic_write_text

    with tempfile.TemporaryDirectory() as folder:
        data_path = Path(folder) / "data.json"
        atomic_write_text(Path(folder) / "note.txt", "hello")
        atomic_write_json(data_path, {"b": 2, "a": 1})
        print(data_path.read_text())        # keys sorted, indent 2
"""

import json
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Optional, Union


# The permission mode this module recommends for any file holding a
# BSR2-wrapped master key (a vault.json or a biometrics keyring.json):
# owner read/write only, nothing for group or other. Exposed as a constant
# so callers request it by name (file_mode=SENSITIVE_FILE_MODE) rather than
# each hardcoding the same octal literal.
SENSITIVE_FILE_MODE = 0o600


class AtomicWriteError(Exception):
    """Raised when a file could not be written atomically."""


def _flush_directory(directory: Path) -> None:
    """fsync a directory so a rename into it is durable. No-op on Windows."""
    if os.name == "nt":
        return
    descriptor = None
    try:
        descriptor = os.open(str(directory), os.O_RDONLY)
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _apply_file_mode(path: Path, file_mode: Optional[int]) -> None:
    """Chmod a just-written file to file_mode, if requested.

    A no-op when file_mode is None (the default for every existing caller),
    and a no-op on Windows regardless of file_mode -- see this module's
    docstring for why enforcing POSIX bits there would be misleading rather
    than protective. A chmod failure (e.g. a filesystem that does not support
    the requested bits) is swallowed rather than raised: the write itself
    already succeeded, and failing to additionally restrict its permissions
    should not be treated the same as failing to write the data at all.
    """
    if file_mode is None:
        return
    if os.name == "nt":
        return
    try:
        os.chmod(path, file_mode)
    except OSError:
        pass


def atomic_write_text(
    path: Union[str, Path],
    text: str,
    *,
    fsync_dir: bool = True,
    make_parents: bool = True,
    file_mode: Optional[int] = None,
) -> None:
    """Write text to path atomically via a temp file and os.replace.

    file_mode: optional. When given (e.g. SENSITIVE_FILE_MODE), the
    requested mode is applied after the atomic rename on POSIX only
    (see _apply_file_mode). chmod is best effort: failure is ignored, so
    the requested mode is not guaranteed. Defaults to None, which
    preserves this function's pre-existing behavior exactly: no permission
    change is made and the file keeps whatever mode the process umask
    produced when the temp file was created.
    """
    target = Path(path)
    if make_parents:
        target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, target)
        _apply_file_mode(target, file_mode)
        if fsync_dir:
            _flush_directory(target.parent)
    except OSError as exc:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise AtomicWriteError(f"unable to write file: {target}") from exc


def atomic_write_json(
    path: Union[str, Path],
    data: dict,
    *,
    fsync_dir: bool = True,
    make_parents: bool = True,
    file_mode: Optional[int] = None,
) -> None:
    """Serialise data (indent=2, sort_keys=True, ensure_ascii=False) and write it
    atomically, matching every existing call site's serialisation.

    file_mode: optional, passed straight through to atomic_write_text. See
    that function's docstring; defaults to None (no permission change).
    """
    if not isinstance(data, dict):
        raise AtomicWriteError("data to write must be a JSON object.")
    serialized = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    atomic_write_text(
        path, serialized, fsync_dir=fsync_dir, make_parents=make_parents, file_mode=file_mode
    )


def warn_if_permissive(
    path: Union[str, Path],
    expected_mode: int = SENSITIVE_FILE_MODE,
    label: str = "file",
) -> bool:
    """Check an on-disk file's permissions and print an advisory if too open.

    Intended to be called right after a sensitive file (a vault.json or a
    biometrics keyring.json) is loaded, so a file that was created before
    this protection existed, or one that was widened later by hand, gets
    flagged instead of silently trusted.

    Returns True if a warning was printed, False otherwise. An OSError from
    stat (including a missing file) returns False. Windows also returns False
    because POSIX modes are not meaningfully comparable there. Invalid
    arguments or a failure while writing to stderr can still raise. This is an
    advisory
    best-effort check, not a security control in its own right -- BSR2's
    encryption is what actually protects the file's contents.

    label is purely cosmetic, used to make the printed warning name the
    specific file being checked (e.g. "vault file" vs "biometrics keyring").
    """
    if os.name == "nt":
        return False
    resolved = Path(path)
    try:
        current_mode = stat.S_IMODE(resolved.stat().st_mode)
    except OSError:
        return False
    if current_mode & ~expected_mode:
        print(
            f"warning: {label} at {resolved} has permissions "
            f"{oct(current_mode)}, which is more permissive than the "
            f"recommended {oct(expected_mode)} (owner read/write only). "
            f"Consider running 'chmod 600 {resolved}' to restrict access.",
            file=sys.stderr,
        )
        return True
    return False




