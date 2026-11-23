"""
File: config/activity_log.py

Purpose
-------
Persist the most recent Activity Log lines to disk so the Settings page
shows what happened in earlier sessions, not only the current one.

Communication / relationships
-----------------------------
- Reads APP_DIR from config/runtime.py, so the log lives in the Archive's
  AppData folder and does not move when the Output Directory setting
  changes, and reuses runtime.read_json_file() / write_json_file() so the
  application has one way to read and atomically write JSON.
- Only writer: controllers/log_controller.py, through
  append_activity_log_entry(), on every LogController.log() call.
- Only reader: gui/pages/settings_page.py, through load_activity_log(),
  each time the Settings page is built.

Settings / parameters
---------------------
- MAX_PERSISTED_ENTRIES (100): a rolling window across sessions. Once the
  cap is reached, each new entry drops the single oldest entry.
- ACTIVITY_LOG_FILE: APP_DIR/activity_log.json, with ACTIVITY_LOG_TEMP_FILE
  (activity_log.json.tmp) used while writing.
- Format: a JSON array of strings, oldest first. Each string already
  carries its "[YYYY-MM-DD HH:MM:SS] " prefix, exactly as the on-screen
  log shows it.

Edge cases
----------
- A missing, unreadable, or corrupt file loads as an empty list and never
  raises, so a damaged log can never stop the Settings page rendering.
- A failed append (an OSError while writing) is swallowed and the temp
  file is removed, so logging can never crash the action being logged.
- Writes go to the temp file (flushed and fsynced by
  runtime.write_json_file()) and then replace the real file, so a crash
  mid-write loses at most the newest entry.
- Blank entries are ignored. A file holding more than the cap is trimmed
  when loaded.

Known limitations
-----------------
- Every append reads and rewrites the whole file, which is fine at 100
  short entries.
- There is no locking between two running copies of the Archive; they can
  overwrite each other's newest entries.
- Entries are plain text, not structured, so they cannot be filtered.
- Newest-first display order is applied by gui/pages/settings_page.py, not
  here; this module stores oldest first.

Examples
--------
- append_activity_log_entry("[2026-11-23 10:00:00] Settings saved.")
- history = load_activity_log()
"""

from __future__ import annotations

import json

from config.runtime import APP_DIR, read_json_file, write_json_file

MAX_PERSISTED_ENTRIES = 100

ACTIVITY_LOG_FILE = APP_DIR / "activity_log.json"
ACTIVITY_LOG_TEMP_FILE = APP_DIR / "activity_log.json.tmp"


def _read_entries() -> list[str]:
    data = read_json_file(ACTIVITY_LOG_FILE)
    if not isinstance(data, list):
        raise TypeError("Activity log JSON must contain a list.")
    return [str(item) for item in data]


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
        entries = _read_entries()
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
        write_json_file(ACTIVITY_LOG_TEMP_FILE, entries)
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


