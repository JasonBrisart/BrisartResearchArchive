"""
File: hardware/base/device_base.py

Purpose
-------
Abstract root interface (DeviceBase) that every hardware device implements: a
display name plus connect, disconnect, and health_check. The reader, camera,
and biometric bases extend it, so hardware_manager can treat any device
uniformly.

Public interface:
- class DeviceBase(ABC) -- Base class for all supported hardware devices.
  Public methods: name, connect, disconnect, health_check.

Communication / relationships
-----------------------------
Standard library: abc.
Imported by:
- hardware/base/biometric_base.py
- hardware/base/camera_base.py
- hardware/base/reader_base.py
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

    from hardware.base.device_base import DeviceBase

    class ExampleDeviceBase(DeviceBase):
        @property
        def name(self):
            return "Example device"

        def connect(self):
            return True

        def disconnect(self):
            return None

        def health_check(self):
            return True

    example = ExampleDeviceBase()
    assert example.connect() is True
"""

from abc import ABC, abstractmethod


class DeviceBase(ABC):
    """
    Base class for all supported hardware devices.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass



