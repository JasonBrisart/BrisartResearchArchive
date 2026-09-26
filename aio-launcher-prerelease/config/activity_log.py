"""
File: config/activity_log.py

Purpose:
Persist the most recent Activity Log lines to disk so the Settings page
shows what happened in previous sessions, not only the current one.

Communication / relationships:
- Reads APP_DIR from config/runtime.py.
- Only writer: controllers/log_controller.py, through
  append_activity_log_entry(), on every LogController.log() call.
- Only reader: gui/pages/settings_page.py, through load_activity_log(),
  every time the Settings page is built.

Settings / parameters:
- MAX_PERSISTED_ENTRIES (100): a rolling window across sessions. Once
  the cap is reached, each new entry drops the single oldest entry.
- ACTIVITY_LOG_FILE: APP_DIR/activity_log.json.
- ACTIVITY_LOG_TEMP_FILE: APP_DIR/activity_log.json.tmp.
- Storage format: a JSON array of strings, oldest first, newest last.
  Each string already carries its own "[YYYY-MM-DD HH:MM:SS] " prefix,
  identical to what LogController writes into the on-screen widgets.

Edge cases:
- A missing, unreadable, or corrupt file returns an empty list and never
  raises, so a broken log can never stop the Settings page rendering.
- A failed append is swallowed, so logging can never crash the action
  being logged.
- Writes go to a .tmp file first and then replace the real file, so a
  crash mid-write loses at most the newest entry, never the whole log.
- Blank entries are ignored. Files holding more than the cap are trimmed
  on load.

Known limitations:
- Every append rewrites the whole file, which is fine at 100 entries.
- There is no locking between two running copies of the Archive; they
  can overwrite each other's newest entries.
- Newest-first display order is handled by gui/pages/settings_page.py,
  not here.

Examples:
- append_activity_log_entry("[2026-09-26 10:00:00] Application settings saved.")
- history = load_activity_log()
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from config.runtime import APP_DIR

MAX_PERSISTED_ENTRIES = 100

ACTIVITY_LOG_FILE = APP_DIR / "activity_log.json"
ACTIVITY_LOG_TEMP_FILE = APP_DIR / "activity_log.json.tmp"


def _read_entries(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise TypeError("Activity log JSON must contain a list.")
    return [str(item) for item in data]


def _write_entries(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        json.dump(entries, file, indent=2, ensure_ascii=False)
        file.write("\n")
        file.flush()
        try:
            os.fsync(file.fileno())
        except OSError:
            pass


def load_activity_log() -> list[str]:
    """
    Return the persisted activity log entries, oldest first, newest
    last. Returns an empty list -- never raises -- if the file is
    missing, unreadable, or corrupt, since a broken log file must
    never prevent the Settings page from rendering. Always trimmed to
    at most MAX_PERSISTED_ENTRIES even if the file somehow holds more
    (e.g. from a future version with a higher cap).
    """
    if not ACTIVITY_LOG_FILE.exists():
        return []
    try:
        entries = _read_entries(ACTIVITY_LOG_FILE)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return []
    return entries[-MAX_PERSISTED_ENTRIES:]


def append_activity_log_entry(entry: str) -> None:
    """
    Append one already-formatted, already-timestamped log line to the
    persisted activity log. If the log is already at
    MAX_PERSISTED_ENTRIES, the single oldest entry is dropped first so
    the file never exceeds the cap. Best-effort: any I/O failure here
    is swallowed rather than raised, so a logging call can never crash
    the action it is logging.
    """
    text = str(entry).strip()
    if not text:
        return
    try:
        entries = load_activity_log()
        entries.append(text)
        if len(entries) > MAX_PERSISTED_ENTRIES:
            entries = entries[-MAX_PERSISTED_ENTRIES:]
        _write_entries(ACTIVITY_LOG_TEMP_FILE, entries)
        ACTIVITY_LOG_TEMP_FILE.replace(ACTIVITY_LOG_FILE)
    except OSError:
        try:
            ACTIVITY_LOG_TEMP_FILE.unlink(missing_ok=True)
        except OSError:
            pass


__all__ = [
    "MAX_PERSISTED_ENTRIES", "ACTIVITY_LOG_FILE",
    "load_activity_log", "append_activity_log_entry",
]
