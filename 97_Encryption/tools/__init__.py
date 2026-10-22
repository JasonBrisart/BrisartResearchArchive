"""
File: tools/__init__.py

Purpose
-------
Marks tools/ as a regular package so `from tools.generate_bsr2_parameters import ...`
in tests/test_bsr2_parameters.py cannot resolve to an installed package named `tools`.

Communication / relationships
-----------------------------
No imports and no exports. Python reads it only when resolving the tools package.

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
