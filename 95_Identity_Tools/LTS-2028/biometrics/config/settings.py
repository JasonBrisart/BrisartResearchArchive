"""
File: biometrics/config/settings.py

Purpose
-------
Central configuration for the biometrics tool: application identity, the
on-disk data/ layout (identities, sealed templates, reports, samples), the
fixed template geometry every feature extractor normalises to, and the default
match threshold. ensure_data_dirs() creates that layout before any command
writes to it.

Public interface:
- ensure_data_dirs()

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: pathlib.
Imported by:
- biometrics/app.py
- gui/tabs/tab_biometrics.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- APP_NAME = "Biometrics" -- display name used in CLI/GUI output and report
  headers.
- APP_VERSION = __version__ -- re-exported ecosystem version from version.py.
- DATA_DIR = Path("data") -- root of all biometrics runtime data, relative to
  the working directory.
- IDENTITY_DIR = DATA_DIR / "identities" -- one JSON identity record per
  enrolled identity.
- TEMPLATE_DIR = DATA_DIR / "templates" -- sealed (BSR2-encrypted) biometric
  templates.
- REPORT_DIR = DATA_DIR / "reports" -- enrollment/verification audit reports.
- SAMPLE_DIR = DATA_DIR / "samples" -- generated synthetic samples and probes.
- TEMPLATE_WIDTH = 64 -- pixel width every image input is resampled to before
  feature extraction.
- TEMPLATE_HEIGHT = 64 -- pixel height every image input is resampled to before
  feature extraction.
- GRID_SIZE = 8 -- cells per side of the grid used to summarise a template
  image.
- DEFAULT_THRESHOLD = 0.94 -- similarity score at or above which verification
  is reported as a match.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from biometrics.config.settings import ensure_data_dirs
    ensure_data_dirs()
"""

from pathlib import Path

from version import __version__

APP_NAME = "Biometrics"
APP_VERSION = __version__

DATA_DIR = Path("data")
IDENTITY_DIR = DATA_DIR / "identities"
TEMPLATE_DIR = DATA_DIR / "templates"
REPORT_DIR = DATA_DIR / "reports"
SAMPLE_DIR = DATA_DIR / "samples"

TEMPLATE_WIDTH = 64
TEMPLATE_HEIGHT = 64
GRID_SIZE = 8
DEFAULT_THRESHOLD = 0.94


def ensure_data_dirs() -> None:
    for directory in (
        IDENTITY_DIR,
        TEMPLATE_DIR,
        REPORT_DIR,
        SAMPLE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)




