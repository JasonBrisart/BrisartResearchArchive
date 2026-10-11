"""
File: hardware/drivers/placeholder_driver.py

Purpose
-------
Reserved location for future low-level device drivers. The file is
intentionally empty: it holds the drivers/ folder in the layout so the planned
driver tier has an agreed home before any driver is written.

Communication / relationships
-----------------------------
Standard library: none.
Imported by: no other module in this tree imports it directly.
Covered by tests: no test file imports this module directly.

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
- LTS builds should never contain vendor-specific implementations from this
  directory.
- Not a real device driver: methods return fixed values and perform no hardware
  I/O. Use it for wiring/tests until a concrete driver exists.
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    import hardware.drivers.placeholder_driver
"""




