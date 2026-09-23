"""
ui.app_settings
----------------

Loading and saving ArchiveSnapshot's GUI application settings.

Settings are always read from and written to the current
ARCHIVE_SNAPSHOT_SETTINGS.json file. No older/legacy settings filenames
are read, since ArchiveSnapshot has no prior public release to migrate
forward from.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.app_info import APP_SETTINGS_FILENAME
from engine.settings import AppSettings


def app_settings_path() -> Path:
    """
    Return the current GUI settings file path.
    """
    return Path.cwd() / APP_SETTINGS_FILENAME


def load_app_settings() -> AppSettings:
    """
    Load the current ArchiveSnapshot GUI settings file.

    Default settings are returned when the file does not exist or
    cannot be decoded.
    """
    path = app_settings_path()

    if not path.exists():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppSettings(
            selected_archive_folder=data.get("selected_archive_folder", ""),
            archive_name=data.get("archive_name", ""),
            archive_description=data.get("archive_description", ""),
            daily_mode_enabled=bool(data.get("daily_mode_enabled", False)),
            daily_run_hour=int(data.get("daily_run_hour", 2)),
            daily_run_minute=int(data.get("daily_run_minute", 0)),
            include_zip_snapshot=bool(data.get("include_zip_snapshot", True)),
            include_hashes=bool(data.get("include_hashes", True)),
            include_folder_tree=bool(data.get("include_folder_tree", True)),
            include_diff_report=bool(data.get("include_diff_report", True)),
            include_project_context_bundle=bool(
                data.get("include_project_context_bundle", True)
            ),
            max_file_mb=float(data.get("max_file_mb", 2000)),
            max_total_mb=float(data.get("max_total_mb", 100000)),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings()


def save_app_settings(settings: AppSettings) -> None:
    """
    Save GUI settings to the current settings filename.
    """
    app_settings_path().write_text(
        json.dumps(settings.to_jsonable(), indent=2),
        encoding="utf-8",
    )
