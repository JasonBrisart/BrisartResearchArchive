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
The interface declares abstract methods. Instantiating the abstract class
raises TypeError; a concrete subclass must implement every inherited abstract
method. Runtime device errors belong to the concrete implementation.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Concrete subclass skeleton. This example demonstrates the abstract contract,
not a real hardware integration. Replace the method bodies before deployment.
The methods return demonstration values and perform no hardware I/O.

::

    from hardware.base.biometric_base import BiometricBase

    class ExampleBiometricBase(BiometricBase):
        @property
        def name(self):
            return "Example device"

        def connect(self):
            return True

        def disconnect(self):
            return None

        def health_check(self):
            return True

        def scan(self):
            return None

    example = ExampleBiometricBase()
    assert example.connect() is True
"""

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class BiometricBase(DeviceBase):

    @abstractmethod
    def scan(self):
        pass



