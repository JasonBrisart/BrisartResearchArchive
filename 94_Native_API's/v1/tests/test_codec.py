"""
File: v1/tests/test_codec.py

Purpose
-------
Characterise v1/brisart_codec.py: confirm what it gets right (RFC 4648
vectors and byte-for-byte agreement with the base64 module on valid
input), run its embedded self-test, and pin down its known defects so
that the frozen v1 baseline cannot change silently.

Communication / relationships
-----------------------------
Standard library: unittest, base64 (reference only), plus support.py in
this folder.
Verifies: v1/brisart_codec.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED (see support.py).

Edge cases
----------
KnownDefectTests assert v1's actual (incorrect) behaviour on purpose. They
are the v1 side of probes C1-C6 in v2/tests/v1_probe.py; a failure here
means v1 changed, not that v1 got better.

Known limitations
-----------------
v1 is end-of-life and is not fixed; these tests document it.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_codec.py
"""

import base64
import unittest

import support
import brisart_codec as codec
from brisart_codec import brisart_b64decode, brisart_b64encode, brisart_urlsafe_b64decode


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        codec._self_test()

    def test_rfc4648_vectors(self):
        pairs = [(b"", b""), (b"f", b"Zg=="), (b"fo", b"Zm8="), (b"foo", b"Zm9v"), (b"foob", b"Zm9vYg=="),
                 (b"fooba", b"Zm9vYmE="), (b"foobar", b"Zm9vYmFy")]
        for plain, encoded in pairs:
            self.assertEqual(brisart_b64encode(plain), encoded)
            self.assertEqual(brisart_b64decode(encoded), plain)
            self.assertEqual(brisart_b64decode(encoded.rstrip(b"=")), plain)

    def test_matches_base64_on_valid_input(self):
        r = support.rng("v1-codec")
        for n in range(0, 200):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_b64encode(data), base64.b64encode(data))
            self.assertEqual(brisart_b64encode(data, urlsafe=True), base64.urlsafe_b64encode(data))
            self.assertEqual(brisart_b64decode(base64.b64encode(data)), data)
            self.assertEqual(brisart_urlsafe_b64decode(base64.urlsafe_b64encode(data).rstrip(b"=")), data)

    def test_rejects_characters_outside_the_alphabet(self):
        with self.assertRaises(ValueError):
            brisart_b64decode("Zm9v!YmFy")


class KnownDefectTests(unittest.TestCase):
    """v1 behaviour that v2 changed. Each test names its probe ID."""

    def test_C1_impossible_length_decodes(self):
        self.assertEqual(brisart_b64decode("Z"), b"")

    def test_C2_wrong_padding_is_repaired(self):
        self.assertEqual(brisart_b64decode("Zg="), b"f")

    def test_C3_leading_padding_decodes(self):
        self.assertEqual(brisart_b64decode("=Zg="), b"\x01")

    def test_C4_non_canonical_trailing_bits_accepted(self):
        self.assertEqual(brisart_b64decode("Zh=="), b"f")

    def test_C5_data_after_padding_decodes(self):
        self.assertEqual(brisart_b64decode("Zm9vYg==Zm9v"), b"foobfoo")

    def test_C6_outer_whitespace_stripped(self):
        self.assertEqual(brisart_b64decode(" Zm9v "), b"foo")


if __name__ == "__main__":
    unittest.main()
