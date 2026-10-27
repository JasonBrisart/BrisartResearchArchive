"""
File: vault/config/settings.py

Purpose
-------
Central configuration for the vault tool: application identity, the on-disk
location of the sealed vault file and its audit directory, and
ensure_data_dirs() which creates that layout before the first write.

Public interface:
- ensure_data_dirs()

Design notes:

``APP_VERSION`` intentionally pulls from the single root
``version.__version__`` rather than hardcoding its own string -- the same fix
already applied to ``biometrics/config/settings.py`` -- so the two tools never
drift into reporting different version numbers for what is one ecosystem
release.

Communication / relationships
-----------------------------
Depends on (project modules):
- version (version.py)
Standard library: pathlib.
Imported by:
- gui/tabs/tab_vault.py
- vault/app.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- APP_NAME = "Vault" -- display name used in CLI/GUI output.
- APP_VERSION = __version__ -- re-exported ecosystem version from version.py.
- DATA_DIR = Path("data") / "vault" -- root of all vault runtime data, relative
  to the working directory.
- VAULT_FILE = DATA_DIR / "vault.json" -- default location of the sealed
  single-file vault.
- AUDIT_DIR = DATA_DIR / "audit" -- append-only audit log directory for vault
  events.

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

    from vault.config.settings import ensure_data_dirs
    ensure_data_dirs()
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




