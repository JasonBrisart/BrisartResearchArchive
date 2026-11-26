"""Purpose
-------
Export, authenticate, and recover password-protected BrisartAI library snapshots.

SQLite supplies a consistent snapshot in memory. The external Official archive
API owns password derivation, encryption and archive authentication.

Communication / relationships
-----------------------------
The CLI supplies the state paths, output path and interactively entered secret.
The backup command never initializes or migrates the application database.

The archive stores the index (including notes and memory in that database) and
optional settings. It does not recursively package the state directory.

Settings / parameters
---------------------
Use BRISART_ENCRYPTION to point at a trusted 97_Encryption/v4 directory
when it cannot be discovered next to the repository's tooling tree.

The snapshot and archive are bounded to 32 MiB and 40 MiB respectively. Output
must be on a filesystem that supports hard links for no-clobber publication.

Edge cases
----------
A missing database, inconsistent snapshot, or existing destination fails.
A failed operation never falls back to writing a plaintext backup.

Verification authenticates the archive, checks the expected members, and checks
the SQLite image without writing recovered data to disk. Restore validates all
members before writing to a new directory and cleans up on handled write errors.

Known limitations
-----------------
This protects exported copies only. The live index, settings, original files,
and any extracted backup remain plaintext. Sensitive bytes are held in memory.

The bounds are for a small-library first pass, not a streaming backup service.
Close BrisartAI before backing up to keep the separate settings file in sync.

Examples
--------
python cli.py backup-create research.bsa

python cli.py backup-verify research.bsa
python cli.py backup-restore research.bsa recovery-copy
"""

from contextlib import closing
from importlib import import_module
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from brisart_ai.state import INDEX_FILENAME, SETTINGS_FILENAME, state_dir

MAX_SNAPSHOT = 32 * 1024**2
MAX_ARCHIVE = 40 * 1024**2
MAX_SETTINGS = 1024**2


class BackupError(Exception):
    """The backup could not be created or verified."""


def _archive_api():
    override = os.environ.get("BRISART_ENCRYPTION")
    candidates = ([Path(override)] if override else
                  [p / "97_Encryption" / "v4" for p in Path(__file__).resolve().parents])
    folder = next((p.resolve() for p in candidates if (p / "brisart_security_archive.py").is_file()), None)
    if folder is None:
        raise BackupError("Set BRISART_ENCRYPTION to the trusted 97_Encryption/v4 directory.")

    def check_origins():
        for name, module in tuple(sys.modules.items()):
            if name.startswith("brisart_security_"):
                origin = getattr(module, "__file__", None)
                if not origin or Path(origin).resolve().parent != folder:
                    raise BackupError("A Brisart Encryption module was loaded outside the selected Official directory.")

    check_origins()
    entry = str(folder)
    sys.path.insert(0, entry)
    try:
        api = import_module("brisart_security_archive")
        check_origins()
        return api
    except ImportError as exc:
        raise BackupError("The selected Official encryption directory is incomplete or incompatible.") from exc
    finally:
        sys.path.remove(entry)


def _bounded(path, limit):
    with Path(path).open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise BackupError("Backup input exceeds its size limit.")
    return data


def _check_index(conn):
    if conn.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise BackupError("The SQLite image did not pass its consistency check.")
    names = {name for (name,) in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
    if not {"sources", "terms"} <= names:
        raise BackupError("The SQLite image is not a BrisartAI library.")


def _snapshot(path, *, max_bytes=MAX_SNAPSHOT):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as src, closing(sqlite3.connect(":memory:")) as dst:
        if not hasattr(dst, "serialize") or not hasattr(dst, "deserialize"):
            raise BackupError("This Python SQLite build does not support in-memory snapshots.")

        def progress(status, remaining, total):
            if max_bytes is not None and total * page_size > max_bytes:
                raise BackupError(f"The database exceeds the {max_bytes // 1024**2} MiB operation limit.")
            if status in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise BackupError("The library is busy; close BrisartAI and try again.")

        page_size = src.execute("PRAGMA page_size").fetchone()[0]
        if max_bytes is not None and src.execute("PRAGMA page_count").fetchone()[0] * page_size > max_bytes:
            raise BackupError(f"The database exceeds the {max_bytes // 1024**2} MiB operation limit.")
        src.backup(dst, pages=64, progress=progress)
        _check_index(dst)
        image = dst.serialize()
        # WAL-mode headers require disk sidecars. Switch the standalone copy
        # to rollback-journal header flags, without modifying the live database.
        if image[18:20] == b"\x02\x02":
            image = image[:18] + b"\x01\x01" + image[20:]
        return image


def _verify(api, blob, password):
    reader = api.ArchiveReader(blob, password=password, max_unpacked_bytes=MAX_SNAPSHOT + MAX_SETTINGS,
                               max_kdf_memory_blocks=api.KdfParams().memory_blocks)
    names = {entry["name"] for entry in reader.directory["entries"]}
    if names not in ({INDEX_FILENAME}, {INDEX_FILENAME, SETTINGS_FILENAME}):
        raise BackupError("Unexpected BrisartAI backup members.")
    image = reader.read(INDEX_FILENAME)
    if len(image) > MAX_SNAPSHOT:
        raise BackupError("The archived database exceeds the snapshot limit.")
    members = {INDEX_FILENAME: image}
    if SETTINGS_FILENAME in names:
        settings = reader.read(SETTINGS_FILENAME)
        if len(settings) > MAX_SETTINGS:
            raise BackupError("The archived settings exceed the size limit.")
        members[SETTINGS_FILENAME] = settings
    with closing(sqlite3.connect(":memory:")) as conn:
        if not hasattr(conn, "deserialize"):
            raise BackupError("This Python SQLite build cannot verify database images.")
        conn.deserialize(image)
        conn.execute("PRAGMA trusted_schema = OFF")
        _check_index(conn)
    return members


def create_backup(db, settings, destination, password):
    path = Path(destination)
    if path.exists() or path.is_symlink():
        raise BackupError("The backup destination already exists.")
    if not password or not password.strip():
        raise BackupError("A nonblank backup passphrase is required.")
    api = _archive_api()
    members = [(INDEX_FILENAME, _snapshot(db), 0, "")]
    if settings is not None and Path(settings).is_file():
        members.append((SETTINGS_FILENAME, _bounded(settings, MAX_SETTINGS), 0, ""))
    try:
        blob = api.build_archive(members, password=password, compression="deflate")
        if len(blob) > MAX_ARCHIVE:
            raise BackupError("The encrypted archive exceeds the size limit.")
        _verify(api, blob, password)
    except api.BrisartArchiveError as exc:
        raise BackupError("The Official archive API could not create or verify the backup.") from exc
    # Stage only ciphertext. Publish atomically without overwriting an existing file.
    with tempfile.TemporaryDirectory(prefix=".brisart-backup-", dir=path.parent) as stage:
        temporary = Path(stage) / "archive.bsa"
        with temporary.open("xb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)


def _read_backup(archive, password):
    api = _archive_api()
    try:
        return _verify(api, _bounded(archive, MAX_ARCHIVE), password)
    except api.BrisartArchiveError as exc:
        raise BackupError("Could not authenticate this backup. Check the passphrase and archive integrity.") from exc



def verify_backup(archive, password):
    _read_backup(archive, password)


def restore_backup(archive, destination, password):
    """Recover verified plaintext files into a new, caller-selected directory."""
    path = Path(destination)
    if path.resolve() == state_dir().resolve():
        raise BackupError("Choose a recovery folder outside the active profile location.")
    if path.exists() or path.is_symlink():
        raise BackupError("The restore destination already exists.")
    members = _read_backup(archive, password)
    path.mkdir(mode=0o700)
    created = []
    try:
        for name, data in members.items():
            target = path / name
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
                created.append(target)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
    except (OSError, KeyboardInterrupt):
        for target in reversed(created):
            target.unlink()
        path.rmdir()
        raise

