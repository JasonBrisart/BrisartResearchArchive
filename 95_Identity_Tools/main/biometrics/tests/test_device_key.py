"""
File: biometrics/tests/test_device_key.py

Purpose
-------
Tests for biometrics.identity.device_key: machine-fingerprint binding.

Verifies: biometrics/identity/device_key.py.
Contains 6 test case(s) across 2 TestCase class(es).

Design notes:

Fast: bind_device / verify_device use the keyed-MAC factor path (~15 ms), not
the slow KDF. An injected 32-byte master key stands in for a real unlocked
device key.

Communication / relationships
-----------------------------
Depends on (project modules):
- biometrics.identity.device_key (biometrics/identity/device_key.py)
Standard library: secrets, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
DeviceFingerprintTests:
- Current fingerprint is a non empty string.
DeviceBindingTests:
- Bind then verify the same fingerprint.
- A different fingerprint does not verify.
- A different master key does not verify.
- Binding and verifying the current machine round trips.
- The bound value does not expose the fingerprint.

Known limitations
-----------------
- Passing proves only the 6 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest biometrics.tests.test_device_key -v
    python tests/run_tests.py
"""

import secrets
import unittest

from biometrics.identity import device_key


class DeviceFingerprintTests(unittest.TestCase):
    def test_current_fingerprint_is_a_non_empty_string(self):
        fingerprint = device_key.current_device_fingerprint()
        self.assertIsInstance(fingerprint, str)
        self.assertTrue(fingerprint.strip("|"))


class DeviceBindingTests(unittest.TestCase):
    def setUp(self):
        self.master_key = secrets.token_bytes(32)

    def test_bind_then_verify_the_same_fingerprint(self):
        bound = device_key.bind_device(self.master_key, "host|linux|x86_64|node")
        self.assertTrue(device_key.verify_device(self.master_key, bound, "host|linux|x86_64|node"))

    def test_a_different_fingerprint_does_not_verify(self):
        bound = device_key.bind_device(self.master_key, "machine-a")
        self.assertFalse(device_key.verify_device(self.master_key, bound, "machine-b"))

    def test_a_different_master_key_does_not_verify(self):
        bound = device_key.bind_device(self.master_key, "machine-a")
        self.assertFalse(device_key.verify_device(secrets.token_bytes(32), bound, "machine-a"))

    def test_binding_and_verifying_the_current_machine_round_trips(self):
        bound = device_key.bind_device(self.master_key)  # uses current fingerprint
        self.assertTrue(device_key.verify_device(self.master_key, bound))

    def test_the_bound_value_does_not_expose_the_fingerprint(self):
        secret_fingerprint = "very-specific-machine-signature-12345"
        bound = device_key.bind_device(self.master_key, secret_fingerprint)
        self.assertNotIn(secret_fingerprint, bound)


if __name__ == "__main__":
    unittest.main()




