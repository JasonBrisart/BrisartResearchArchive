"""
File: frameworks/shared/schema.py

Purpose
-------
Preserve the legacy import path for the TFL CSV schema.

Communication / relationships
-----------------------------
- Re-exports DEFAULT_TRIAL_FIELDNAMES from frameworks/TFL/schema.py.

Settings / parameters
---------------------
- No independent schema configuration.

Edge cases
----------
- Both import paths refer to the same list object.

Known limitations
-----------------
- Compatibility shim only; frameworks define their own schemas.

Examples
--------
- from frameworks.shared.schema import DEFAULT_TRIAL_FIELDNAMES
"""
from frameworks.TFL.schema import DEFAULT_TRIAL_FIELDNAMES

__all__ = ["DEFAULT_TRIAL_FIELDNAMES"]
