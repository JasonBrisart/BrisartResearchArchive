"""
File: hardware/base/camera_base.py

Purpose
-------
Abstract interface for camera devices. Extends DeviceBase with the
frame-capture operation that concrete cameras (ONVIF, placeholder) must
implement.

Public interface:
- class CameraBase(DeviceBase). Public methods: capture_image.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.device_base (hardware/base/device_base.py)
Standard library: abc.
Imported by:
- hardware/cameras/onvif_camera.py
- hardware/cameras/placeholder_camera.py
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

    from hardware.base.camera_base import CameraBase
    obj = CameraBase()
    obj.capture_image()
"""

from abc import abstractmethod

from hardware.base.device_base import DeviceBase


class CameraBase(DeviceBase):

    @abstractmethod
    def capture_image(self):
        pass



