"""
File: vault/config/settings.py

Purpose
-------
Configuration constants for the vault.

Communication / relationships
-----------------------------
Direct module imports: pathlib, version.

Settings / parameters
---------------------
Module-level named settings: APP_NAME, APP_VERSION, DATA_DIR, VAULT_FILE, AUDIT_DIR. See their definitions below for values.

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
Configuration constants for the vault.

``APP_VERSION`` intentionally pulls from the single root
``version.__version__`` rather than hardcoding its own string -- the same
fix already applied to ``biometrics/config/settings.py`` -- so the two tools
never drift into reporting different version numbers for what is one
ecosystem release.
"""

from pathlib import Path

from version import __version__

APP_NAME = "Vault"
APP_VERSION = __version__

DATA_DIR = Path("data") / "vault"
VAULT_FILE = DATA_DIR / "vault.json"
AUDIT_DIR = DATA_DIR / "audit"


def ensure_data_dirs() -> None:
    for directory in (DATA_DIR, AUDIT_DIR):
        directory.mkdir(parents=True, exist_ok=True)

