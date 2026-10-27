"""
File: hardware/base/biometric_binding.py

Purpose
-------
Defines the contract for the ONE operation this project deliberately does not
implement: the raw call into an operating system's own biometric subsystem (the
Windows Biometric Framework/WinBio on Windows, libfprint + fprintd on Linux, or
an equivalent vendor SDK where no OS-level framework exists). Every other piece
of fingerprint-scanner logic -- device-name matching, retry policy,
capture-result validation, and translation into this project's own exception
hierarchy -- is implemented in pure Python, with zero OS or SDK calls, in
hardware/biometric/fingerprint_scanner.py, and needs no binding at all to
exercise that logic in isolation.

Public interface:
- class BiometricBindingError(Exception) -- Raised by a BiometricBinding
  implementation for any low-level failure (session establishment, device
  listing, device open, capture timeout, no finger presented, or sensor read
  failure). fingerprint_scanner.py catches this exception type specifically and
  translates it into DeviceConnectionError / FingerNotPresentError.
- class BiometricBinding(ABC) -- The raw biometric-subsystem operations
  hardware/biometric/fingerprint_scanner.py needs. An implementation of this
  class is the only place in a deployment of BrisartIdentityTools where
  OS-level or vendor-SDK biometric code (WinBio, libfprint/fprintd, or a vendor
  SDK) is called. This project ships no implementation of this class -- see
  hardware/README.md. Public methods: open_session, close_session,
  list_devices, open_device, close_device, capture.

Design notes:

Unlike ONVIF (an open network protocol with no OS-proprietary layer, see
hardware/cameras/onvif_camera.py), there is no equivalent open wire protocol
for fingerprint scanners. Every real capture path goes through an OS-owned
biometric framework or a vendor SDK -- the same category of unavoidable wall
PC/SC presents for smart-card readers. This module mirrors
hardware/base/pcsc_binding.py's contract for exactly that reason. A
BiometricBinding implementation is the one piece of code in this project's
fingerprint-scanner support path that must call into OS-owned or vendor-owned,
non-Brisart code. This project ships the CONTRACT only. Implementing it --
actually calling WinBio, libfprint/fprintd, or a vendor SDK -- is left to the
organization deploying this software, on their own machine, under their own
audit posture. See hardware/README.md, "Why the biometric binding is not
shipped," for the full reasoning.

Communication / relationships
-----------------------------
Standard library: abc.
Imported by:
- hardware/biometric/fingerprint_scanner.py
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
The interface declares abstract methods. Instantiating the abstract class
raises TypeError; a concrete subclass must implement every inherited abstract
method. Runtime device errors belong to the concrete implementation.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Concrete subclass skeleton. This example demonstrates the abstract contract,
not a real hardware integration. Replace the method bodies before deployment.
The binding/transport skeleton raises NotImplementedError when called.

::

    from hardware.base.biometric_binding import BiometricBinding

    class ExampleBiometricBinding(BiometricBinding):
        def open_session(self):
            raise NotImplementedError("Provide a deployment implementation.")

        def close_session(self):
            raise NotImplementedError("Provide a deployment implementation.")

        def list_devices(self):
            raise NotImplementedError("Provide a deployment implementation.")

        def open_device(self, device_name):
            raise NotImplementedError("Provide a deployment implementation.")

        def close_device(self):
            raise NotImplementedError("Provide a deployment implementation.")

        def capture(self):
            raise NotImplementedError("Provide a deployment implementation.")

    example = ExampleBiometricBinding()
"""

from abc import ABC, abstractmethod


class BiometricBindingError(Exception):
    """Raised by a BiometricBinding implementation for any low-level
    failure (session establishment, device listing, device open,
    capture timeout, no finger presented, or sensor read failure).
    fingerprint_scanner.py catches this exception type specifically
    and translates it into DeviceConnectionError / FingerNotPresentError."""


class BiometricBinding(ABC):
    """The raw biometric-subsystem operations
    hardware/biometric/fingerprint_scanner.py needs. An implementation
    of this class is the only place in a deployment of
    BrisartIdentityTools where OS-level or vendor-SDK biometric code
    (WinBio, libfprint/fprintd, or a vendor SDK) is called. This
    project ships no implementation of this class -- see
    hardware/README.md.
    """

    @abstractmethod
    def open_session(self) -> None:
        """Open a session with the biometric subsystem. Raise
        BiometricBindingError on failure."""

    @abstractmethod
    def close_session(self) -> None:
        """Close a previously opened session. Must not raise if no
        session is currently held."""

    @abstractmethod
    def list_devices(self) -> list:
        """Return a list of device name strings currently visible to
        the subsystem. Return an empty list (not an exception) if none
        are attached."""

    @abstractmethod
    def open_device(self, device_name: str) -> None:
        """Open the named scanner device. Raise BiometricBindingError
        if the device does not exist or fails to open."""

    @abstractmethod
    def close_device(self) -> None:
        """Close the currently open device, if any. Must not raise if
        nothing is currently open."""

    @abstractmethod
    def capture(self) -> dict:
        """Capture one fingerprint image from the currently open
        device and return {"width": int, "height": int, "pixels":
        bytes} -- flat, row-major, 8-bit grayscale, with
        len(pixels) == width * height. Raise BiometricBindingError if
        no finger is presented within the binding's own timeout, or on
        any other capture failure."""




