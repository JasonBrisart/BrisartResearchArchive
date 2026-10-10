"""
File: hardware/biometric/placeholder_biometric.py

Purpose
-------
Placeholder biometric implementation.

Communication / relationships
-----------------------------
Direct module imports: hardware.base.biometric_base.

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

