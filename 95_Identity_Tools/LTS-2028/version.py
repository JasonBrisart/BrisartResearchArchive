"""
File: version.py

Purpose
-------
Single source of truth for this application tree's release version.
This module defines the __version__ string and no functions or classes.
It is a plain module, not a package marker.

Design notes:

Lives in a plain module rather than __init__.py because the application
folders deliberately use no __init__.py files (PEP 420 namespace packages).
Everything that needs the version imports it from here:

    from version import __version__

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- app.py
- biometrics/config/settings.py
- cli.py
- vault/config/settings.py
Covered by tests: tests/test_cli_dispatcher.py.

Settings / parameters
---------------------
- __version__ = "1.3.10" -- the release version of this tree.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- The version is a plain string edited by hand. Nothing checks it against
  docs/CHANGELOG.md, the README files, or what actually shipped. LTS-2028 and
  main each carry their own copy of this file with their own value.
- It versions the tools, not stored data. Each stored format carries its own
  format string (for example "brisart-identity-tools/vault-record/v1"), so
  changing this value never migrates or invalidates existing files.
- The value is treated as opaque text: cli.py and the GUI print it, and the
  settings modules re-export it. Nothing parses or compares versions.

Examples
--------
::

    import version
"""

__version__ = "1.3.10"




