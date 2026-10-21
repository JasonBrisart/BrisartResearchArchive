"""
File: v1/tests/test_inflate.py

Purpose
-------
Characterise v1/brisart_inflate.py: valid zlib and raw DEFLATE streams
from every zlib level and strategy decode correctly, Adler-32 matches
zlib for ordinary seeds, the embedded self-test passes, and the known
defects (no output cap, unchecked stored-block length, over-subscribed
codes, empty-input Adler-32 seed, preset-dictionary error type) are
pinned down.

Communication / relationships
-----------------------------
Standard library: unittest, zlib (reference only), plus support.py in
this folder.
Verifies: v1/brisart_inflate.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
v1 decodes one bit per Python call, so datasets stay small.

Known limitations
-----------------
Corrupted-stream behaviour is not compared with zlib here: v1 accepts
some streams zlib rejects, which KnownDefectTests records instead.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_inflate.py
"""

import unittest
import zlib

import support
import brisart_inflate
from brisart_inflate import brisart_adler32, brisart_inflate as inflate, brisart_zlib_decompress


def over_subscribed_stream():
    """Dynamic block for b"a" whose literal/length code over-subscribes with a third 1-bit symbol."""
    value, count = 0, 0

    def bits(v, n):
        nonlocal value, count
        value |= (v & ((1 << n) - 1)) << count
        count += n

    def code(c, n):
        for i in range(n - 1, -1, -1):
            bits((c >> i) & 1, 1)
    lengths = [0] * 258
    lengths[97] = lengths[256] = lengths[257] = 1
    bits(1, 1)
    bits(2, 2)
    bits(1, 5)
    bits(0, 5)
    bits(15, 4)
    for symbol in (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15):
        bits(4 if symbol < 16 else 0, 3)
    for length in lengths + [0]:
        code(length, 4)
    code(0, 1)
    code(1, 1)
    return value.to_bytes((count + 7) // 8, "little")


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_inflate._self_test()

    def test_every_level_and_strategy(self):
        r = support.rng("v1-inflate")
        datasets = [b"a", b"ab" * 200, bytes(2000), support.random_bytes(r, 600), bytes(range(256)) * 4,
                    b"the quick brown fox jumps over the lazy dog " * 30]
        for data in datasets:
            for level in (0, 1, 6, 9):
                for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED):
                    c = zlib.compressobj(level, zlib.DEFLATED, 15, 8, strategy)
                    self.assertEqual(brisart_zlib_decompress(c.compress(data) + c.flush()), data)
                    c = zlib.compressobj(level, zlib.DEFLATED, -15, 8, strategy)
                    self.assertEqual(inflate(c.compress(data) + c.flush()), data)

    def test_adler32_matches_zlib(self):
        r = support.rng("v1-adler")
        for n in (0, 1, 5552, 5553, 20000):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_adler32(data), zlib.adler32(data))

    def test_bad_checksum_and_header_are_rejected(self):
        good = zlib.compress(b"hello")
        with self.assertRaises(ValueError):
            brisart_zlib_decompress(good[:-1] + bytes([good[-1] ^ 1]))
        self.assertEqual(brisart_zlib_decompress(good[:-1] + bytes([good[-1] ^ 1]), verify_checksum=False), b"hello")
        with self.assertRaises(ValueError):
            brisart_zlib_decompress(b"\x78\x9d" + good[2:])


class KnownDefectTests(unittest.TestCase):
    def test_I1_no_output_cap(self):
        bomb = zlib.compress(bytes(300_000), 9)
        self.assertEqual(len(brisart_zlib_decompress(bomb)), 300_000)
        self.assertNotIn("max_output", brisart_zlib_decompress.__code__.co_varnames)

    def test_I2_stored_block_complement_unchecked(self):
        stream = bytes([1]) + (5).to_bytes(2, "little") + (0).to_bytes(2, "little") + b"hello"
        self.assertEqual(inflate(stream), b"hello")

    def test_I3_over_subscribed_code_accepted(self):
        stream = over_subscribed_stream()
        self.assertEqual(inflate(stream), b"a")
        with self.assertRaises(zlib.error):
            zlib.decompressobj(-15).decompress(stream)

    def test_I4_empty_input_adler32_not_reduced(self):
        self.assertEqual(brisart_adler32(b"", 0xFFFF), 0xFFFF)
        self.assertEqual(zlib.adler32(b"", 0xFFFF), 14)

    def test_I5_preset_dictionary_error_is_not_a_value_error(self):
        c = zlib.compressobj(6, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY, zdict=b"dictionary")
        packed = c.compress(b"dictionary text") + c.flush()
        with self.assertRaises(NotImplementedError) as caught:
            brisart_zlib_decompress(packed)
        self.assertNotIsInstance(caught.exception, ValueError)


if __name__ == "__main__":
    unittest.main()
