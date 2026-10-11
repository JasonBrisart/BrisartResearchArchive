"""
File: biometrics/identity/device_key.py

Purpose
-------
Device binding: tying an enrolled identity to the machine that enrolled it.

Public interface:
- class DeviceKeyError(ValueError) -- Raised when device fingerprint material
  cannot be gathered or is invalid.
- current_device_fingerprint() -- Collect a best-effort, machine-specific
  fingerprint string.
- bind_device(master_key, fingerprint=None) -- Produce a stored binding of a
  device fingerprint under the master key.
- verify_device(master_key, bound_value, fingerprint=None) -- Check whether the
  current (or supplied) device matches a stored binding.

Design notes:

The problem this solves: a stolen identity store (the JSON file on disk) should
not be usable on a different machine without also compromising something that
is not stored in the file itself. A device key is a value derived from
machine-specific material that is never written to disk in recoverable form --
only a keyed binding of it is stored, via :mod:`crypto.factors`. Verifying a
device later means recomputing the same derivation from the live machine and
checking it against the stored binding, not reading a device key back out of
the record.

Machine-specific material is deliberately weak on its own (a hostname is
public, a MAC address is often guessable). This module does not claim device
binding is a strong security boundary equivalent to the passphrase or recovery
code -- it is one more thing an attacker must also reproduce, not a replacement
for the keyring's own authentication.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.factors (crypto/factors.py)
Standard library: platform, socket, uuid.
Imported by:
- biometrics/engine/enrollment.py
Covered by tests: biometrics/tests/test_device_key.py.

Settings / parameters
---------------------
- DEVICE_FACTOR_NAME = "device_binding"

Edge cases
----------
- current_device_fingerprint() raises DeviceKeyError: "unable to gather any
  device fingerprint material on this platform."
- Broad ``except Exception`` boundary in _safe: failures are reported to the
  user/caller rather than crashing.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.

Examples
--------
Call shapes only, not a runnable script: master_key, bound_value stand for
values the caller supplies.

::

    from biometrics.identity.device_key import (
        current_device_fingerprint,
        bind_device,
        verify_device,
    )
    current_device_fingerprint()
    bind_device(master_key)
    verify_device(master_key, bound_value)
"""

import platform
import socket
import uuid

from crypto.factors import bind_factor, verify_bound_factor

DEVICE_FACTOR_NAME = "device_binding"


class DeviceKeyError(ValueError):
    """Raised when device fingerprint material cannot be gathered or is invalid."""


def _safe(getter, default: str = "") -> str:
    try:
        value = getter()
    except Exception:
        return default
    if value is None:
        return default
    return str(value)


def current_device_fingerprint() -> str:
    """Collect a best-effort, machine-specific fingerprint string.

    Combines several weak, individually public signals (hostname, platform
    string, MAC address) so that reproducing all of them together is harder
    than reproducing any single one. Every field is gathered defensively:
    a platform that cannot report one of these (a stripped-down or unusual
    environment) still produces a fingerprint, just a less specific one,
    rather than raising and blocking enrollment entirely.
    """
    hostname = _safe(socket.gethostname)
    platform_string = _safe(platform.platform)
    machine = _safe(platform.machine)
    # uuid.getnode() returns a MAC address when available, or a random value
    # (marked by its multicast bit) when it is not. A random fallback still
    # contributes to the fingerprint's specificity for this run; it simply
    # cannot be reproduced across runs on the same machine, which is a known,
    # accepted limitation on such platforms.
    node = _safe(uuid.getnode)
    fingerprint = "|".join((hostname, platform_string, machine, node))
    if not fingerprint.strip("|"):
        raise DeviceKeyError(
            "unable to gather any device fingerprint material on this platform."
        )
    return fingerprint


def bind_device(master_key: bytes, fingerprint: str = None) -> str:
    """Produce a stored binding of a device fingerprint under the master key.

    ``fingerprint`` defaults to the current machine's fingerprint; a caller can
    pass an explicit value when re-binding to a previously recorded fingerprint
    (for example, during a migration that must not change the binding).
    """
    fingerprint = fingerprint if fingerprint is not None else current_device_fingerprint()
    return bind_factor(master_key, DEVICE_FACTOR_NAME, fingerprint)


def verify_device(master_key: bytes, bound_value: str, fingerprint: str = None) -> bool:
    """Check whether the current (or supplied) device matches a stored binding."""
    fingerprint = fingerprint if fingerprint is not None else current_device_fingerprint()
    return verify_bound_factor(master_key, DEVICE_FACTOR_NAME, fingerprint, bound_value)




