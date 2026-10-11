"""
File: hardware/hardware_manager.py

Purpose
-------
Central hardware manager. The single entry point between the rest of
BrisartIdentityTools and any registered hardware driver.

Public interface:
- class HardwareManager. Public methods: create_device.

Design notes:

This file never constructs a driver's network/OS connection itself -- it only
looks up whatever class was registered under a name and instantiates it with
whatever arguments the caller supplies. For a zero-argument placeholder
(PlaceholderCamera, PlaceholderReader, PlaceholderBiometric), that means
create_device(name) alone is enough. For a real driver (PCSCReader,
ONVIFCamera, FingerprintScanner), each of which requires a caller-supplied
binding/transport object at construction time (see
hardware/base/pcsc_binding.py, hardware/base/onvif_transport.py,
hardware/base/biometric_binding.py), the caller passes that object through
create_device() exactly as they would to the driver class directly.
HardwareManager itself never imports, constructs, or knows about any concrete
PCSCBinding, ONVIFTransport, or BiometricBinding implementation. It has no
knowledge of networks, sockets, or operating-system libraries of any kind.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.registry (hardware/registry.py)
Standard library: none.
Imported by: no other module in this tree imports it directly.
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
- HardwareManager.create_device() raises ValueError: "Hardware device '{...}'
  is not registered."

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.hardware_manager import HardwareManager
    obj = HardwareManager()
    obj.create_device(device_name)
"""

from hardware.registry import get


class HardwareManager:
    def create_device(self, device_name: str, *args, **kwargs):
        device_class = get(device_name)
        if device_class is None:
            raise ValueError(
                f"Hardware device '{device_name}' is not registered."
            )
        return device_class(*args, **kwargs)




