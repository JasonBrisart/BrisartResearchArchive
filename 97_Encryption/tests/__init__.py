"""
File: tests/__init__.py

Purpose
-------
Marks tests/ as a regular package so `python -m unittest tests.<module>` and discovery
always load these suites, never an installed third-party package named `tests`.

Communication / relationships
-----------------------------
No imports and no exports. Python reads it only when resolving the tests package.

Settings / parameters
---------------------
None.

Edge cases
----------
Takes effect only when the 97_Encryption root is first on sys.path. That is the
default for `python -m ...` run from the root, which is how docs/TESTING.md
says to run everything.

Known limitations
-----------------
Does not stop shadowing when commands are run from a different working directory.

Examples
--------
    python -m unittest discover -s tests -p "test_*.py" -v
"""
