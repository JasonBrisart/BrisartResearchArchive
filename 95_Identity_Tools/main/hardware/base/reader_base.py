"""
File: hardware/base/reader_base.py

Purpose
-------
Base interface for access card readers.

Communication / relationships
-----------------------------
Direct module imports: abc, hardware.base.device_base.

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

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class ReaderBase(DeviceBase):

    @abstractmethod
    def read_card(self):
        pass
