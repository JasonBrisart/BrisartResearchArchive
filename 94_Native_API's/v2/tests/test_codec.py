"""
File: v2/tests/test_codec.py

Purpose
-------
Verify v2/brisart_codec.py: RFC 4648 Base64 test vectors, byte-for-byte
agreement with the base64 module on valid input, exhaustive and fuzzed
rejection of malformed input, the canonical-encoding property, hostile
input raising only the documented error, and linear running time.

Communication / relationships
-----------------------------
Standard library: unittest, base64, binascii (reference only), plus
support.py in this folder.
Verifies: v2/brisart_codec.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED (see support.py).

Edge cases
----------
Every two-character Base64 tail is checked for the zero-trailing-bits
rule, and every byte value outside the alphabet is injected at several
positions.

Known limitations
-----------------
Agreement with base64 is tested on generated input, not proven.

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_codec.py
"""

import base64
import binascii
import unittest

import support
from brisart_codec import (
    BrisartBase64Error, brisart_b64decode, brisart_b64encode, brisart_urlsafe_b64decode, brisart_urlsafe_b64encode)

STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
VECTORS = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar"]


class Base64Tests(unittest.TestCase):
    def test_rfc4648_vectors(self):
        expected = [b"", b"Zg==", b"Zm8=", b"Zm9v", b"Zm9vYg==", b"Zm9vYmE=", b"Zm9vYmFy"]
        for plain, encoded in zip(VECTORS, expected):
            self.assertEqual(brisart_b64encode(plain), encoded)
            self.assertEqual(brisart_b64decode(encoded), plain)
            self.assertEqual(brisart_b64decode(encoded.rstrip(b"=")), plain)

    def test_matches_base64_for_every_length_up_to_300(self):
        r = support.rng("b64")
        for n in range(301):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_b64encode(data), base64.b64encode(data))
            self.assertEqual(brisart_urlsafe_b64encode(data), base64.urlsafe_b64encode(data))
            self.assertEqual(brisart_b64decode(base64.b64encode(data)), data)
            self.assertEqual(brisart_urlsafe_b64decode(base64.urlsafe_b64encode(data)), data)

    def test_malformed_input_rejected(self):
        for text in ("Z", "Zg=", "=Zg=", "Zh==", "Zm9vYg==Zm9v", "Zm9v YmFy", "Zm9v!YmFy", "====", "Zg===", "A-_A",
                     "Zm9v\u00e9", " Zm9v"):
            with self.assertRaises(BrisartBase64Error, msg=repr(text)):
                brisart_b64decode(text)

    def test_two_character_tails_follow_the_trailing_bits_rule(self):
        for a in STD:
            for b in STD:
                value = (STD.index(a) << 6) | STD.index(b)
                if value & 15:
                    with self.assertRaises(BrisartBase64Error):
                        brisart_b64decode(a + b)
                else:
                    self.assertEqual(brisart_b64decode(a + b), bytes([value >> 4]))

    def test_every_non_alphabet_byte_is_rejected(self):
        allowed = set(STD.encode()) | {ord("=")}
        for value in range(256):
            if value in allowed:
                continue
            for template in (bytes([value]) + b"AAA", b"AA" + bytes([value]) + b"A", b"AAA" + bytes([value])):
                with self.assertRaises(BrisartBase64Error):
                    brisart_b64decode(template)

    def test_options(self):
        self.assertEqual(brisart_b64decode("Zm9v\r\nYmFy", allow_whitespace=True), b"foobar")
        with self.assertRaises(BrisartBase64Error):
            brisart_b64decode("Zg", padding="required")
        with self.assertRaises(BrisartBase64Error):
            brisart_b64decode("Zg==", padding="forbidden")
        with self.assertRaises(BrisartBase64Error):
            brisart_b64decode("A" * 400, max_output=10)
        self.assertEqual(brisart_b64decode("Zh==", canonical=False), b"f")
        with self.assertRaises(TypeError):
            brisart_b64encode("text")


class FuzzAndResourceTests(unittest.TestCase):
    def test_accepted_input_re_encodes_to_itself(self):
        r = support.rng("codec-canon")
        for _ in range(support.scaled(4000)):
            text = "".join(r.choice(STD + "=") for _ in range(r.randint(0, 14)))
            try:
                data = brisart_b64decode(text)
            except BrisartBase64Error:
                continue
            self.assertEqual(brisart_b64encode(data).rstrip(b"=").decode(), text.rstrip("="))

    def test_hostile_bytes_raise_only_the_documented_error(self):
        r = support.rng("codec-hostile")
        for _ in range(support.scaled(2000)):
            blob = support.random_bytes(r, r.randint(0, 40))
            for kw in ({}, {"urlsafe": True}, {"padding": "required"}, {"allow_whitespace": True}):
                try:
                    brisart_b64decode(blob, **kw)
                except BrisartBase64Error:
                    pass

    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: bytes(60_000 * k), brisart_b64encode)
        support.assert_roughly_linear(self, lambda k: b"A" * (80_000 * k), brisart_b64decode)

    def test_never_accepts_what_strict_stdlib_rejects(self):
        r = support.rng("codec-strict")
        for _ in range(support.scaled(3000)):
            text = "".join(r.choice(STD + "=") for _ in range(r.randint(0, 16)))
            try:
                ours = brisart_b64decode(text, padding="required", canonical=False)
            except BrisartBase64Error:
                ours = None
            try:
                theirs = base64.b64decode(text, validate=True)
            except (binascii.Error, ValueError):
                theirs = None
            if ours is not None:
                self.assertEqual(ours, theirs, text)


if __name__ == "__main__":
    unittest.main()
