"""
File: hardware/registry.py

Purpose
-------
Stores available device registrations.

Communication / relationships
-----------------------------
No direct module-level imports are declared.

Settings / parameters
---------------------
Module-level named settings: _DEVICE_REGISTRY. See their definitions below for values.

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

_DEVICE_REGISTRY = {}


def register(device_name: str, device_class):
    _DEVICE_REGISTRY[device_name] = device_class


def get(device_name: str):
    return _DEVICE_REGISTRY.get(device_name)


def list_registered():
    return sorted(_DEVICE_REGISTRY.keys())
