"""
File: version.py

Purpose
-------
Single source of truth for the ecosystem version. This module defines no
functions or classes; it exists for the module-level values or package marker
it provides.

Design notes:

Lives in a plain module rather than __init__.py because this package tree
deliberately uses no __init__.py files (PEP 420 namespace packages). Everything
that needs the version imports it from here:

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
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- No known limitations beyond the documented contract of its public interface.

Examples
--------
::

    import version
"""

__version__ = "1.3.9"




