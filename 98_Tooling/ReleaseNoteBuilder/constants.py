"""
File: constants.py

Purpose
-------
ReleaseNoteBuilder constants.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
Module-level named settings: APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_NAME, REPOSITORY_URL, APPLICATION_TAGLINE, OUTPUT_RELEASE_NOTES, OUTPUT_CHANGELOG, OUTPUT_MANIFEST, EXCLUDED_DIRS, EXCLUDED_FILES, EXCLUDED_SUFFIXES, TEXT_SUFFIXES. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
ReleaseNoteBuilder constants.

Part of BrisartDevTools.
"""

APP_NAME = "ReleaseNoteBuilder"
APP_VERSION = "1.0.0"

AUTHOR = "Jason Brisart"

REPOSITORY_NAME = "BrisartDevTools"
REPOSITORY_URL = "https://github.com/JasonBrisart/BrisartDevTools"

APPLICATION_TAGLINE = (
    "Generate release notes, changelog drafts, and "
    "release manifests from project version comparisons."
)

OUTPUT_RELEASE_NOTES = "RELEASE_NOTES.md"
OUTPUT_CHANGELOG = "CHANGELOG_DRAFT.md"
OUTPUT_MANIFEST = "RELEASE_MANIFEST.json"

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "venv",
    ".venv",
    "env",
    "build",
    "dist",
    "node_modules",
    "updates",
}

EXCLUDED_FILES = {
    OUTPUT_RELEASE_NOTES,
    OUTPUT_CHANGELOG,
    OUTPUT_MANIFEST,
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".rar",
    ".log",
}

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
}
