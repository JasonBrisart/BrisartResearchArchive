"""
File: hardware/cameras/placeholder_camera.py

Purpose
-------
Stand-in CameraBase implementation that performs no hardware I/O and returns
fixed values. It lets the hardware manager, registry, and callers be wired and
exercised end-to-end before a real camera is attached.

Public interface:
- class PlaceholderCamera(CameraBase). Public methods: name, connect,
  disconnect, health_check, capture_image.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.camera_base (hardware/base/camera_base.py)
Standard library: none.
Imported by: no other module in this tree imports it directly.
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
- Placeholder camera implementation.
- Used only for testing architecture until real camera vendors are supported.
- Not a real device driver: methods return fixed values and perform no hardware
  I/O. Use it for wiring/tests until a concrete driver exists.
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
::

    from hardware.cameras.placeholder_camera import PlaceholderCamera
    obj = PlaceholderCamera()
    obj.name
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



