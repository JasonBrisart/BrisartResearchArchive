"""
File: biometrics/config/settings.py

Purpose
-------
Central configuration for the biometrics tool: application identity and the
on-disk data/ layout (identities, reports, samples). ensure_data_dirs() creates
that layout before any command writes to it.

Image geometry for feature extraction lives in
biometrics/features/fingerprint_features.py and
biometrics/features/video_features.py; per-modality match thresholds live in
biometrics/engine/modalities.py (DEFAULT_THRESHOLDS).

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
- APP_NAME = "Biometrics" -- tool name. Not read by other modules.
- APP_VERSION = __version__ -- re-exported ecosystem version from version.py.
  Not read by other modules.
- DATA_DIR = Path("data") -- root of all biometrics runtime data, relative to
  the working directory.
- IDENTITY_DIR = DATA_DIR / "identities" -- one JSON identity record per
  enrolled identity.
- TEMPLATE_DIR = DATA_DIR / "templates" -- created by ensure_data_dirs();
  sealed templates are stored inside each identity record in IDENTITY_DIR.
- REPORT_DIR = DATA_DIR / "reports" -- enrollment/verification audit reports.
- SAMPLE_DIR = DATA_DIR / "samples" -- generated synthetic samples and probes.
- TEMPLATE_WIDTH = 64 -- not read by the feature extractors; fingerprint
  extraction uses fingerprint_features.TARGET_WIDTH (128).
- TEMPLATE_HEIGHT = 64 -- not read by the feature extractors; fingerprint
  extraction uses fingerprint_features.TARGET_HEIGHT (128).
- GRID_SIZE = 8 -- not read by the feature extractors, which define their own
  GRID_SIZE.
- DEFAULT_THRESHOLD = 0.94 -- not read by verification; thresholds come from
  biometrics.engine.modalities.DEFAULT_THRESHOLDS (voice 0.85, fingerprint
  0.80, video 0.75).

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
