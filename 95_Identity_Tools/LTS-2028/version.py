"""
File: version.py

Purpose
-------
Single source of truth for the ecosystem version.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

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
Single source of truth for the ecosystem version.

Lives in a plain module rather than __init__.py because this package tree
deliberately uses no __init__.py files (PEP 420 namespace packages). Everything
that needs the version imports it from here:

    from version import __version__
"""

__version__ = "1.3.9"

