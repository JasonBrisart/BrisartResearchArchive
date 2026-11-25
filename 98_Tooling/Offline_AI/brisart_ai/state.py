r"""
File: brisart_ai/state.py

Purpose
-------
Resolve per-user paths and migrate eligible legacy settings and indexes.

Public operations: state_dir (environ=None, platform=None, home=None) - Return the
folder that holds BrisartAI's saved state. Does not create it; index_path ();
settings_path (); migrate_legacy_state (project_root=PROJECT_ROOT, environ=None,
target=None, log=_warn) - Move the index and settings from beside the program into the
per-user folder.

Internal helpers include _warn, _migration_lock, _fsync_file, _table_counts,
_remove_with_sidecars, _is_empty_index, _move_index, _move_file.

Communication / relationships
-----------------------------
Both launchers call migrate_legacy_state; settings and the index use default paths from
here.

No direct project import appears in this module’s top-level imports. The file is reached
as a launcher, test, or helper, or through a runtime import rather than through an
ordinary domain import.

Concrete calls within this file include sqlite3.connect, sqlite3.DatabaseError.

Settings / parameters
---------------------
BRISARTAI_STATE_DIR selects another directory and opts out of legacy migration.

Module configuration and named constants: STATE_VENDOR_DIRNAME='Brisart Research
Archive', STATE_APP_DIRNAME='BrisartAI', STATE_DIR_ENV='BRISARTAI_STATE_DIR',
INDEX_FILENAME='brisart_ai_index.sqlite3', SETTINGS_FILENAME='research_settings.json',
LOCK_FILENAME='.migrate.lock', LOCK_STALE_SECONDS=120.0, LOCK_WAIT_SECONDS=150.0,
PROJECT_ROOT.

Call signatures: state_dir(environ=None, platform=None, home=None); index_path();
settings_path(); migrate_legacy_state(project_root=PROJECT_ROOT, environ=None,
target=None, log=_warn).

Edge cases
----------
Migration uses a lock and preserves existing destination state rather than overwriting
it.

Explicit exception branches or raised errors in this file include sqlite3.Error,
(OSError, sqlite3.Error), OSError, FileExistsError, sqlite3.DatabaseError,
FileNotFoundError, TimeoutError.

Known limitations
-----------------
Filesystem permissions and operating-system profile synchronization still apply; this is
not encryption.

Examples
--------
state.index_path()

Other callable entry points in this module include index_path, settings_path,
migrate_legacy_state.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Mapping, Optional

STATE_VENDOR_DIRNAME = "Brisart Research Archive"
STATE_APP_DIRNAME = "BrisartAI"
STATE_DIR_ENV = "BRISARTAI_STATE_DIR"
INDEX_FILENAME = "brisart_ai_index.sqlite3"
SETTINGS_FILENAME = "research_settings.json"
LOCK_FILENAME = ".migrate.lock"
LOCK_STALE_SECONDS = 120.0
LOCK_WAIT_SECONDS = 150.0
PROJECT_ROOT = Path(__file__).resolve().parents[1]
_INDEX_SIDECARS = ("-wal", "-shm", "-journal")


def state_dir(
    environ: Optional[Mapping[str, str]] = None,
    platform: Optional[str] = None,
    home: Optional[Path] = None,
) -> Path:
    """Return the folder that holds BrisartAI's saved state. Does not create it."""
    env = os.environ if environ is None else environ
    override = str(env.get(STATE_DIR_ENV, "")).strip()
    if override:
        return Path(override).expanduser()
    system = sys.platform if platform is None else platform
    home_dir = Path.home() if home is None else Path(home)
    if system.startswith("win"):
        base = env.get("APPDATA") or str(home_dir / "AppData" / "Roaming")
    elif system == "darwin":
        base = str(home_dir / "Library" / "Application Support")
    else:
        base = env.get("XDG_CONFIG_HOME") or str(home_dir / ".config")
    return Path(base) / STATE_VENDOR_DIRNAME / STATE_APP_DIRNAME


def index_path() -> Path:
    return state_dir() / INDEX_FILENAME


def settings_path() -> Path:
    return state_dir() / SETTINGS_FILENAME


def _warn(message: str) -> None:
    print(message, file=sys.stderr)


@contextlib.contextmanager
def _migration_lock(folder: Path) -> Iterator[None]:
    lock = folder / LOCK_FILENAME
    deadline = time.monotonic() + LOCK_WAIT_SECONDS
    descriptor = None
    while descriptor is None:
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not take {lock} within {LOCK_WAIT_SECONDS:.0f} s")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(descriptor)
        with contextlib.suppress(OSError):
            lock.unlink()


def _fsync_file(path: Path) -> None:
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())


def _table_counts(connection: sqlite3.Connection) -> Dict[str, int]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        name: connection.execute('SELECT COUNT(*) FROM "%s"' % name.replace('"', '""')).fetchone()[0]
        for name in names
    }


def _remove_with_sidecars(path: Path) -> None:
    for suffix in ("",) + _INDEX_SIDECARS:
        with contextlib.suppress(OSError):
            Path(str(path) + suffix).unlink()


def _is_empty_index(path: Path) -> bool:
    try:
        with contextlib.closing(sqlite3.connect(str(path), timeout=5)) as connection:
            return all(count == 0 for count in _table_counts(connection).values())
    except sqlite3.Error:
        return False


def _move_index(old: Path, new: Path, log: Callable[[str], None]) -> bool:
    if not old.exists() or (new.exists() and not _is_empty_index(new)):
        return False
    temporary = new.with_name("." + new.name + ".migrating")
    try:
        source = sqlite3.connect(str(old), timeout=5)
        try:
            destination = sqlite3.connect(str(temporary))
            try:
                source.backup(destination)
            finally:
                destination.close()
            expected = _table_counts(source)
        finally:
            source.close()
        check = sqlite3.connect(str(temporary))
        try:
            intact = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            actual = _table_counts(check)
        finally:
            check.close()
        if not intact or actual != expected:
            raise sqlite3.DatabaseError("the copy does not match the original")
        _fsync_file(temporary)
        for suffix in _INDEX_SIDECARS:
            with contextlib.suppress(OSError):
                Path(str(new) + suffix).unlink()
        os.replace(temporary, new)
    except (OSError, sqlite3.Error) as exc:
        with contextlib.suppress(OSError):
            temporary.unlink()
        log(f"Could not move {old.name} from {old.parent} to {new.parent}: {exc}. "
            "The original was left where it is.")
        return False
    _remove_with_sidecars(old)
    return True


def _move_file(old: Path, new: Path, log: Callable[[str], None]) -> bool:
    if not old.exists() or new.exists():
        return False
    temporary = new.with_name("." + new.name + ".migrating")
    try:
        with open(old, "rb") as source, open(temporary, "wb") as destination:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        if temporary.stat().st_size != old.stat().st_size:
            raise OSError("the copy is not the same size as the original")
        os.replace(temporary, new)
    except OSError as exc:
        with contextlib.suppress(OSError):
            temporary.unlink()
        log(f"Could not move {old.name} from {old.parent} to {new.parent}: {exc}. "
            "The original was left where it is.")
        return False
    with contextlib.suppress(OSError):
        old.unlink()
    return True


def migrate_legacy_state(
    project_root: Path = PROJECT_ROOT,
    environ: Optional[Mapping[str, str]] = None,
    target: Optional[Path] = None,
    log: Callable[[str], None] = _warn,
) -> List[str]:
    """Move the index and settings from beside the program into the per-user folder.

    Returns the file names moved. Safe to call on every start: when there is
    nothing to move it touches nothing.
    """
    env = os.environ if environ is None else environ
    if str(env.get(STATE_DIR_ENV, "")).strip():
        return []
    project_root = Path(project_root)
    legacy_index = project_root / INDEX_FILENAME
    legacy_settings = project_root / "data" / SETTINGS_FILENAME
    if not legacy_index.exists() and not legacy_settings.exists():
        return []
    folder = state_dir(env) if target is None else Path(target)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with _migration_lock(folder):
            moved: List[str] = []
            if _move_index(legacy_index, folder / INDEX_FILENAME, log):
                moved.append(INDEX_FILENAME)
            if _move_file(legacy_settings, folder / SETTINGS_FILENAME, log):
                moved.append(SETTINGS_FILENAME)
    except OSError as exc:
        log(f"Could not move saved state to {folder}: {exc}. Saved files were left where they are.")
        return []
    if moved:
        with contextlib.suppress(OSError):
            legacy_settings.parent.rmdir()
        log(f"Moved saved state ({', '.join(moved)}) from {project_root} to {folder}")
    return moved


__all__ = [
    "INDEX_FILENAME", "SETTINGS_FILENAME", "STATE_APP_DIRNAME", "STATE_DIR_ENV",
    "STATE_VENDOR_DIRNAME", "index_path", "migrate_legacy_state", "settings_path",
    "state_dir",
]
