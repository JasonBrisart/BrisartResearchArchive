"""
File: version.py

Purpose
-------
Single source of truth for the Brisart Research Archive version. Replaces
version.txt so the version is importable, testable, and cannot drift
between the GUI, the CLI, and the updater.

Communication / relationships
-----------------------------
- gui/theme.py imports DISPLAY_VERSION for the Settings page.
- cli.py imports DISPLAY_VERSION for its banner.
- services/updater/versioning.py reads VERSION from this file with ast,
  without importing it, so the updater always sees the version on disk
  even after an in-place update in the same process.

Settings / parameters
---------------------
- VERSION: MAJOR.MINOR.PATCH, compared by the updater.
- RELEASE_LABEL: stage label shown next to the number; not compared.
- DISPLAY_VERSION: "VERSION RELEASE_LABEL".

Edge cases
----------
- VERSION must stay a plain string literal; the updater parses it
  statically and treats anything else as 0.0.0.

Known limitations
-----------------
- Pre-release labels (ALPHA, BETA) are not ordered by the updater.

Examples
--------
- from version import DISPLAY_VERSION
"""
VERSION = "0.9.5"
RELEASE_LABEL = "ALPHA"
DISPLAY_VERSION = f"{VERSION} {RELEASE_LABEL}"
