"""
File: hardware/base/biometric_base.py

Purpose
-------
Abstract interface for biometric capture devices. Extends DeviceBase with the
capture operation that concrete scanners (fingerprint, placeholder) must
implement.

Public interface:
- class BiometricBase(DeviceBase). Public methods: scan.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.device_base (hardware/base/device_base.py)
Standard library: abc.
Imported by:
- hardware/biometric/fingerprint_scanner.py
- hardware/biometric/placeholder_biometric.py
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
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.base.biometric_base import BiometricBase
    obj = BiometricBase()
    obj.scan()
"""

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class BiometricBase(DeviceBase):

    @abstractmethod
    def scan(self):
        pass



