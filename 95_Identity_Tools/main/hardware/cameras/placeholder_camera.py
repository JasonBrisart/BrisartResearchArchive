"""
File: hardware/cameras/placeholder_camera.py

Purpose
-------
Placeholder camera implementation.

Communication / relationships
-----------------------------
Direct module imports: hardware.base.camera_base.

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

Additional module documentation
-------------------------------
Placeholder camera implementation.

Used only for testing architecture until
real camera vendors are supported.
"""

from hardware.base.camera_base import CameraBase


class PlaceholderCamera(CameraBase):

    @property
    def name(self):
        return "Placeholder Camera"

    def connect(self):
        return True

    def disconnect(self):
        pass

    def health_check(self):
        return True

    def capture_image(self):
        return None
