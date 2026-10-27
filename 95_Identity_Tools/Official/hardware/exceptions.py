"""
File: hardware/exceptions.py

Purpose
-------
Exception hierarchy for the hardware layer. Every hardware failure derives from
HardwareError so callers can catch the whole family with one clause, while
DeviceConnectionError and UnsupportedDeviceError let them distinguish an
unreachable device from a device type this build cannot drive.

Public interface:
- class HardwareError(Exception)
- class DeviceConnectionError(HardwareError)
- class UnsupportedDeviceError(HardwareError)

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- hardware/biometric/fingerprint_scanner.py
- hardware/cameras/onvif_camera.py
- hardware/card_readers/pcsc_reader.py
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

    import hardware.exceptions
"""

class HardwareError(Exception):
    pass


class DeviceConnectionError(HardwareError):
    pass


class UnsupportedDeviceError(HardwareError):
    pass



