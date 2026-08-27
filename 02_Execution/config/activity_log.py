"""
config/activity_log.py
Persistent Activity Log storage. Keeps the most recent
MAX_PERSISTED_ENTRIES timestamped activity lines on disk (under
APPDATA, alongside user_settings.json -- see config/runtime.APP_DIR),
so the Activity Log on the Settings page shows what happened in
previous sessions, not just the current one, until the cap is reached
-- at which point the oldest entries are dropped one-for-one to make
room for new ones (a fixed-size rolling window, not an ever-growing
file).

Talks to:
  - controllers/log_controller.py: LogController.log() calls
    append_activity_log_entry() with every logged message, in addition
    to writing it into the live on-screen Text widgets. This is the
    only writer.
  - gui/pages/settings_page.py: render() calls load_activity_log()
    once, every time the Settings page is built, to populate the
    Activity Log Text box with history from prior sessions before any
    new entries from the current session are appended on top. This is
    the only reader.

Persistence model, specifically:
  - MAX_PERSISTED_ENTRIES (100): once this many entries exist, appending
    a new one drops the single oldest entry first, so the file holds at
    most 100 entries at any time -- a rolling window across however
    many sessions it took to reach that count, not a per-session cap.
  - Storage format: a JSON array of strings, oldest first / newest
    last -- the same order they should be displayed in a
    top-to-bottom scrolling log. Each string is a fully-formatted line
    that already includes its own "[YYYY-MM-DD HH:MM:SS] " prefix
    (matching exactly what LogController writes into the Text widgets),
    so the persisted file and the live widget always show identical
    text for the same event -- there is no separate timestamp field.
  - Writes use the same atomic pattern as config/runtime.py (write to
    a .tmp file, then os.replace() over the real file) so a crash or
    forced close mid-write can never corrupt the log into something
    that fails to load next launch -- worst case, only the newest
    entry is lost, never the whole file.
  - Every public function here is best-effort and never raises: a
    corrupt or missing log file returns an empty list rather than
    failing page render, and a failed append is silently swallowed
    rather than being allowed to crash whatever action was being
    logged in the first place.
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
