"""
File: v3/tests/test_codec.py

Purpose
-------
Verify v3/brisart_codec.py: RFC 4648 test vectors for Base64, Base32,
Base32hex and Base16; byte-for-byte agreement with the base64 module on
valid input; exhaustive and fuzzed rejection of malformed input; the
canonical-encoding property; and linear running time.

Communication / relationships
-----------------------------
Standard library: unittest, base64, binascii (reference only), plus
support.py in this folder.
Verifies: v3/brisart_codec.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED (see support.py).

Edge cases
----------
Every two-character Base64 tail and every Base32 final group remainder
is checked for the zero-trailing-bits rule; every byte value outside an
alphabet is injected at several positions.

Known limitations
-----------------
Agreement with base64 is tested on generated input, not proven.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_codec.py
"""

import base64
import binascii
import unittest

import support
from brisart_codec import (
    BrisartBase32Error, BrisartBase64Error, brisart_b16decode, brisart_b16encode, brisart_b32decode,
    brisart_b32encode, brisart_b64decode, brisart_b64encode, brisart_urlsafe_b64decode, brisart_urlsafe_b64encode)

STD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
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
        self.assertEqual(base64.b64decode("Zm9vYg==Zm9v"), b"foob")       # the leniency being avoided

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


class Base32Tests(unittest.TestCase):
    def test_rfc4648_base32_and_base32hex_vectors(self):
        b32 = [b"", b"MY======", b"MZXQ====", b"MZXW6===", b"MZXW6YQ=", b"MZXW6YTB", b"MZXW6YTBOI======"]
        b32hex = [b"", b"CO======", b"CPNG====", b"CPNMU===", b"CPNMUOG=", b"CPNMUOJ1", b"CPNMUOJ1E8======"]
        for plain, a, b in zip(VECTORS, b32, b32hex):
            self.assertEqual(brisart_b32encode(plain), a)
            self.assertEqual(brisart_b32decode(a), plain)
            self.assertEqual(brisart_b32encode(plain, hex=True), b)
            self.assertEqual(brisart_b32decode(b, hex=True), plain)

    def test_rfc4648_base16_vectors(self):
        for plain, hexed in zip(VECTORS, [b"", b"66", b"666F", b"666F6F", b"666F6F62", b"666F6F6261", b"666F6F626172"]):
            self.assertEqual(brisart_b16encode(plain), hexed)
            self.assertEqual(brisart_b16decode(hexed), plain)
            self.assertEqual(brisart_b16encode(plain, lowercase=True), hexed.lower())

    def test_matches_base64_module(self):
        r = support.rng("b32")
        for n in range(0, 260):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_b32encode(data), base64.b32encode(data))
            self.assertEqual(brisart_b32encode(data, hex=True), base64.b32hexencode(data))
            self.assertEqual(brisart_b32decode(base64.b32encode(data)), data)
            self.assertEqual(brisart_b32decode(base64.b32hexencode(data), hex=True), data)
            self.assertEqual(brisart_b32decode(base64.b32encode(data).lower(), casefold=True), data)
            self.assertEqual(brisart_b16encode(data), base64.b16encode(data))
            self.assertEqual(brisart_b16decode(base64.b16encode(data)), data)
            self.assertEqual(brisart_b16decode(base64.b16encode(data).lower(), casefold=True), data)

    def test_padding_policies_and_lengths(self):
        self.assertEqual(brisart_b32decode("MY", padding="optional"), b"f")
        with self.assertRaises(BrisartBase32Error):
            brisart_b32decode("MY")                                   # padding required by default
        with self.assertRaises(BrisartBase32Error):
            brisart_b32decode("MY======", padding="forbidden")
        for text in ("M", "MZX", "MZXW6Y", "MY=====", "MY=======", "MZXW6===MY======", "=MY=====", "MZXQ===",
                     "my======", "MY======\n", "MZXW6YT1", "MZXW6YT\u00e9"):
            with self.assertRaises(BrisartBase32Error, msg=repr(text)):
                brisart_b32decode(text)

    def test_every_final_group_obeys_the_trailing_bits_rule(self):
        for remainder, size in ((2, 1), (4, 2), (5, 3), (7, 4)):
            spare = remainder * 5 - size * 8
            for last in B32:
                text = "A" * (remainder - 1) + last
                value = B32.index(last)
                padded = text + "=" * {2: 6, 4: 4, 5: 3, 7: 1}[remainder]
                if value & ((1 << spare) - 1):
                    with self.assertRaises(BrisartBase32Error):
                        brisart_b32decode(padded)
                    self.assertEqual(brisart_b32decode(padded, canonical=False),
                                     base64.b32decode(padded))
                else:
                    self.assertEqual(brisart_b32decode(padded), base64.b32decode(padded))

    def test_base16_strictness(self):
        for text in ("6", "666", "6G", "66 ", " 66", "6\u0666", "ab"):
            with self.assertRaises(BrisartBase32Error, msg=repr(text)):
                brisart_b16decode(text)
        self.assertEqual(bytes.fromhex("66 6f"), b"fo")                # what fromhex alone would accept
        with self.assertRaises(BrisartBase32Error):
            brisart_b16decode("66 6F")
        with self.assertRaises(BrisartBase32Error):
            brisart_b16decode("66" * 100, max_output=10)

    def test_error_hierarchy(self):
        self.assertTrue(issubclass(BrisartBase32Error, BrisartBase64Error))
        self.assertTrue(issubclass(BrisartBase32Error, ValueError))


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
            text32 = "".join(r.choice(B32 + "=") for _ in range(r.randint(0, 18)))
            try:
                data32 = brisart_b32decode(text32)
            except BrisartBase32Error:
                continue
            self.assertEqual(brisart_b32encode(data32).decode(), text32)

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

    def test_hostile_bytes_raise_only_the_documented_errors(self):
        r = support.rng("codec-hostile")
        for _ in range(support.scaled(2000)):
            blob = support.random_bytes(r, r.randint(0, 40))
            for decode in (brisart_b64decode, brisart_b32decode, brisart_b16decode):
                try:
                    decode(blob)
                except BrisartBase64Error:
                    pass

    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: bytes(60_000 * k), brisart_b64encode)
        support.assert_roughly_linear(self, lambda k: b"A" * (80_000 * k), brisart_b64decode)
        support.assert_roughly_linear(self, lambda k: bytes(30_000 * k), brisart_b32encode)
        support.assert_roughly_linear(self, lambda k: b"A" * (40_000 * k), brisart_b32decode)


if __name__ == "__main__":
    unittest.main()
