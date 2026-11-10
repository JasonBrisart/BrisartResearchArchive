"""
File: storage.py

Purpose
-------
Own everything Project Context Helper remembers between runs: the open-folder-after-build
  preference (app_settings.json), last-used export settings (last_export_settings.json), named
  custom profiles (custom_profiles.json), and export history (build_history.json), including
  recording each finished export. All four files share one folder, one atomic writer, and one
  lock.

Communication / relationships
-----------------------------
Imports app (state file names, .pch- prefix) and export/settings.py (ScanSettings,
  VALID_PROFILES for reserved names). BuildResult from export/pipeline.py is imported for type
  annotations only, so loading storage never loads the scanner, renderer, or pipeline. Imported by cli.py
  (profiles, last settings, record_export), gui/state.py (preferences, last settings),
  gui/build_tab.py (last settings, record_export), gui/extras_tab.py (profiles), and
  gui/about_tab.py (history).

Settings / parameters
---------------------
Files live in application_dir(): the PCH_STATE_DIR environment variable when set, otherwise
  beside the executable (frozen) or beside run.py (source). Every function also accepts an
  explicit app_dir. History keeps the newest MAX_HISTORY_ENTRIES (50). state_lock waits up to
  LOCK_TIMEOUT_SECONDS (5) and clears a lock older than STALE_LOCK_SECONDS (30).

Edge cases
----------
Convenience paths never raise: unreadable or malformed preferences and last-used settings
  load as defaults/None, and failed saves of them are ignored, as is a failed record_export.
  Preferences accept only real JSON booleans, so the string "false" does not count as on;
  keys written by older versions (check_updates_startup, auto_install_updates) are ignored
  and dropped on the next save. Profile and history writes raise (ValueError, OSError, or
  TimeoutError when the folder is busy), and a corrupted custom_profiles.json is reported and
  left untouched. Profile names are trimmed and case-sensitive; standard and archive are
  reserved in any case. History items with the wrong shape are skipped.

Known limitations
-----------------
Each file is replaced atomically, but there is no transaction across files. Locking is
  advisory between copies of this program and is untested on network filesystems. A hard
  kill can leave a .pch-*.tmp or lock file behind (the scanner skips both). Clearing history
  never deletes export folders.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from tempfile import TemporaryDirectory
    from export.settings import settings_for_profile
    import storage

    with TemporaryDirectory() as directory:
        app_dir = Path(directory)
        storage.save_profile("Review", settings_for_profile("archive"), app_dir)
        assert storage.list_profiles(app_dir) == ["Review"]
        assert storage.load_profile(" Review ", app_dir).profile == "archive"
        assert storage.delete_profile("Review", app_dir) is True
"""

from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator
import json
import os
import sys
import tempfile
import threading
import time

from app import (
    APP_SETTINGS_FILENAME,
    BUILD_HISTORY_FILENAME,
    CUSTOM_PROFILES_FILENAME,
    INTERNAL_NAME_PREFIX,
    LAST_SETTINGS_FILENAME,
)
from export.settings import VALID_PROFILES, ScanSettings

if TYPE_CHECKING:
    from export.pipeline import BuildResult


# ---- Shared folder, lock, and atomic write
STATE_ENV_VAR = "PCH_STATE_DIR"
LOCK_FILENAME = f"{INTERNAL_NAME_PREFIX}state.lock"
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 30.0
MAX_HISTORY_ENTRIES = 50
_THREAD_LOCK = threading.RLock()


def application_dir() -> Path:
    """
    PCH_STATE_DIR wins (tests use it so real state is never touched); otherwise
    beside the executable when frozen, or beside this file (and run.py) from source.
    """
    override = os.environ.get(STATE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


@contextmanager
def state_lock(app_dir: Path | None = None) -> Iterator[None]:
    """
    Serialize read-modify-write updates of profiles and history across threads
    (RLock) and processes (an O_EXCL lock file), so two simultaneous saves cannot
    silently drop one another's change. A lock file older than
    STALE_LOCK_SECONDS is treated as left behind by a killed process.
    """
    directory = app_dir or application_dir()
    with _THREAD_LOCK:
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / LOCK_FILENAME
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    if time.time() - lock_path.stat().st_mtime > STALE_LOCK_SECONDS:
                        lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Settings folder is busy ({lock_path} is held by another Project "
                        "Context Helper process). Try again in a moment."
                    )
                time.sleep(0.02)
        try:
            os.write(fd, str(os.getpid()).encode("ascii"))
            yield
        finally:
            os.close(fd)
            try:
                lock_path.unlink()
            except OSError:
                pass


def _atomic_write(path: Path, text: str) -> None:
    """
    Write through a unique .pch-*.tmp sibling, fsync, then os.replace, so a reader
    never sees a half-written file and a failed write leaves no temp file behind.
    The .pch- prefix keeps any leftover out of exports.
    """
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{INTERNAL_NAME_PREFIX}{path.name}.", suffix=".tmp", dir=directory)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        raise


# ---- App Preferences (app_settings.json)
@dataclass(slots=True)
class AppPreferences:
    open_after_build: bool = False


def app_settings_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / APP_SETTINGS_FILENAME


def load_preferences(app_dir: Path | None = None) -> AppPreferences:
    path = app_settings_path(app_dir)
    if not path.exists():
        return AppPreferences()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return AppPreferences()
    defaults = AppPreferences()
    if not isinstance(raw, dict):
        return defaults

    def flag(key: str, default: bool) -> bool:
        # Only real JSON booleans count; bool("false") would be True.
        value = raw.get(key, default)
        return value if isinstance(value, bool) else default

    return AppPreferences(
        open_after_build=flag("open_after_build", defaults.open_after_build),
    )


def save_preferences(preferences: AppPreferences, app_dir: Path | None = None) -> None:
    path = app_settings_path(app_dir)
    try:
        _atomic_write(path, json.dumps(asdict(preferences), indent=2))
    except Exception:
        pass


# ---- Last Used Settings (last_export_settings.json)
def last_settings_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / LAST_SETTINGS_FILENAME


def save_last_settings(settings: ScanSettings, app_dir: Path | None = None) -> None:
    try:
        path = last_settings_path(app_dir)
        _atomic_write(path, json.dumps(settings.to_jsonable(), indent=2))
    except Exception:
        pass


def load_last_settings(app_dir: Path | None = None) -> ScanSettings | None:
    path = last_settings_path(app_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    try:
        return ScanSettings.from_jsonable(raw)
    except Exception:
        return None


# ---- Custom Profiles (custom_profiles.json)
def profiles_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / CUSTOM_PROFILES_FILENAME


def is_reserved_name(name: str) -> bool:
    return name.strip().lower() in VALID_PROFILES


def _load_all_profiles(app_dir: Path | None = None, strict: bool = False) -> dict[str, dict]:
    """
    Readers get {} for a missing or unreadable file. Writers pass strict=True and
    get ValueError instead, so an unreadable file is never overwritten with only
    the newly saved profile.
    """
    path = profiles_path(app_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        if strict:
            raise ValueError(f"{path.name} could not be read ({exc}); it was not modified. Repair or move it, then try again.") from exc
        return {}
    profiles = raw.get("profiles") if isinstance(raw, dict) else None
    if not isinstance(profiles, dict):
        if strict:
            raise ValueError(f"{path.name} does not contain a profiles object; it was not modified. Repair or move it, then try again.")
        return {}
    return profiles


def _save_all_profiles(profiles: dict[str, dict], app_dir: Path | None = None) -> None:
    path = profiles_path(app_dir)
    _atomic_write(path, json.dumps({"profiles": profiles}, indent=2))


def list_profiles(app_dir: Path | None = None) -> list[str]:
    return sorted(_load_all_profiles(app_dir).keys())




def save_profile(name: str, settings: ScanSettings, app_dir: Path | None = None) -> None:
    name = name.strip()
    if not name:
        raise ValueError("Profile name cannot be empty.")
    if is_reserved_name(name):
        raise ValueError(f"'{name}' is a built-in profile name and cannot be used for a custom profile.")
    with state_lock(app_dir):
        profiles = _load_all_profiles(app_dir, strict=True)
        profiles[name] = settings.to_jsonable()
        _save_all_profiles(profiles, app_dir)


def load_profile(name: str, app_dir: Path | None = None) -> ScanSettings | None:
    raw = _load_all_profiles(app_dir).get(name.strip())
    if raw is None:
        return None
    try:
        return ScanSettings.from_jsonable(raw)
    except Exception:
        return None


def delete_profile(name: str, app_dir: Path | None = None) -> bool:
    name = name.strip()
    with state_lock(app_dir):
        profiles = _load_all_profiles(app_dir, strict=True)
        if name not in profiles:
            return False
        del profiles[name]
        _save_all_profiles(profiles, app_dir)
    return True


# ---- Build History (build_history.json)
@dataclass(frozen=True, slots=True)
class HistoryEntry:
    created: str
    root: str
    profile: str
    export_dir: str
    included_count: int
    skipped_count: int
    total_included_bytes: int
    git_branch: str = ""
    git_commit_short: str = ""


def history_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / BUILD_HISTORY_FILENAME


def load_history(app_dir: Path | None = None) -> list[HistoryEntry]:
    path = history_path(app_dir)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    entries: list[HistoryEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(HistoryEntry(**item))
        except TypeError:
            continue
    return entries


def save_history(entries: list[HistoryEntry], app_dir: Path | None = None) -> None:
    path = history_path(app_dir)
    _atomic_write(path, json.dumps([asdict(e) for e in entries], indent=2))


def append_history_entry(entry: HistoryEntry, app_dir: Path | None = None) -> list[HistoryEntry]:
    with state_lock(app_dir):
        entries = load_history(app_dir)
        entries.insert(0, entry)
        entries = entries[:MAX_HISTORY_ENTRIES]
        save_history(entries, app_dir)
    return entries


def recent_entries(limit: int = 10, app_dir: Path | None = None) -> list[HistoryEntry]:
    return load_history(app_dir)[:limit]


def clear_history(app_dir: Path | None = None) -> None:
    with state_lock(app_dir):
        save_history([], app_dir)


def record_export(result: BuildResult, settings: ScanSettings, app_dir: Path | None = None) -> None:
    # History is a convenience list; a full disk or busy lock must never fail a finished export.
    try:
        append_history_entry(HistoryEntry(
            created=result.created, root=str(result.root), profile=settings.profile,
            export_dir=str(result.export_dir), included_count=result.included_count,
            skipped_count=result.skipped_count, total_included_bytes=result.total_included_bytes,
            git_branch=result.git_branch or "", git_commit_short=result.git_commit_short or "",
        ), app_dir)
    except Exception:
        pass
