"""
File: hardware/biometric/fingerprint_scanner.py

Purpose
-------
A BiometricBase implementation for any fingerprint scanner reachable through an
organization-supplied biometric binding, containing every piece of logic this
project can implement in pure Python with zero OS or SDK calls: device-name
matching, retry policy, and validation of a capture result's shape before
handing it back to the caller. This file deliberately goes no further than that
boundary.

Public interface:
- class FingerNotPresentError(DeviceConnectionError) -- Raised when scan() is
  called but no finger was presented to the scanner within the binding's own
  timeout, or the binding otherwise failed to produce a capture.
- class FingerprintScanner(BiometricBase) -- A BiometricBase adapter for any
  fingerprint scanner reachable through an organization-supplied binding.
  Public methods: name, connect, disconnect, health_check, scan.

Design notes:

It does not import ctypes, does not detect the platform, does not speak D-Bus,
and does not import any vendor SDK. The one operation this file cannot do in
pure Python -- actually talking to a physical fingerprint scanner through the
OS's own biometric subsystem or a vendor SDK -- is delegated to a
hardware.base.biometric_binding.BiometricBinding instance supplied by the
caller at construction time. This project ships the contract for that binding
(hardware/base/biometric_binding.py) but no implementation of it, mirroring the
same boundary hardware/card_readers/pcsc_reader.py already draws for smart-card
readers. See hardware/README.md, "Why the biometric binding is not shipped,"
for why that line is drawn here specifically.

Communication / relationships
-----------------------------
Depends on (project modules):
- hardware.base.biometric_base (hardware/base/biometric_base.py)
- hardware.base.biometric_binding (hardware/base/biometric_binding.py)
- hardware.exceptions (hardware/exceptions.py)
Standard library: none.
Imported by: no other module in this tree imports it directly.
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
- CAPTURE_RETRY_COUNT = 1

Edge cases
----------
- FingerprintScanner.__init__() raises TypeError: "FingerprintScanner requires
  a hardware.base.biometric_binding.BiometricBinding instance; got {...}
  instead. This project ships the binding CONTRACT only -- see
  hardware/README.md, 'Why the biometric binding is not shipped,' for how to
  supply one."
- FingerprintScanner.connect() raises DeviceConnectionError: "no fingerprint
  scanners were reported by the binding, or none matched {...}."
- FingerprintScanner._find_device_name() raises DeviceConnectionError:
  "binding.list_devices() failed: {...}"
- FingerprintScanner.scan() raises DeviceConnectionError: "{...} is not
  connected; call connect() first."
- FingerprintScanner.scan() raises FingerNotPresentError: "no finger detected
  on {...}: {...}"
- FingerprintScanner._validate_capture_shape() raises DeviceConnectionError:
  "binding.capture() must return a dict; got {...}."
- FingerprintScanner._validate_capture_shape() raises DeviceConnectionError:
  "binding.capture() result is missing key(s): {...}."
- FingerprintScanner._validate_capture_shape() raises DeviceConnectionError:
  "binding.capture()'s width/height must be int."
- FingerprintScanner._validate_capture_shape() raises DeviceConnectionError:
  "binding.capture()'s pixels must be bytes."
- FingerprintScanner._validate_capture_shape() raises DeviceConnectionError:
  "binding.capture() returned {...} pixel bytes; expected width*height =
  {...}."
- FingerprintScanner._find_device_name(): translates BiometricBindingError into
  DeviceConnectionError, so callers only need to handle this module's own error
  type.
- FingerprintScanner.connect(), FingerprintScanner.scan(): catches
  (BiometricBindingError, DeviceConnectionError) and handles it in place; it
  does not propagate to the caller.
- FingerprintScanner.disconnect(): catches BiometricBindingError and handles it
  in place; it does not propagate to the caller.
- FingerprintScanner.health_check(): catches DeviceConnectionError and handles
  it in place; it does not propagate to the caller.

Known limitations
-----------------
- No test module imports this file directly; it is exercised only through its
  callers' tests, so check changes manually.

Examples
--------
Call shapes only, not a runnable script: binding stands for a value the caller
supplies.

::

    from hardware.biometric.fingerprint_scanner import FingerprintScanner
    obj = FingerprintScanner(binding)
    obj.name
"""

from hardware.base.biometric_base import BiometricBase
from hardware.base.biometric_binding import (
    BiometricBinding,
    BiometricBindingError,
)
from hardware.exceptions import DeviceConnectionError

CAPTURE_RETRY_COUNT = 1


class FingerNotPresentError(DeviceConnectionError):
    """Raised when scan() is called but no finger was presented to the
    scanner within the binding's own timeout, or the binding otherwise
    failed to produce a capture."""


class FingerprintScanner(BiometricBase):
    """A BiometricBase adapter for any fingerprint scanner reachable
    through an organization-supplied binding.

    Contains 100% pure Python logic: device-name matching, retries, and
    capture-result shape validation. Makes zero OS or SDK calls itself
    -- every operation that must touch WinBio, libfprint/fprintd, or a
    vendor SDK is delegated to the required `binding` argument, an
    implementation of hardware.base.biometric_binding.BiometricBinding
    supplied by the caller.
    """

    def __init__(self, binding: BiometricBinding, device_name_contains=None):
        if not isinstance(binding, BiometricBinding):
            raise TypeError(
                "FingerprintScanner requires a hardware.base."
                "biometric_binding.BiometricBinding instance; got "
                f"{type(binding).__name__!r} instead. This project "
                "ships the binding CONTRACT only -- see "
                "hardware/README.md, 'Why the biometric binding is "
                "not shipped,' for how to supply one."
            )
        self._binding = binding
        self._device_name_contains = device_name_contains
        self._device_name = None
        self._session_open = False
        self.last_error = None

    @property
    def name(self) -> str:
        if self._device_name is not None:
            return f"Fingerprint Scanner ({self._device_name})"
        return "Fingerprint Scanner (not connected)"

    def connect(self) -> bool:
        try:
            self._binding.open_session()
            self._session_open = True
            device_name = self._find_device_name()
            if device_name is None:
                raise DeviceConnectionError(
                    "no fingerprint scanners were reported by the "
                    f"binding, or none matched "
                    f"{self._device_name_contains!r}."
                )
            self._binding.open_device(device_name)
            self._device_name = device_name
            self.last_error = None
            return True
        except (BiometricBindingError, DeviceConnectionError) as exc:
            self.last_error = exc
            self.disconnect()
            return False

    def _find_device_name(self):
        try:
            names = self._binding.list_devices()
        except BiometricBindingError as exc:
            raise DeviceConnectionError(
                f"binding.list_devices() failed: {exc}"
            ) from exc
        if not names:
            return None
        if self._device_name_contains:
            needle = self._device_name_contains.lower()
            matches = [n for n in names if needle in n.lower()]
            return matches[0] if matches else None
        return names[0]

    def disconnect(self) -> None:
        try:
            self._binding.close_device()
        except BiometricBindingError:
            pass  # best-effort teardown
        if self._session_open:
            try:
                self._binding.close_session()
            except BiometricBindingError:
                pass  # best-effort teardown
        self._session_open = False
        self._device_name = None

    def health_check(self) -> bool:
        if self._device_name is None or not self._session_open:
            return False
        try:
            current_name = self._find_device_name()
            self.last_error = None
            return current_name == self._device_name
        except DeviceConnectionError as exc:
            self.last_error = exc
            return False

    def scan(self) -> dict:
        if self._device_name is None:
            raise DeviceConnectionError(
                f"{self.name} is not connected; call connect() first."
            )
        last_exception = None
        for _attempt in range(CAPTURE_RETRY_COUNT + 1):
            try:
                result = self._binding.capture()
                self._validate_capture_shape(result)
                self.last_error = None
                return result
            except (BiometricBindingError, DeviceConnectionError) as exc:
                last_exception = exc
        self.last_error = last_exception
        raise FingerNotPresentError(
            f"no finger detected on {self.name}: {last_exception}"
        )

    @staticmethod
    def _validate_capture_shape(result) -> None:
        if not isinstance(result, dict):
            raise DeviceConnectionError(
                "binding.capture() must return a dict; got "
                f"{type(result).__name__!r}."
            )
        missing = {"width", "height", "pixels"} - result.keys()
        if missing:
            raise DeviceConnectionError(
                f"binding.capture() result is missing key(s): "
                f"{sorted(missing)}."
            )
        width, height, pixels = (
            result["width"], result["height"], result["pixels"]
        )
        if not isinstance(width, int) or not isinstance(height, int):
            raise DeviceConnectionError(
                "binding.capture()'s width/height must be int."
            )
        if not isinstance(pixels, (bytes, bytearray)):
            raise DeviceConnectionError(
                "binding.capture()'s pixels must be bytes."
            )
        if len(pixels) != width * height:
            raise DeviceConnectionError(
                f"binding.capture() returned {len(pixels)} pixel "
                f"bytes; expected width*height = {width * height}."
            )




