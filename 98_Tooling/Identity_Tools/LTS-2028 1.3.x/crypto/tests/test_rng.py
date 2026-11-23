"""
File: crypto/tests/test_rng.py

Purpose
-------
Tests for crypto.rng.ManagedGenerator / new_generator.

Verifies: crypto/errors.py, crypto/rng.py.
Contains 10 test case(s) across 3 TestCase class(es).

Design notes:

Fast: seeds from secrets.token_bytes and expands via BSR2's sponge DRBG; no KDF
involved.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
- crypto.rng (crypto/rng.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
No module-level settings and no on-disk fixtures; every test constructs its
inputs in memory.

Edge cases
----------
NewGeneratorTests:
- New generator returns a usable generator.
- New generator rejects empty purpose.
- New generator rejects non string purpose.
GenerateTests:
- Generate returns the requested length.
- Generate rejects non positive length.
- Generate rejects empty additional input.
- Different additional input yields different output.
- Two generators produce independent streams.
PersonalizationTests:
- Direct construction rejects short personalization.
- Direct construction rejects non bytes personalization.

Known limitations
-----------------
- Security rests on BSR2, a custom research construction that has not been
  independently audited (see docs/SECURITY.md); do not treat it as a
  replacement for vetted, audited cryptography.
- Passing proves only the 10 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
::

    python -m unittest crypto.tests.test_rng -v
    python tests/run_tests.py
"""

import unittest

from crypto.errors import Bsr2IntegrationError
from crypto.rng import ManagedGenerator, new_generator


class NewGeneratorTests(unittest.TestCase):
    def test_new_generator_returns_a_usable_generator(self):
        self.assertTrue(hasattr(new_generator("t"), "generate"))

    def test_new_generator_rejects_empty_purpose(self):
        with self.assertRaises(Bsr2IntegrationError):
            new_generator("")

    def test_new_generator_rejects_non_string_purpose(self):
        with self.assertRaises(Bsr2IntegrationError):
            new_generator(123)


class GenerateTests(unittest.TestCase):
    def setUp(self):
        self.rng = new_generator("g")

    def test_generate_returns_the_requested_length(self):
        self.assertEqual(len(self.rng.generate(64, b"a")), 64)

    def test_generate_rejects_non_positive_length(self):
        # crypto/rng.py does not wrap the vendored DRBG error; it surfaces as
        # BrisartDRBGError (a ValueError). Assert the shipped behavior.
        with self.assertRaises(ValueError):
            self.rng.generate(0, b"a")

    def test_generate_rejects_empty_additional_input(self):
        with self.assertRaises(ValueError):
            self.rng.generate(32, b"")

    def test_different_additional_input_yields_different_output(self):
        self.assertNotEqual(self.rng.generate(32, b"a"), self.rng.generate(32, b"b"))

    def test_two_generators_produce_independent_streams(self):
        self.assertNotEqual(
            new_generator("s").generate(32, b"x"),
            new_generator("s").generate(32, b"x"),
        )


class PersonalizationTests(unittest.TestCase):
    def test_direct_construction_rejects_short_personalization(self):
        with self.assertRaises(Bsr2IntegrationError):
            ManagedGenerator(b"short")

    def test_direct_construction_rejects_non_bytes_personalization(self):
        with self.assertRaises(Bsr2IntegrationError):
            ManagedGenerator("not-bytes-and-long-enough-string")


if __name__ == "__main__":
    unittest.main()




