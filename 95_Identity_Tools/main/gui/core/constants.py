"""
File: gui/core/constants.py

Purpose
-------
Shared constants and the repo-root bootstrap for the GUI package.

Communication / relationships
-----------------------------
Direct module imports: sys, pathlib.

Settings / parameters
---------------------
Module-level named settings: _REPO_ROOT, APP_TITLE, _MODALITY_FILETYPES. See their definitions below for values.

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
Shared constants and the repo-root bootstrap for the GUI package.

This module is imported first by every other ``gui`` module, so putting the
``sys.path`` bootstrap here guarantees the repository root is importable no
matter which GUI file is used as the entry point (``python -m gui.app``,
``python cli.py gui``, or opening a single tab/widget module directly in an
editor).

The root is located by walking UP to the directory that contains ``version.py``
(the single source of truth for the ecosystem version), rather than assuming a
fixed number of parent directories. That is deliberate: this file lives at
``gui/core/constants.py`` -- two levels below the root -- and using a hardcoded
``parent.parent`` would break the moment the file's depth changed. The walk is
the same robust pattern the test runner uses, so relocating GUI files never
re-breaks imports.

Nothing in this module imports a tool package, so importing it can never
trigger a ``vault``/``biometrics``/``packages`` import before the path is set.
"""

import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    """Return the first ancestor of ``start`` (including its own directory)
    that contains ``version.py``. Falls back to the walk's top if none match."""
    current = start.resolve().parent
    for candidate in (current, *current.parents):
        if (candidate / "version.py").is_file():
            return candidate
    return current


# --- repo-root bootstrap (runs on first import of any gui module) ---------
_REPO_ROOT = _find_repo_root(Path(__file__))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

APP_TITLE = "BrisartIdentityTools"

# File-type filters offered by the biometrics enroll/verify file pickers, keyed
# by modality name. A modality without an entry simply gets no filter (all
# files), so adding a new modality to biometrics.engine.modalities does not
# require editing this table for the dialog to keep working.
_MODALITY_FILETYPES = {
    "voice": [("WAV audio", "*.wav")],
    "fingerprint": [("Fingerprint images", "*.pgm *.png")],
    "video": [("BRVID clips", "*.brvid")],
}


class _Cancelled(Exception):
    """Raised internally when a nested sub-dialog (e.g. a payload editor
    opened from within another dialog) is cancelled by the user."""

