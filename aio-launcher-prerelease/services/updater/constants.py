"""
services/updater/constants.py

Shared constants for the update system: registry location, marker
comments, local paths, size/count limits, and the frozen-executable
check. Nothing in this file has any side effects or does any I/O.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REGISTRY_PAGE_URL = "https://brisartresearcharchive.com/tooling"
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

ALLOWED_REMOTE_HOSTS = {"brisartresearcharchive.com"}
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
