"""
File: research/__init__.py

Purpose
-------
Marks research/ as a regular package so the research runner's folder can never be
shadowed by an installed package named `research`.

Communication / relationships
-----------------------------
No imports and no exports. Python reads it only when resolving the research package.

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
