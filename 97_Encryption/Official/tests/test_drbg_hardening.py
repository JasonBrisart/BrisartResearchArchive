"""
File: tests/test_drbg_hardening.py

Purpose
-------
Tests for the 0.4.0 BrisartDRBG hardening: fork detection, refusal to copy,
deep-copy or pickle generator state, the ``from_system_entropy`` constructor,
boolean length rejection, and size ceilings on personalization and
additional input, while confirming that the frozen output is unchanged.

Communication / relationships
-----------------------------
Imports brisart_security_drbg.py; patches ``os.getpid`` inside that module to
simulate running in a forked child.

Settings / parameters
---------------------
SEED = bytes(range(64)); PERSONALIZATION = b"BSR2 drbg hardening".

Edge cases
----------
After a detected fork the generator is destroyed and stays unusable until a
valid reseed, after which it works in the new process.

Known limitations
-----------------
Fork detection is simulated, not exercised with a real ``os.fork``, so the
test also runs on Windows.

Examples
--------
    python -m unittest -v tests.test_drbg_hardening
"""
import copy
import pickle
import unittest
from unittest.mock import patch

import brisart_security_drbg as drbg_module
from brisart_security_drbg import (
    MAX_ADDITIONAL_INPUT_BYTES,
    MAX_PERSONALIZATION_BYTES,
    BrisartDRBG,
    BrisartDRBGError,
)

SEED = bytes(range(64))
PERSONALIZATION = b"BSR2 drbg hardening"


class DrbgHardeningTests(unittest.TestCase):
    def test_fork_detection_destroys_until_reseed(self) -> None:
        generator = BrisartDRBG(SEED, PERSONALIZATION)
        generator.generate(16, b"parent")
        child_pid = drbg_module.os.getpid() + 1
        with patch.object(drbg_module.os, "getpid", return_value=child_pid):
            with self.assertRaises(BrisartDRBGError):
                generator.generate(16, b"child")
            with self.assertRaises(BrisartDRBGError):
                generator.generate(16, b"child again")
            generator.reseed(bytes(reversed(SEED)), b"child reseed")
            self.assertEqual(len(generator.generate(16, b"child after reseed")), 16)

    def test_state_cannot_be_cloned(self) -> None:
        generator = BrisartDRBG(SEED, PERSONALIZATION)
        for action in (lambda: copy.copy(generator), lambda: copy.deepcopy(generator), lambda: pickle.dumps(generator)):
            with self.assertRaises(TypeError):
                action()
        self.assertNotIn("state", repr(generator))

    def test_from_system_entropy_is_unique(self) -> None:
        first = BrisartDRBG.from_system_entropy(PERSONALIZATION).generate(32, b"a")
        second = BrisartDRBG.from_system_entropy(PERSONALIZATION).generate(32, b"a")
        self.assertNotEqual(first, second)

    def test_limits_and_types(self) -> None:
        generator = BrisartDRBG(SEED, PERSONALIZATION)
        with self.assertRaises(BrisartDRBGError):
            generator.generate(True, b"bool length")
        with self.assertRaises(BrisartDRBGError):
            generator.generate(16, b"x" * (MAX_ADDITIONAL_INPUT_BYTES + 1))
        with self.assertRaises(BrisartDRBGError):
            BrisartDRBG(SEED, b"p" * (MAX_PERSONALIZATION_BYTES + 1))
        with self.assertRaises(BrisartDRBGError):
            generator.reseed(SEED, b"x" * (MAX_ADDITIONAL_INPUT_BYTES + 1))

    def test_output_unchanged_by_hardening(self) -> None:
        expected = (
            "ec2c0cac81eaa228234ba739aa7141459a2f0b5ddb0442d711ff0ab78e903f31"
        )
        output = BrisartDRBG(SEED, b"BSR2 known answer DRBG").generate(128, b"first request")
        self.assertEqual(output.hex()[:64], expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
