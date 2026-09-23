"""
config/tooling_state.py
Persistent, on-disk record of which Tooling-page programs (see
config/tooling_catalog.py) are currently installed, which version of
each, and where each one lives on disk. Kept as its own small file --
separate from config/runtime.py's user_settings.json -- because this
data is a factual record of installed state (rebuilt automatically by
services/tooling_manager.py on every install/update), not a user
preference someone would hand-edit.

Talks to:
  - services/tooling_manager.py is the only writer: every successful
    download_and_install_tool() call updates and re-saves this file.
  - gui/pages/tooling_page.py is the primary reader: it calls
    load_tooling_state() once per render to decide whether each
    catalog entry shows "Download" or "Run" + "Open Folder".

Storage format: a JSON object keyed by tool_id (matching
config.tooling_catalog's "id" field), each value a dict with:
  - "installed_version": the registry version string that was
    installed, exactly as published (e.g. "1.2.0").
  - "install_path": absolute path (as a string) to the folder this
    program was extracted/installed into.
Tools never installed simply have no key in this file at all -- there
is no "installed: false" placeholder entry, since the absence of a key
IS the "not installed" state.

Uses the same atomic write pattern as config/runtime.py's
save_settings() (write to a .tmp file, then os.replace() over the real
file) so a crash or forced close mid-write can never corrupt this
record -- worst case, the most recent install/update's state update is
lost, never the whole file or a previous program's entry.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from config.runtime import APP_DIR

TOOLING_STATE_FILE = APP_DIR / "tooling_state.json"
TOOLING_STATE_TEMP_FILE = APP_DIR / "tooling_state.json.tmp"

# Where installed programs actually live on disk, one subfolder per
# tool_id. Kept under the same APP_DIR as everything else this app
# persists (settings, activity log), rather than inside the Archive's
# own execution folder, so re-installing or updating the Archive
# itself never touches or risks these separately-installed programs.
TOOLING_INSTALL_ROOT = APP_DIR / "tools"


def get_install_dir(tool_id: str) -> Path:
    """Returns the folder a given tool_id installs into. Does not
    create it -- callers that need it to exist should mkdir it
    themselves (services/tooling_manager.py does this right before
    extracting/copying a downloaded release into it)."""
    return TOOLING_INSTALL_ROOT / str(tool_id)


def load_tooling_state() -> dict:
    """
    Returns the current installed-tools record as a dict, or an empty
    dict if the file doesn't exist yet or is unreadable/corrupt --
    never raises. A corrupt state file is treated the same as "nothing
    is installed yet" rather than crashing the Tooling page; the next
    successful install/update will naturally overwrite it with valid
    data again.
    """
    if not TOOLING_STATE_FILE.exists():
        return {}
    try:
        with open(TOOLING_STATE_FILE, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_tooling_state(state: dict) -> bool:
    """
    Atomically writes `state` (a dict keyed by tool_id) to disk.
    Returns True on success, False on any I/O failure -- callers
    (services/tooling_manager.py) should treat a False return as "the
    install succeeded but recording that fact failed," and log it as a
    warning rather than as a failed install, since the program itself
    is still usable even if this bookkeeping write didn't land.
    """
    if not isinstance(state, dict):
        return False
    try:
        TOOLING_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOOLING_STATE_TEMP_FILE, "w", encoding="utf-8", newline="\n") as file:
            json.dump(state, file, indent=2, ensure_ascii=False, sort_keys=True)
            file.write("\n")
            file.flush()
            try:
                os.fsync(file.fileno())
            except OSError:
                pass
        TOOLING_STATE_TEMP_FILE.replace(TOOLING_STATE_FILE)
        return True
    except OSError:
        try:
            TOOLING_STATE_TEMP_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def get_tool_record(tool_id: str) -> dict | None:
    """Returns {"installed_version": ..., "install_path": ...} for an
    installed tool, or None if it's not currently installed."""
    return load_tooling_state().get(str(tool_id))


def is_tool_installed(tool_id: str) -> bool:
    return get_tool_record(tool_id) is not None


def record_tool_installed(tool_id: str, version: str, install_path: str) -> bool:
    """Called by services/tooling_manager.py after a download+extract
    (or copy, for a single-exe asset) completes successfully. Overwrites
    any previous record for this tool_id -- e.g. on an update, the old
    version string is simply replaced with the new one."""
    state = load_tooling_state()
    state[str(tool_id)] = {
        "installed_version": str(version),
        "install_path": str(install_path),
    }
    return save_tooling_state(state)


def remove_tool_record(tool_id: str) -> bool:
    """Not currently wired to any UI action, but kept available for a
    future 'Uninstall' button -- removes the bookkeeping entry only;
    does NOT delete the installed files themselves. Returns True if a
    record existed and was removed, False if there was nothing to
    remove or the save failed."""
    state = load_tooling_state()
    if str(tool_id) not in state:
        return False
    del state[str(tool_id)]
    return save_tooling_state(state)


__all__ = [
    "TOOLING_STATE_FILE", "TOOLING_INSTALL_ROOT", "get_install_dir",
    "load_tooling_state", "save_tooling_state", "get_tool_record",
    "is_tool_installed", "record_tool_installed", "remove_tool_record",
]
