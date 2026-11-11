"""
File: version.py

Purpose
-------
Hold the Entitle version string, the one place every surface reads it from: the command line,
  the window title, tests, and any release or packaging script. It has no imports and no side
  effects, so offline release tooling can read it without importing the application.

Communication / relationships
-----------------------------
Imports nothing. Imported by cli.py (--version), gui/window.py (window title), and
  tests/test_cli.py and tests/test_gui.py (which check that both surfaces show it).

Settings / parameters
---------------------
__version__ is a plain dotted string: major.minor.patch.

Edge cases
----------
Changing it changes the text printed by python run.py --version and shown in the window title
  only; it is never written into entitlements or records, so it does not affect verification.
  The version of the linked encryption is not here: it comes from 97_Encryption and is shown
  by --version on its own line.

Known limitations
-----------------
Nothing checks that the value matches the newest docs/CHANGELOG.md entry; update both together.

Examples
--------
Usage from the directory containing run.py:

    from version import __version__

    print(f"Entitle {__version__}")
"""

__version__ = "0.6.0"
