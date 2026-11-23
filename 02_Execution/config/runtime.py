"""
File: config/runtime.py

Purpose
-------
Own where the Archive keeps its files: load, validate, and atomically save
the one persisted setting (the Output Directory), and resolve the folder
TFL sessions are written to. Standard library only; safe to import
without Tk.

Communication / relationships
-----------------------------
- gui/main_window.py calls load_settings() at startup.
- controllers/system_controller.py uses normalize_settings(),
  save_settings(), get_output_folder(), and get_tfl_output_dir().
- cli.py calls get_tfl_output_dir() for runs, analysis, listing, and
  "where". The TFL core (frameworks/TFL/) never imports this module: the
  host resolves the folder and passes it in, so config/ can change without
  touching the framework.
- config/activity_log.py reads APP_DIR.

Settings / parameters
---------------------
- APP_DIR: %APPDATA%/Brisart Research Archive (on Windows,
  C:/Users/<name>/AppData/Roaming/Brisart Research Archive). When APPDATA
  is not set (macOS, Linux) the base is the home folder instead.
- SETTINGS_FILE: APP_DIR/user_settings.json, written through a .tmp
  companion. DEFAULT_SETTINGS holds settings_version and output_folder
  ("outputs"); the output folder is the only persisted application
  setting.
- APP_NAME is the single owner of the application name; gui/theme.py
  imports it.
- Output Directory: a relative value stays inside APP_DIR; an absolute
  value (chosen with Browse) moves output elsewhere. TFL sessions go in its
  TFL subfolder, by default APP_DIR/outputs/TFL.
- resolve_output_folder() expands environment variables and "~" before
  deciding whether a value is absolute.

Edge cases
----------
- normalize_settings() keeps only known keys, so retired settings
  (default_framework, the three updater preferences, theme, and the
  window size) are dropped the next time settings are saved.
- Unsafe output-folder text (reserved Windows names such as CON, control
  characters, trailing dots or spaces, invalid characters, stray colons)
  falls back to "outputs".
- An unreadable settings file is moved aside to user_settings.invalid.json
  (or .invalid.N.json) and defaults are used; a message is printed.
- A stale .tmp file is promoted when the main file is missing and the temp
  file is valid; otherwise it is deleted.
- save_settings() validates its temp file before replacing the real one,
  so a failed or interrupted save leaves the previous file untouched. It
  returns False and prints the reason on failure instead of raising.
- get_tfl_output_dir() creates the folder if it does not exist.

Known limitations
-----------------
- Python installed from the Microsoft Store redirects writes under
  %APPDATA% to a private LocalCache folder, so files may appear under
  %LOCALAPPDATA%/Packages/PythonSoftwareFoundation.Python.*/LocalCache/
  Roaming instead. The Settings page shows the real resolved path.
- Output-path validation applies Windows filename rules on every OS.
- A settings file left by a very early release at config/user_settings.json
  (next to the code) is no longer read or copied; only its output folder
  could have carried over, so choose it again with Browse.
- Problems are reported with print(), which a windowed launch does not
  show; the Activity Log does not receive them.

Examples
--------
- settings = load_settings()
- get_tfl_output_dir()
- normalize_settings({"output_folder": "lab"})
"""
from __future__ import annotations

import json
import os
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
DEFAULT_SETTINGS = {
    "settings_version": SETTINGS_VERSION,
    "output_folder": "outputs",
}
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
    source = data if isinstance(data, dict) else {}
    settings = {key: source.get(key) for key in DEFAULT_SETTINGS}
    settings["settings_version"] = SETTINGS_VERSION
    settings["output_folder"] = normalize_output_folder(settings.get("output_folder"))
    return settings


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


TFL_OUTPUT_SUBFOLDER = "TFL"


def get_tfl_output_dir(settings: dict | None = None) -> Path:
    output_dir = get_output_folder(settings) / TFL_OUTPUT_SUBFOLDER
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


__all__ = [
    "APP_NAME", "SETTINGS_VERSION", "APP_DIR", "SETTINGS_FILE", "SETTINGS_TEMP_FILE",
    "DEFAULT_SETTINGS",
    "normalize_text",
    "normalize_output_folder", "normalize_settings",
    "is_safe_output_folder_text", "get_default_output_dir",
    "resolve_output_folder", "get_output_folder",
    "get_tfl_output_dir", "read_json_file", "write_json_file", "settings_file_is_valid",
    "cleanup_stale_temp_settings", "backup_invalid_settings_file",
    "load_settings", "save_settings",
]


