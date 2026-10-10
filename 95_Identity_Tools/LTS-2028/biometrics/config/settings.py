"""
File: biometrics/config/settings.py

Purpose
-------
Defines ensure_data_dirs for 95_Identity_Tools/LTS-2028/biometrics/config.

Communication / relationships
-----------------------------
Direct module imports: pathlib, version.

Settings / parameters
---------------------
Module-level named settings: APP_NAME, APP_VERSION, DATA_DIR, IDENTITY_DIR, TEMPLATE_DIR, REPORT_DIR, SAMPLE_DIR, TEMPLATE_WIDTH, TEMPLATE_HEIGHT, GRID_SIZE, DEFAULT_THRESHOLD. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.
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

