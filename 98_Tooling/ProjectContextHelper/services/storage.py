"""
File: services/storage.py

Purpose
-------
Centralize preferences, last-used export settings, custom profiles, and export history
  persistence for Project Context Helper in Brisart Research Archive.

Implemented responsibilities:
- application_dir: Return the PCH_STATE_DIR environment folder when set; otherwise resolve
  persisted state beside sys.executable for frozen mode or two directories above storage.py for
  source mode.
- state_lock: Context manager serializing state changes: an in-process reentrant lock plus a
  .pch-state.lock file created with O_EXCL; waits up to 5 seconds and removes a lock file older
  than 30 seconds as stale.
- _atomic_write: Create the parent, write a uniquely named .pch-*.tmp sibling (tempfile.mkstemp),
  flush/fsync, replace the destination, and remove the temp file before reraising failures.
- app_settings_path: Return app_settings.json beneath an explicit app_dir or the resolved
  application directory.
- load_preferences: Return defaults for missing/unreadable/invalid-JSON/non-object preferences;
  otherwise accept only real JSON booleans for the three keys, using defaults for anything else.
- save_preferences: Serialize AppPreferences to JSON via _atomic_write and suppress write
  exceptions.
- last_settings_path: Return last_export_settings.json beneath an explicit app_dir or the
  application directory.
- save_last_settings: Serialize ScanSettings to the last-settings file using the atomic writer;
  suppress failures because settings memory is a convenience feature.
- load_last_settings: Return None for missing, unreadable, unparseable, or unconvertible saved
  settings; otherwise reconstruct ScanSettings.
- clear_last_settings: Attempt to unlink the last-settings file when present; suppress
  filesystem failures.
- profiles_path: Return custom_profiles.json beneath the chosen application directory.
- is_reserved_name: Trim/lowercase the requested name and check it against the two built-in
  profile names.
- _load_all_profiles: Read the custom-profile JSON object and its profiles dictionary. Readers get
  an empty dictionary for missing/unreadable/invalid data; writers (strict=True) get ValueError
  for an existing unreadable/invalid file so it is never overwritten.
- _save_all_profiles: Wrap the profile mapping under a profiles key and atomically serialize it;
  errors propagate.
- list_profiles: Return sorted keys from the saved profile mapping.
- profile_exists: Trim the name and test exact case-sensitive membership in saved profiles.
- save_profile: Trim the name, reject empty/reserved names, then under state_lock merge serialized
  settings into the existing mapping and atomically write it; an existing exact name is
  overwritten.
- load_profile: Trim and look up the name, then reconstruct ScanSettings; return None for
  absent/unconvertible entries.
- delete_profile: Under state_lock, trim and remove an exact saved name, write the remaining
  mapping, and return True; return False if absent.
- history_path: Return build_history.json beneath the chosen application directory.
- load_history: Read JSON history; instantiate HistoryEntry for each object item, skipping
  non-object and constructor-TypeError records; missing/unreadable/invalid JSON or a non-list
  container returns an empty list.
- save_history: Serialize HistoryEntry objects as a JSON list through _atomic_write; errors
  propagate.
- append_history_entry: Under state_lock, load history, prepend the new entry, retain at most
  MAX_HISTORY_ENTRIES, persist, and return the retained list.
- recent_entries: Return the first limit entries of loaded history using list slicing.
- clear_history: Under state_lock, persist an empty history list without deleting any export
  outputs.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: APP_SETTINGS_FILENAME, BUILD_HISTORY_FILENAME, CUSTOM_PROFILES_FILENAME,
  INTERNAL_NAME_PREFIX, LAST_SETTINGS_FILENAME, MAX_HISTORY_ENTRIES, PROFILE_ARCHIVE,
  PROFILE_STANDARD.
- core.models: ScanSettings.

Consumers in the supplied source:
- cli/cli.py imports this module through services.
- core/builder.py imports HistoryEntry, append_history_entry.
- gui/about_tab.py imports HistoryEntry, application_dir, clear_history, recent_entries.
- gui/builders.py imports AppPreferences, load_preferences, save_preferences,
  load_last_settings, save_last_settings.
- gui/profiles_section.py imports this module through services.
- services/updater.py imports application_dir.

Settings / parameters
---------------------
Source data lives beside run.py; frozen data lives beside the executable; the PCH_STATE_DIR
  environment variable overrides both (used by the test suite; also usable for a portable or
  shared state folder). Stores four JSON files. History is capped at 50 entries;
  recent_entries defaults to 10. state_lock waits up to LOCK_TIMEOUT_SECONDS (5) and treats a
  lock file older than STALE_LOCK_SECONDS (30) as abandoned.

Function signatures (nested callbacks are scoped to their enclosing function):
- application_dir() -> Path
- state_lock(app_dir: Path | None=None) -> Iterator[None]
- _atomic_write(path: Path, text: str) -> None
- app_settings_path(app_dir: Path | None=None) -> Path
- load_preferences(app_dir: Path | None=None) -> AppPreferences
- save_preferences(preferences: AppPreferences, app_dir: Path | None=None) -> None
- last_settings_path(app_dir: Path | None=None) -> Path
- save_last_settings(settings: ScanSettings, app_dir: Path | None=None) -> None
- load_last_settings(app_dir: Path | None=None) -> ScanSettings | None
- clear_last_settings(app_dir: Path | None=None) -> None
- profiles_path(app_dir: Path | None=None) -> Path
- is_reserved_name(name: str) -> bool
- _load_all_profiles(app_dir: Path | None=None, strict: bool=False) -> dict[str, dict]
- _save_all_profiles(profiles: dict[str, dict], app_dir: Path | None=None) -> None
- list_profiles(app_dir: Path | None=None) -> list[str]
- profile_exists(name: str, app_dir: Path | None=None) -> bool
- save_profile(name: str, settings: ScanSettings, app_dir: Path | None=None) -> None
- load_profile(name: str, app_dir: Path | None=None) -> ScanSettings | None
- delete_profile(name: str, app_dir: Path | None=None) -> bool
- history_path(app_dir: Path | None=None) -> Path
- load_history(app_dir: Path | None=None) -> list[HistoryEntry]
- save_history(entries: list[HistoryEntry], app_dir: Path | None=None) -> None
- append_history_entry(entry: HistoryEntry, app_dir: Path | None=None) -> list[HistoryEntry]
- recent_entries(limit: int=10, app_dir: Path | None=None) -> list[HistoryEntry]
- clear_history(app_dir: Path | None=None) -> None

Module constants and expressions:
- STATE_ENV_VAR = 'PCH_STATE_DIR'
- LOCK_FILENAME = INTERNAL_NAME_PREFIX + 'state.lock'
- LOCK_TIMEOUT_SECONDS = 5.0
- STALE_LOCK_SECONDS = 30.0
- RESERVED_PROFILE_NAMES = {PROFILE_STANDARD, PROFILE_ARCHIVE}

AppPreferences record fields:
- open_after_build: bool = False
- check_updates_startup: bool = False
- auto_install_updates: bool = False

HistoryEntry record fields:
- created: str (required constructor field)
- root: str (required constructor field)
- profile: str (required constructor field)
- export_dir: str (required constructor field)
- included_count: int (required constructor field)
- skipped_count: int (required constructor field)
- total_included_bytes: int (required constructor field)
- git_branch: str = ''
- git_commit_short: str = ''

Edge cases
----------
Atomic-write helper flushes/fsyncs a uniquely named temporary file before os.replace and
  removes it on caught failures. Temp and lock files start with .pch-, which the scanner skips.
  Convenience loaders/writers (preferences, last-used settings) still fall back or suppress
  errors; custom-profile and history writes propagate errors.

v4.0.0 fixes: a JSON list/null in app_settings.json returns defaults instead of raising, and a
  string such as "false" no longer counts as True. A corrupted custom_profiles.json is reported
  (ValueError) instead of being silently overwritten with only the newly saved profile.

Known limitations
-----------------
Persistence is per file, not a multi-file transaction. Hard termination can leave a .pch-*.tmp
  file or a lock file; a lock file is treated as stale after 30 seconds. File locking is
  advisory (it only coordinates processes running this module) and is untested on network
  filesystems. No automatic recovery of a malformed state file is implemented; convenience
  loaders still fall back silently.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from tempfile import TemporaryDirectory
    from core.constants import settings_for_profile
    from services import storage

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
from typing import Iterator
import json
import os
import sys
import tempfile
import threading
import time

from core.constants import (
    APP_SETTINGS_FILENAME,
    BUILD_HISTORY_FILENAME,
    CUSTOM_PROFILES_FILENAME,
    INTERNAL_NAME_PREFIX,
    LAST_SETTINGS_FILENAME,
    MAX_HISTORY_ENTRIES,
    PROFILE_ARCHIVE,
    PROFILE_STANDARD,
)
from core.models import ScanSettings


# ============================================================
# 1. Shared application_dir() / state_lock() / _atomic_write() helpers
# ============================================================
STATE_ENV_VAR = "PCH_STATE_DIR"
LOCK_FILENAME = f"{INTERNAL_NAME_PREFIX}state.lock"
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 30.0
_THREAD_LOCK = threading.RLock()


def application_dir() -> Path:
    """
    Return the application's root folder (the one containing run.py),
    not the services/ folder this module itself lives in.

    v4.0.0: a PCH_STATE_DIR environment variable, when set, takes
    precedence, so tests (and portable setups) never touch the real
    state files beside run.py.
    """
    override = os.environ.get(STATE_ENV_VAR)
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@contextmanager
def state_lock(app_dir: Path | None = None) -> Iterator[None]:
    """
    v4.0.0: serialize read-modify-write updates (profiles, history).
    v3.1.4 had no locking, so two saves at the same moment (two GUI
    windows, a GUI build plus a CLI build, or the new background build
    worker plus a profile save) could each load the old file and the
    second write silently discarded the first one's change.

    The in-process RLock covers threads; the O_EXCL lock file covers
    separate processes. A lock file left by a killed process is removed
    once it is older than STALE_LOCK_SECONDS.
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
    Write `text` to `path` atomically: write to a sibling temp file,
    flush and fsync it, then swap it into place with os.replace()
    (atomic on both POSIX and Windows), so a reader can never observe
    a partially-written file.

    Bugfix (v3.1.2): if anything went wrong between creating the temp
    file and the os.replace() call succeeding -- disk full partway
    through the write, a permissions error, an interrupted fsync, or
    any other exception -- the temp file was previously left behind
    on disk forever, with no cleanup attempted. This is more than
    just clutter: this application_dir() folder is the same folder
    this very tool is commonly pointed at to export itself (as it
    plainly is by whoever is running it, given the actual exports
    already sitting in PROJECT_CONTEXT_EXPORTS/ next to this file) --
    so a stray ".custom_profiles.json.tmp12345"-style leftover would
    not match any exact entry in DEFAULT_EXCLUDE_FILES (which only
    excludes exact, static filenames) and would silently appear in
    a subsequent export's Skipped File Details table, or worse, get
    swept in as an actual included source file if its dynamic name
    happens to end in a configured extension. The write is now
    wrapped so that any failure attempts to remove its own temp file
    before the original exception is re-raised, leaving no debris
    behind on a failed write the way a fully successful or a
    hard-killed (unrecoverable) write both already effectively do.

    v4.0.0: the temp name was ".<name>.tmp<PID>", so two threads in the
    same process (now possible with background builds) could write the
    same temp file at once. Temp files are now created with
    tempfile.mkstemp (unique per call) and use the .pch- prefix, which
    the scanner always skips, so a leftover can no longer end up in an
    export.
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


# ============================================================
# 2. App Preferences (app_settings.json)
# ============================================================
@dataclass(slots=True)
class AppPreferences:
    open_after_build: bool = False
    check_updates_startup: bool = False
    auto_install_updates: bool = False


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
        # v4.0.0: only real JSON booleans count. v3.1.4 used bool(), so a
        # hand-edited "false" string switched the preference ON.
        value = raw.get(key, default)
        return value if isinstance(value, bool) else default

    return AppPreferences(
        open_after_build=flag("open_after_build", defaults.open_after_build),
        check_updates_startup=flag("check_updates_startup", defaults.check_updates_startup),
        auto_install_updates=flag("auto_install_updates", defaults.auto_install_updates),
    )


def save_preferences(preferences: AppPreferences, app_dir: Path | None = None) -> None:
    path = app_settings_path(app_dir)
    try:
        _atomic_write(path, json.dumps(asdict(preferences), indent=2))
    except Exception:
        pass


# ============================================================
# 3. Last Used Settings (last_export_settings.json)
# ============================================================
def last_settings_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / LAST_SETTINGS_FILENAME


def save_last_settings(settings: ScanSettings, app_dir: Path | None = None) -> None:
    """
    Any failure here is swallowed rather than raised -- this is a
    convenience feature and must never cause an otherwise-successful
    build to fail or surface an error dialog to the user.
    """
    try:
        path = last_settings_path(app_dir)
        _atomic_write(path, json.dumps(settings.to_jsonable(), indent=2))
    except Exception:
        pass


def load_last_settings(app_dir: Path | None = None) -> ScanSettings | None:
    """
    Returns None when no file exists yet, or when it can't be parsed
    into a valid ScanSettings -- callers should fall back to the
    selected profile's normal defaults rather than raising.
    """
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


def clear_last_settings(app_dir: Path | None = None) -> None:
    path = last_settings_path(app_dir)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


# ============================================================
# 4. Custom Profiles (custom_profiles.json)
# ============================================================
RESERVED_PROFILE_NAMES = {PROFILE_STANDARD, PROFILE_ARCHIVE}


def profiles_path(app_dir: Path | None = None) -> Path:
    return (app_dir or application_dir()) / CUSTOM_PROFILES_FILENAME


def is_reserved_name(name: str) -> bool:
    return name.strip().lower() in RESERVED_PROFILE_NAMES


def _load_all_profiles(app_dir: Path | None = None, strict: bool = False) -> dict[str, dict]:
    """
    v4.0.0: strict=True is used by save/delete. In v3.1.4 an unreadable or
    malformed custom_profiles.json loaded as {}, and the next save then
    overwrote the file with only the new profile -- every other saved
    profile was lost permanently with no warning. Writers now refuse to
    touch a file they cannot read.
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


def profile_exists(name: str, app_dir: Path | None = None) -> bool:
    return name.strip() in _load_all_profiles(app_dir)


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


# ============================================================
# 5. Build History (build_history.json)
# ============================================================
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

