"""
File: version.py

Purpose
-------
BrisartOS Version
Single source of truth for the BrisartOS version string.
Pure Python. No dependencies.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
Module-level named settings: NAME, VERSION. See their definitions below for values.

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

NAME = "BrisartOS"
VERSION = "0.10.0-alpha"


def version_text():
    return f"{NAME} {VERSION}"


if __name__ == "__main__":
    print(version_text())

