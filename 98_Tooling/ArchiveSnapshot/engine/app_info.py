"""
engine.app_info
---------------
Application metadata and shared filenames for ArchiveSnapshot.

This module is the single source of truth for application identity,
generated filenames, storage paths, Project Context Helper bundle names,
and default scan exclusions.
"""
from __future__ import annotations

APP_NAME = "ArchiveSnapshot"
APP_VERSION = "2.1.2"
AUTHOR = "Jason Brisart"
REPOSITORY_NAME = "BrisartPreservationTools"

APP_TAGLINE = (
    "Local-first calendar-based archival snapshot tool for preserving "
    "digital collections over time."
)

# ---------------------------------------------------------------------------
# Snapshot storage
# ---------------------------------------------------------------------------
# The on-disk store where every dated snapshot lives. Named after the
# program itself (ArchiveSnapshot) rather than a generic "timeline".
STORE_DIRNAME = "ARCHIVE_SNAPSHOT"
STORE_INDEX_FILENAME = "ARCHIVE_SNAPSHOT_INDEX.json"
STORE_LOG_FILENAME = "ARCHIVE_SNAPSHOT_LOG.md"

# ---------------------------------------------------------------------------
# Snapshot outputs
# ---------------------------------------------------------------------------
SUMMARY_FILENAME = "ARCHIVE_SUMMARY.md"
MANIFEST_FILENAME = "ARCHIVE_MANIFEST.json"
HASHES_FILENAME = "HASHES.sha256"
TREE_FILENAME = "FOLDER_TREE.txt"
SETTINGS_FILENAME = "ARCHIVE_SETTINGS.json"
ZIP_FILENAME = "ARCHIVE_FILES.zip"
DIFF_FILENAME = "CHANGES_SINCE_PREVIOUS.md"

# ---------------------------------------------------------------------------
# GUI settings
# ---------------------------------------------------------------------------
APP_SETTINGS_FILENAME = "ARCHIVE_SNAPSHOT_SETTINGS.json"

# ---------------------------------------------------------------------------
# Daily automation
# ---------------------------------------------------------------------------
DAILY_CONFIG_FILENAME = "DAILY_SNAPSHOT_CONFIG.json"
DAILY_LOG_FILENAME = "DAILY_SNAPSHOT_LOG.md"
DAILY_STATE_FILENAME = "DAILY_SNAPSHOT_STATE.json"

# ---------------------------------------------------------------------------
# Project Context Helper import
# ---------------------------------------------------------------------------
PROJECT_CONTEXT_ACTIVE_DIRNAME = "SNAPSHOT_ACTIVE"
PROJECT_CONTEXT_ACTIVE_SUBDIRNAME = "PROJECT_CONTEXT_HELPER"
PROJECT_CONTEXT_DEST_DIRNAME = "PROJECT_CONTEXT_HELPER"
PROJECT_CONTEXT_INDEX_FILENAME = "PROJECT_CONTEXT_INDEX.json"
PROJECT_CONTEXT_MD_FILENAME = "PROJECT_CONTEXT.md"
PROJECT_CONTEXT_SUMMARY_FILENAME = "PROJECT_SUMMARY.txt"
PROJECT_CONTEXT_SETTINGS_FILENAME = "PROJECT_CONTEXT_SETTINGS.json"
PROJECT_CONTEXT_MANIFEST_FILENAME = "PROJECT_MANIFEST.json"
PROJECT_CONTEXT_ZIP_FILENAME = "PROJECT_SNAPSHOT.zip"

PROJECT_CONTEXT_KNOWN_FILES = {
    PROJECT_CONTEXT_MD_FILENAME,
    PROJECT_CONTEXT_SUMMARY_FILENAME,
    PROJECT_CONTEXT_SETTINGS_FILENAME,
    PROJECT_CONTEXT_MANIFEST_FILENAME,
    PROJECT_CONTEXT_ZIP_FILENAME,
}

# ---------------------------------------------------------------------------
# Default scan exclusions
# ---------------------------------------------------------------------------
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "build",
    "dist",
    STORE_DIRNAME,
}

DEFAULT_EXCLUDED_FILES = {
    SUMMARY_FILENAME,
    MANIFEST_FILENAME,
    HASHES_FILENAME,
    TREE_FILENAME,
    SETTINGS_FILENAME,
    ZIP_FILENAME,
    DIFF_FILENAME,
    STORE_INDEX_FILENAME,
    STORE_LOG_FILENAME,
    DAILY_STATE_FILENAME,
    DAILY_CONFIG_FILENAME,
    DAILY_LOG_FILENAME,
    APP_SETTINGS_FILENAME,
}

DEFAULT_EXCLUDED_SUFFIXES = {
    ".tmp",
    ".temp",
    ".lock",
    ".pyc",
    ".pyo",
}
