"""
File: hardware/card_readers/placeholder_reader.py

Purpose
-------
Placeholder reader implementation.

Communication / relationships
-----------------------------
Direct module imports: hardware.base.reader_base.

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

from hardware.base.reader_base import ReaderBase


class PlaceholderReader(ReaderBase):

    @property
    def name(self):
        return "Placeholder Reader"

    def connect(self):
        return True

    def disconnect(self):
        pass

    def health_check(self):
        return True

    def read_card(self):
        return None
