# Hardware Integration

Optional device contracts and driver logic for the current application line.

The supplied hardware modules are not required for ordinary Vault,
Biometrics, or Packages workflows.

They do not provide complete, ready-to-use physical-device connectivity.

## Architecture

```text
hardware/
├── base/
│   ├── device_base.py
│   ├── camera_base.py
│   ├── biometric_base.py
│   ├── reader_base.py
│   ├── pcsc_binding.py
│   ├── onvif_transport.py
│   └── biometric_binding.py
├── cameras/
│   ├── placeholder_camera.py
│   └── onvif_camera.py
├── card_readers/
│   ├── placeholder_reader.py
│   └── pcsc_reader.py
├── biometric/
│   ├── placeholder_biometric.py
│   └── fingerprint_scanner.py
├── drivers/
│   └── placeholder_driver.py
├── exceptions.py
├── hardware_manager.py
└── registry.py
```

## Device interfaces

`DeviceBase` defines the common lifecycle:

- `name`
- `connect()`
- `disconnect()`
- `health_check()`

Modality-specific bases add:

- `CameraBase.capture_image()`
- `ReaderBase.read_card()`
- `BiometricBase.scan()`

Consult each concrete implementation for its return shape and exception
behavior. An abstract interface alone does not guarantee that every external
binding handles failures identically.

## Caller-supplied connectivity

| Driver | Required integration |
| --- | --- |
| `ONVIFCamera` | Caller-supplied `ONVIFTransport` |
| `PCSCReader` | Caller-supplied `PCSCBinding` |
| `FingerprintScanner` | Caller-supplied `BiometricBinding` |

The supplied driver code owns application-side protocol construction,
response parsing, selection, retries, and validation for its implemented
operations.

The supplied contracts do not implement the actual network, operating-system,
or vendor-SDK connection.

A deployment must provide and validate that connection.

This separation is an architectural choice. It should not be described as
proof that all possible devices require one particular operating-system
framework or that the supplied logic implements every feature of a protocol.

## Registry and manager

The registry maps names to classes.

`HardwareManager.create_device()` looks up a registered class and forwards
constructor arguments.

For example, after implementing a compatible binding:

```python
from hardware.card_readers.pcsc_reader import PCSCReader
from hardware.hardware_manager import HardwareManager
from hardware.registry import register

# my_binding must be an implemented PCSCBinding instance.
register("lab-reader", PCSCReader)

manager = HardwareManager()
reader = manager.create_device("lab-reader", binding=my_binding)
```

This is an integration example, not a complete runnable device connection.

A new driver must implement the appropriate base interface and be registered
before lookup through the manager.

## Placeholder devices

Placeholder implementations demonstrate interface shape.

They are not physical-device drivers, real captures, or evidence of hardware
compatibility.

`drivers/placeholder_driver.py` is different: it is an intentionally empty
module that reserves the `drivers/` folder for future low-level drivers. It
defines no classes or functions.

## Dependencies

The supplied driver logic uses standard-library Python.

A caller-supplied binding or transport can introduce operating-system
requirements, network access, SDKs, services, or third-party dependencies.
Those requirements belong to the deployment integration and must be documented
there.

## Validation status

No `hardware/tests/` suite is included in this snapshot.

The supplied ONVIF, PC/SC, and fingerprint-scanner logic has not been validated
against physical devices as part of this repository's test suite.

Protocol and contract documentation describes intended behavior. It does not
establish protocol conformance or correctness against every device.

## Recommended validation

Before deployment:

- Test against controlled fake bindings and transports.
- Exercise malformed responses and connection failures.
- Verify retry and cleanup behavior.
- Validate the actual device, firmware, operating system, and supplied binding.
- Document capture formats and conversion into supported biometric inputs.
- Check authentication, transport protection, and access-control requirements.

Hardware connectivity does not validate biometric matching accuracy or BSR2's
cryptographic security.
