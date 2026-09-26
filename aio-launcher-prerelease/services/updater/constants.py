"""
File: services/updater/constants.py

Purpose:
Hold the shared updater constants: registry location and markers, local
paths, size and time limits, the obsolete-file list, and the frozen
executable check. No side effects and no I/O.

Communication / relationships:
- Imported by every module in services/updater/.

Settings / parameters:
- REGISTRY_PAGE_URL: the page holding the release registry JSON. Its
  host must be in ALLOWED_REMOTE_HOSTS.
- APP_REGISTRY_ID "brisart_research_archive"; REGISTRY_START_MARKER and
  REGISTRY_END_MARKER.
- UPDATES_DIR and BACKUPS_DIR live under APPDATA.
- PROTECTED_NAMES: never backed up or overwritten.
- ALLOWED_REMOTE_HOSTS: exact hostnames the updater may contact.
- OBSOLETE_RELEASE_PATHS: files deleted from existing installations
  after a successful backup.
- Timeouts: 15 s for the registry, 120 s for downloads.

Edge cases:
- A REGISTRY_PAGE_URL whose host is not listed in ALLOWED_REMOTE_HOSTS
  fails validation before any request is sent.

Known limitations:
- The AIO Launcher prerelease location on GitHub is the current registry
  target; if that path moves, change REGISTRY_PAGE_URL.
- The registry page is read up to 64 KiB, so the markers must appear
  within that limit.

Examples:
- from services.updater.constants import REGISTRY_PAGE_URL
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REGISTRY_PAGE_URL = (
    "https://github.com/JasonBrisart/BrisartResearchArchive/"
    "blob/main/aio-launcher-prerelease/"
)
APP_REGISTRY_ID = "brisart_research_archive"
REGISTRY_START_MARKER = "<!--BRISART_REGISTRY_START-->"
REGISTRY_END_MARKER = "<!--BRISART_REGISTRY_END-->"

EXECUTION_DIR = Path(__file__).resolve().parents[2]
LOCAL_VERSION_FILE = EXECUTION_DIR / "version.txt"

APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "Brisart Research Archive"
UPDATES_DIR = APP_DIR / "updates"
BACKUPS_DIR = APP_DIR / "updates" / "backups"

# Names that are NEVER touched by the apply step, whether the update is
# applying over EXECUTION_DIR (source mode) or overwriting a frozen exe's
# own directory. This app's actual output/settings data already lives
# under APPDATA (see config/runtime.py), outside EXECUTION_DIR entirely,
# so this list only needs to guard against dev-environment clutter that
# might otherwise get backed up/overwritten unnecessarily.
PROTECTED_NAMES = {"__pycache__", ".git", ".venv", "venv", "updates"}

ALLOWED_REMOTE_HOSTS = {
    "github.com",
}

# Files that existed in earlier releases but have since been removed from
# the Archive. The installer copies files overwrite-only, so without this
# list an existing installation would keep these modules forever. Each
# entry is a path relative to the application directory, using forward
# slashes. Removal happens only after the pre-install backup is written.
OBSOLETE_RELEASE_PATHS = (
    "config/tooling_catalog.py",
    "config/tooling_state.py",
    "gui/pages/tooling_page.py",
    "services/tooling_manager.py",
    "services/tool_update_notify.py",
)

USER_AGENT = "BrisartResearchArchive-Updater/3.0"
VERSION_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:[\s\-].*)?$")

VERSION_TIMEOUT_SECONDS = 15
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_REGISTRY_RESPONSE_BYTES = 65_536
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ZIP_MEMBERS = 25_000
MAX_UNCOMPRESSED_ZIP_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250.0


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
