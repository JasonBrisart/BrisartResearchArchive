"""
File: hardware/registry.py

Purpose
-------
Process-wide, in-memory registry mapping a device name to the class that drives
it. Drivers register themselves here and hardware_manager looks them up by
name, so new device types can be added without editing the manager.

Public interface:
- register(device_name, device_class)
- get(device_name)
- list_registered()

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- hardware/hardware_manager.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- _DEVICE_REGISTRY = {} -- private name -> device-class map; populated only
  through register().

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

    from hardware.registry import register, get, list_registered
    register(device_name, device_class)
    get(device_name)
    list_registered()
"""

_DEVICE_REGISTRY = {}


def register(device_name: str, device_class):
    _DEVICE_REGISTRY[device_name] = device_class


def get(device_name: str):
    return _DEVICE_REGISTRY.get(device_name)


def list_registered():
    return sorted(_DEVICE_REGISTRY.keys())



