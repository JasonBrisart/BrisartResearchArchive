"""
File: version.py

Purpose
-------
Single source of truth for the Brisart Research Archive version, shown by
the GUI and the CLI.

Communication / relationships
-----------------------------
- gui/theme.py imports DISPLAY_VERSION for the Settings page.
- cli.py imports DISPLAY_VERSION for its banner.
- docs/CHANGELOG.md records each VERSION, and tests/test_app.py checks that
  its newest heading matches DISPLAY_VERSION.

Settings / parameters
---------------------
- VERSION: MAJOR.MINOR.PATCH.
- RELEASE_LABEL: stage label shown next to the number.
- DISPLAY_VERSION: "VERSION RELEASE_LABEL".

Edge cases
----------
- Change VERSION and add the matching docs/CHANGELOG.md entry in the same
  release; the test fails if the newest changelog heading differs.

Known limitations
-----------------
- Only the newest changelog heading is checked against DISPLAY_VERSION;
  older entries are not validated.
- Nothing compares versions: the number is for display and for the
  changelog only.

Examples
--------
- from version import DISPLAY_VERSION
"""
VERSION = "0.9.13"
RELEASE_LABEL = "ALPHA"
DISPLAY_VERSION = f"{VERSION} {RELEASE_LABEL}"


