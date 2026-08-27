"""
config/runtime.py
Persistent application settings.
Kept from the Archive branch essentially unchanged - this module was
already solid: normalization, path validation, atomic JSON storage,
recovery, and persistence, all pure standard library.

WINDOW SIZE DEFAULTS, specifically:
DEFAULT_SETTINGS["window_width"/"window_height"] is 800x600, chosen so
the app opens at a reasonable, non-bloated size rather than filling a
large portion of the screen by default. MIN_WINDOW_WIDTH/
MIN_WINDOW_HEIGHT were lowered to match (800x600) -- previously they
were 1060/700, which is HIGHER than the new default, meaning
normalize_int() would have silently clamped an 800x600 default (or any
saved 800x600 setting) straight back up to 1060x700 the moment it
passed through here. Both this file's MIN_WINDOW_WIDTH/HEIGHT and
gui/main_window.py's hardcoded self.minsize() call (a second,
independent floor enforced directly by Tk) must be kept in sync with
each other, or a smaller default gets silently overridden by whichever
one of the two still has the old, larger floor.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path, PureWindowsPath
from typing import Any

# ============================================================
# Constants
# ============================================================

APP_NAME = "Brisart Research Archive"
SETTINGS_VERSION = 1

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_FILE = APP_DIR / "user_settings.json"
SETTINGS_TEMP_FILE = APP_DIR / "user_settings.json.tmp"
SETTINGS_BACKUP_FILE = APP_DIR / "user_settings.json.bak"
LEGACY_SETTINGS_FILE = Path(__file__).resolve().parent / "user_settings.json"

DEFAULT_SETTINGS = {
    "settings_version": SETTINGS_VERSION,
    "default_framework": "TFL",
    "theme": "dark",
    "output_folder": "outputs",
    "enable_update_checks": True,
    "notify_on_update": True,
    # Governs BOTH the automatic startup check and the manual "Check
    # Updates" button: when True, a verified newer release is installed
    # automatically rather than only downloaded. Defaults to True since
    # this app is built first for daily use by its own author -- flip
    # to False in Settings if you'd rather always confirm installs
    # yourself via the Yes/No prompt.
    "auto_install_updates": True,
    # Deliberately modest (not the previous 1220x780) so the window
    # opens at a reasonable size rather than dominating the screen by
    # default. See the module docstring for why MIN_WINDOW_WIDTH/HEIGHT
    # below had to move together with this.
    "window_width": 800,
    "window_height": 600,
}

ALLOWED_THEMES = {"dark"}
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
MAX_WINDOW_WIDTH = 7680
MAX_WINDOW_HEIGHT = 4320

INVALID_WINDOWS_FILENAME_CHARS = {"<", ">", '"', "|", "?", "*"}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

# ============================================================
# Normalization
# ============================================================

def normalize_text(value: Any, default: str) -> str:
    if value is None:
        return str(default)
    text = str(value).strip()
    return text or str(default)


def normalize_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes", "y", "on", "enabled"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "disabled", ""}:
            return False
    return bool(default)


def normalize_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)
    return max(minimum, min(normalized, maximum))


def normalize_theme(value: Any) -> str:
    theme = normalize_text(value, DEFAULT_SETTINGS["theme"]).casefold()
    if theme not in ALLOWED_THEMES:
        return DEFAULT_SETTINGS["theme"]
    return theme


def normalize_framework_id(value: Any) -> str:
    framework_id = normalize_text(value, DEFAULT_SETTINGS["default_framework"])
    cleaned = "".join(
        character for character in framework_id
        if character.isalnum() or character in {"-", "_"}
    )
    return cleaned.upper() or DEFAULT_SETTINGS["default_framework"]


# ============================================================
# Path validation
# ============================================================

def contains_control_character(text: str) -> bool:
    return any(ord(character) < 32 for character in str(text))


def windows_path_parts(text: str) -> tuple[str, ...]:
    try:
        return PureWindowsPath(text).parts
    except (TypeError, ValueError, OSError):
        return ()


def is_windows_drive_part(part: str) -> bool:
    normalized = str(part).strip()
    return len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha()


def invalid_path_part(part: str, *, is_first_part: bool) -> bool:
    if part is None:
        return True
    text = str(part)
    if is_first_part and is_windows_drive_part(text):
        return False
    if text in {"\\", "/"}:
        return False
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {".", ".."}:
        return False
    if stripped.endswith("."):
        return True
    if stripped.endswith(" "):
        return True
    if ":" in stripped:
        return True
    name_without_extension = stripped.split(".", 1)[0].upper()
    if name_without_extension in WINDOWS_RESERVED_NAMES:
        return True
    return any(character in INVALID_WINDOWS_FILENAME_CHARS for character in stripped)


def is_safe_output_folder_text(text: str) -> bool:
    if text is None:
        return False
    text = str(text).strip()
    if not text:
        return False
    if "\x00" in text:
        return False
    if contains_control_character(text):
        return False
    parts = windows_path_parts(text)
    if not parts:
        return False
    for index, part in enumerate(parts):
        if invalid_path_part(part, is_first_part=(index == 0)):
            return False
    return True


def normalize_output_folder(value: Any) -> str:
    text = normalize_text(value, DEFAULT_SETTINGS["output_folder"])
    if not is_safe_output_folder_text(text):
        return DEFAULT_SETTINGS["output_folder"]
    return text


# ============================================================
# Settings normalization + output paths
# ============================================================

def normalize_settings(data: Any) -> dict:
    settings = dict(data) if isinstance(data, dict) else {}
    settings["settings_version"] = SETTINGS_VERSION
    settings["default_framework"] = normalize_framework_id(settings.get("default_framework"))
    settings["theme"] = normalize_theme(settings.get("theme"))
    settings["output_folder"] = normalize_output_folder(settings.get("output_folder"))
    settings["enable_update_checks"] = normalize_bool(
        settings.get("enable_update_checks"), DEFAULT_SETTINGS["enable_update_checks"]
    )
    settings["notify_on_update"] = normalize_bool(
        settings.get("notify_on_update"), DEFAULT_SETTINGS["notify_on_update"]
    )
    settings["auto_install_updates"] = normalize_bool(
        settings.get("auto_install_updates"), DEFAULT_SETTINGS["auto_install_updates"]
    )
    settings["window_width"] = normalize_int(
        settings.get("window_width"), DEFAULT_SETTINGS["window_width"], MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH
    )
    settings["window_height"] = normalize_int(
        settings.get("window_height"), DEFAULT_SETTINGS["window_height"], MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT
    )
    return settings


def get_app_dir() -> Path:
    return APP_DIR


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def get_default_output_dir() -> Path:
    return APP_DIR / DEFAULT_SETTINGS["output_folder"]


def resolve_output_folder(value: str | Path | None = None) -> Path:
    if value is None:
        return get_default_output_dir()
    text = str(value).strip()
    if not text:
        return get_default_output_dir()
    if not is_safe_output_folder_text(text):
        return get_default_output_dir()
    expanded = os.path.expandvars(os.path.expanduser(text))
    path = Path(expanded)
    if path.is_absolute():
        return path
    return APP_DIR / path


def get_output_folder(settings: dict | None = None) -> Path:
    normalized = load_settings() if settings is None else normalize_settings(settings)
    return resolve_output_folder(normalized["output_folder"])


def sanitize_framework_id(framework_id: Any) -> str:
    normalized_id = normalize_text(framework_id, "UNKNOWN")
    safe_id = "".join(
        character if (character.isalnum() or character in {"-", "_"}) else "_"
        for character in normalized_id
    )
    safe_id = safe_id.strip("._")
    return safe_id or "UNKNOWN"


def get_framework_output_dir(framework_id: str, settings: dict | None = None) -> Path:
    safe_id = sanitize_framework_id(framework_id)
    output_dir = get_output_folder(settings) / safe_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# ============================================================
# JSON storage
# ============================================================

def read_json_file(path: Path) -> Any:
    path = Path(path)
    with open(path, "r", encoding="utf-8-sig") as file:
        return json.load(file)


def write_json_file(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, sort_keys=True)
        file.write("\n")
        file.flush()
        try:
            os.fsync(file.fileno())
        except OSError:
            pass


def settings_file_is_valid(path: Path) -> bool:
    path = Path(path)
    if not path.is_file():
        return False
    try:
        data = read_json_file(path)
        if not isinstance(data, dict):
            return False
        normalize_settings(data)
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return False


# ============================================================
# Recovery
# ============================================================

def cleanup_stale_temp_settings() -> None:
    if not SETTINGS_TEMP_FILE.exists():
        return
    if not SETTINGS_FILE.exists() and settings_file_is_valid(SETTINGS_TEMP_FILE):
        try:
            SETTINGS_TEMP_FILE.replace(SETTINGS_FILE)
            return
        except OSError:
            pass
    try:
        SETTINGS_TEMP_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def migrate_legacy_settings() -> bool:
    if SETTINGS_FILE.exists():
        return True
    if not LEGACY_SETTINGS_FILE.exists():
        return True
    if not settings_file_is_valid(LEGACY_SETTINGS_FILE):
        print("Legacy settings were not migrated because the file is invalid.")
        return False
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LEGACY_SETTINGS_FILE, SETTINGS_FILE)
        return True
    except OSError as exc:
        print(f"Could not migrate legacy settings: {exc}")
        return False


def backup_invalid_settings_file() -> Path | None:
    if not SETTINGS_FILE.exists():
        return None
    candidate = APP_DIR / "user_settings.invalid.json"
    counter = 1
    while candidate.exists():
        candidate = APP_DIR / f"user_settings.invalid.{counter}.json"
        counter += 1
    try:
        SETTINGS_FILE.replace(candidate)
        return candidate
    except OSError:
        return None


# ============================================================
# Persistence
# ============================================================

def load_settings() -> dict:
    cleanup_stale_temp_settings()
    migrate_legacy_settings()
    if not SETTINGS_FILE.exists():
        return normalize_settings(DEFAULT_SETTINGS)
    try:
        data = read_json_file(SETTINGS_FILE)
        if not isinstance(data, dict):
            raise TypeError("Settings JSON must contain an object.")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        backup_path = backup_invalid_settings_file()
        print(f"Could not load settings; using defaults: {exc}")
        if backup_path is not None:
            print(f"Invalid settings were preserved at: {backup_path}")
        return normalize_settings(DEFAULT_SETTINGS)
    return normalize_settings(data)


def save_settings(settings: dict) -> bool:
    if not isinstance(settings, dict):
        print("Could not save settings: settings must be a dictionary.")
        return False
    normalized = normalize_settings(settings)
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if settings_file_is_valid(SETTINGS_FILE):
            try:
                shutil.copy2(SETTINGS_FILE, SETTINGS_BACKUP_FILE)
            except OSError as exc:
                print(f"Settings backup could not be refreshed: {exc}")
        write_json_file(SETTINGS_TEMP_FILE, normalized)
        if not settings_file_is_valid(SETTINGS_TEMP_FILE):
            raise ValueError("Temporary settings validation failed.")
        SETTINGS_TEMP_FILE.replace(SETTINGS_FILE)
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"Could not save settings: {exc}")
        try:
            SETTINGS_TEMP_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def reset_settings() -> bool:
    return save_settings(dict(DEFAULT_SETTINGS))


__all__ = [
    "APP_NAME", "SETTINGS_VERSION", "APP_DIR", "SETTINGS_FILE", "SETTINGS_TEMP_FILE",
    "SETTINGS_BACKUP_FILE", "LEGACY_SETTINGS_FILE", "DEFAULT_SETTINGS",
    "MIN_WINDOW_WIDTH", "MIN_WINDOW_HEIGHT", "MAX_WINDOW_WIDTH", "MAX_WINDOW_HEIGHT",
    "normalize_text", "normalize_bool", "normalize_int", "normalize_theme",
    "normalize_framework_id", "normalize_output_folder", "normalize_settings",
    "is_safe_output_folder_text", "get_app_dir", "ensure_app_dir", "get_default_output_dir",
    "resolve_output_folder", "get_output_folder", "sanitize_framework_id",
    "get_framework_output_dir", "read_json_file", "write_json_file", "settings_file_is_valid",
    "cleanup_stale_temp_settings", "migrate_legacy_settings", "backup_invalid_settings_file",
    "load_settings", "save_settings", "reset_settings",
]
