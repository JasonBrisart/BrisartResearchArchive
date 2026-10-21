r"""
File: version.py

Purpose
-------
Define the single release-version string imported by BrisartOS components,
without computing metadata or performing initialization.

Design notes:

The only executable statement assigns __version__. Consumers import the string
from this root-level module. The value is opaque text: this file neither
validates version syntax nor compares releases, and changing it performs no
data migration.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/extensions/registry.py
- brisartos/services/archive.py
- brisartos/services/settings.py
- brisartos/services/updates.py
- brisartos/shell/commands.py
- modules/hello_lab/module.py
Covered by tests: brisartos/extensions/tests/test_registry.py,
brisartos/services/tests/test_services.py, tests/test_project.py.

Settings / parameters
---------------------
- __version__ = '0.0.14' -- The release version of this tree, kept as opaque
  text.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the interpreter reaches the importer unchanged.

Known limitations
-----------------
- The version is a plain string edited by hand. A test checks that no other
  file copies the value and that the newest heading in docs/CHANGELOG.md
  contains it, but nothing checks it against what actually shipped.
- The value is treated as opaque text: nothing parses or compares versions, so
  ordering between releases is not enforced.
- It versions the program, not stored data. Files written under data/ carry no
  format version, so changing this value never migrates or invalidates them.

Examples
--------
Run from the repository root.

::

    from version import __version__
    assert isinstance(__version__, str) and __version__
"""

__version__ = "0.0.14"
