"""
File: hardware/base/device_base.py

Purpose
-------
Defines the root interface used by all hardware devices.

All future hardware integrations must inherit from DeviceBase so
the remainder of BrisartIdentityTools can communicate with hardware
through a consistent API.

This file intentionally contains no vendor-specific logic.

Communication / relationships
-----------------------------
Direct module imports: abc.

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
