"""
File: hardware/biometric/placeholder_biometric.py

Purpose
-------
Stand-in BiometricBase implementation that performs no hardware I/O and returns
fixed values. It lets the hardware manager, registry, and callers be wired and
exercised end-to-end before a real scanner is attached.

Public interface:
- class PlaceholderBiometric(BiometricBase). Public methods: name, connect,
  disconnect, health_check, scan.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.biometric_base (hardware/base/biometric_base.py)
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
- Placeholder biometric implementation.
- Not a real device driver: methods return fixed values and perform no hardware
  I/O. Use it for wiring/tests until a concrete driver exists.
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.biometric.placeholder_biometric import PlaceholderBiometric
    obj = PlaceholderBiometric()
    obj.name
"""

from hardware.base.biometric_base import BiometricBase


class PlaceholderBiometric(BiometricBase):

    @property
    def name(self):
        return "Placeholder Biometric"

    def connect(self):
        return True

    def disconnect(self):
        pass

    def health_check(self):
        return True

    def scan(self):
        return None




