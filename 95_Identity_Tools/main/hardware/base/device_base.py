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

    from hardware.base.device_base import DeviceBase
    obj = DeviceBase()
    obj.name
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



