r"""
File: brisart_ai/version_info.py

Purpose
-------
Expose the app label and release version to the desktop.

Internal helpers include _read_version.

Communication / relationships
-----------------------------
Loads project-root version.py by file path.

Direct importing modules include brisart_ai/tests/test_version_info.py,
brisart_ai/ui/app.py, brisart_ai/ui/sidebar.py.

Settings / parameters
---------------------
APP_NAME is BrisartAI; version resolution happens at import.

Module configuration and named constants: APP_NAME='BrisartAI'.

Edge cases
----------
Missing, invalid or empty version data falls back to 0.0.0-unknown.

Explicit exception branches or raised errors in this file include Exception.

Known limitations
-----------------
This module reports a local version; it has no updater or remote check.

The fallback hides the underlying import exception from normal startup. If the displayed version is 0.0.0-unknown, inspect the root version file rather than assuming an update failed.

Examples
--------
from brisart_ai.version_info import APP_NAME, __version__
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

APP_NAME = "BrisartAI"

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_FILE = _PROJECT_ROOT / "version.py"
_FALLBACK_VERSION = "0.0.0-unknown"


def _read_version() -> str:
    try:
        spec = importlib.util.spec_from_file_location("_brisart_version", _VERSION_FILE)
        if spec is None or spec.loader is None:
            return _FALLBACK_VERSION
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = getattr(module, "__version__", "")
        return str(version).strip() or _FALLBACK_VERSION
    except Exception:
        return _FALLBACK_VERSION


__version__ = _read_version()

__all__ = ["APP_NAME", "__version__"]
