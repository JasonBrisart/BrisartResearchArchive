"""
Storage
Single consolidated module for every piece of persisted application
state that is not part of a build's own output files.

Sections in this file, each self-contained but sharing the same
application_dir() helper and the same atomic-write helper:
  1. Shared application_dir() / _atomic_write() helpers
  2. App Preferences      (app_settings.json)
  3. Last Used Settings   (last_export_settings.json) -- always-on GUI memory
  4. Custom Profiles      (custom_profiles.json)       -- named, explicit Save/Load/Delete
  5. Build History        (build_history.json)         -- Recent Exports list

No external dependencies.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import sys

from core.constants import (
    APP_SETTINGS_FILENAME,
    BUILD_HISTORY_FILENAME,
    CUSTOM_PROFILES_FILENAME,
    LAST_SETTINGS_FILENAME,
    MAX_HISTORY_ENTRIES,
    PROFILE_ARCHIVE,
    PROFILE_STANDARD,
)
from core.models import ScanSettings


# ============================================================
# 1. Shared application_dir() / _atomic_write() helpers
# ============================================================
def application_dir() -> Path:
    """
    Return the application's root folder (the one containing run.py),
    not the services/ folder this module itself lives in.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


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
    """
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / f".{path.name}.tmp{os.getpid()}"
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
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
    return AppPreferences(
        open_after_build=bool(raw.get("open_after_build", defaults.open_after_build)),
        check_updates_startup=bool(raw.get("check_updates_startup", defaults.check_updates_startup)),
        auto_install_updates=bool(raw.get("auto_install_updates", defaults.auto_install_updates)),
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


def _load_all_profiles(app_dir: Path | None = None) -> dict[str, dict]:
    path = profiles_path(app_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    profiles = raw.get("profiles")
    return profiles if isinstance(profiles, dict) else {}


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
    profiles = _load_all_profiles(app_dir)
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
    profiles = _load_all_profiles(app_dir)
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
    entries: list[HistoryEntry] = []
    for item in raw:
        try:
            entries.append(HistoryEntry(**item))
        except TypeError:
            continue
    return entries


def save_history(entries: list[HistoryEntry], app_dir: Path | None = None) -> None:
    path = history_path(app_dir)
    _atomic_write(path, json.dumps([asdict(e) for e in entries], indent=2))


def append_history_entry(entry: HistoryEntry, app_dir: Path | None = None) -> list[HistoryEntry]:
    entries = load_history(app_dir)
    entries.insert(0, entry)
    entries = entries[:MAX_HISTORY_ENTRIES]
    save_history(entries, app_dir)
    return entries


def recent_entries(limit: int = 10, app_dir: Path | None = None) -> list[HistoryEntry]:
    return load_history(app_dir)[:limit]


def clear_history(app_dir: Path | None = None) -> None:
    save_history([], app_dir)
