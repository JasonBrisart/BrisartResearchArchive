"""
File: v2/tests/test_inflate.py

Purpose
-------
Verify v2/brisart_inflate.py: agreement with zlib on valid streams and
on randomly corrupted ones (accept/reject decision, output and consumed
length), every two-byte zlib header, the output cap, Adler-32 against
zlib, the bit reader, and linear time.

Communication / relationships
-----------------------------
Standard library: unittest, zlib (reference only), plus support.py in
this folder.
Verifies: v2/brisart_inflate.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
v2 checks the output cap just after appending a literal byte rather
than before; the boundary test therefore asserts only accept/reject at
max_output = len(data) and len(data) - 1, which v2 and v3 share.

Known limitations
-----------------
Agreement with zlib is checked on generated input, not proven. v2 has
no gzip or CRC-32; those are tested in v3/tests.

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_inflate.py
"""

import unittest
import zlib

import support
from brisart_inflate import (
    DEFAULT_MAX_OUTPUT, BrisartBitReader, BrisartInflateError, BrisartInflateUnsupported, brisart_adler32,
    brisart_inflate, brisart_inflate_prefix, brisart_zlib_decompress)

WORDS = ("kernel scheduler framebuffer window pixel operating system brisart archive " * 2).split()


def raw_deflate(data, level=6, strategy=zlib.Z_DEFAULT_STRATEGY):
    c = zlib.compressobj(level, zlib.DEFLATED, -15, 8, strategy)
    return c.compress(data) + c.flush()


class ZlibTests(unittest.TestCase):
    def test_every_level_strategy_and_window(self):
        r = support.rng("inflate-valid")
        datasets = [b"", b"a", b"ab" * 500, bytes(5000), support.random_bytes(r, 3000),
                    (" ".join(r.choice(WORDS) for _ in range(2000))).encode(), bytes(range(256)) * 20]
        for data in datasets:
            for level in range(10):
                for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED, zlib.Z_HUFFMAN_ONLY, zlib.Z_RLE, zlib.Z_FIXED):
                    for wbits in (9, 15):
                        c = zlib.compressobj(level, zlib.DEFLATED, wbits, 8, strategy)
                        self.assertEqual(brisart_zlib_decompress(c.compress(data) + c.flush()), data)

    def test_corrupted_streams_get_zlibs_verdict(self):
        r = support.rng("inflate-fuzz")
        for _ in range(support.scaled(4000)):
            data = r.choice([support.random_bytes(r, r.randint(0, 400)),
                             (" ".join(r.choice(WORDS) for _ in range(r.randint(1, 300)))).encode(),
                             bytes([r.randint(0, 255)]) * r.randint(1, 1500)])
            stream = bytearray(raw_deflate(data, r.choice([0, 1, 6, 9]),
                                           r.choice([zlib.Z_DEFAULT_STRATEGY, zlib.Z_FIXED, zlib.Z_RLE])))
            mode = r.choice(["flip", "flip", "trunc", "insert", "delete", "clean"])
            if mode == "flip" and stream:
                stream[r.randrange(len(stream))] ^= 1 << r.randrange(8)
            elif mode == "trunc" and stream:
                del stream[r.randrange(len(stream)):]
            elif mode == "insert":
                stream.insert(r.randrange(len(stream) + 1), r.randrange(256))
            elif mode == "delete" and stream:
                del stream[r.randrange(len(stream))]
            stream = bytes(stream)
            try:
                ours = ("ok",) + brisart_inflate_prefix(stream, 0, None)
            except BrisartInflateError:
                ours = ("err", None, None)
            d = zlib.decompressobj(-15)
            try:
                out = d.decompress(stream)
                theirs = ("ok", out, len(stream) - len(d.unused_data)) if d.eof else ("err", None, None)
            except zlib.error:
                theirs = ("err", None, None)
            self.assertEqual(ours, theirs, (mode, stream.hex()))

    def test_every_two_byte_header_gets_zlibs_verdict(self):
        body = raw_deflate(b"hello")
        tail = zlib.adler32(b"hello").to_bytes(4, "big")
        for cmf in range(256):
            for flg in range(256):
                stream = bytes([cmf, flg]) + body + tail
                try:
                    ours = brisart_zlib_decompress(stream)
                except BrisartInflateError:
                    ours = None
                try:
                    theirs = zlib.decompress(stream)
                except zlib.error:
                    theirs = None
                self.assertEqual(ours, theirs, "%02x%02x" % (cmf, flg))

    def test_preset_dictionary_trailing_data_and_checksum(self):
        c = zlib.compressobj(6, zlib.DEFLATED, 15, 8, zlib.Z_DEFAULT_STRATEGY, zdict=b"dictionary")
        with self.assertRaises(BrisartInflateUnsupported):
            brisart_zlib_decompress(c.compress(b"dictionary text") + c.flush())
        good = zlib.compress(b"hello")
        with self.assertRaises(BrisartInflateError):
            brisart_zlib_decompress(good + b"x")
        self.assertEqual(brisart_zlib_decompress(good + b"x", allow_trailing=True), b"hello")
        bad = good[:-1] + bytes([good[-1] ^ 1])
        with self.assertRaises(BrisartInflateError):
            brisart_zlib_decompress(bad)
        self.assertEqual(brisart_zlib_decompress(bad, verify_checksum=False), b"hello")


class CapTests(unittest.TestCase):
    def test_the_cap_is_exact_for_literals_matches_and_stored_blocks(self):
        r = support.rng("cap")
        for data in (support.random_bytes(r, 3000), b"ab" * 3000, bytes(3000)):
            for level in (0, 1, 9):
                packed = zlib.compress(data, level)
                self.assertEqual(brisart_zlib_decompress(packed, max_output=len(data)), data)
                with self.assertRaises(BrisartInflateError):
                    brisart_zlib_decompress(packed, max_output=len(data) - 1)
        literal_only = raw_deflate(b"abcdefgh", 6, zlib.Z_HUFFMAN_ONLY)
        self.assertEqual(brisart_inflate(literal_only, max_output=8), b"abcdefgh")
        with self.assertRaises(BrisartInflateError):
            brisart_inflate(literal_only, max_output=7)
        self.assertEqual(brisart_zlib_decompress(zlib.compress(b""), max_output=0), b"")

    def test_default_cap_stops_a_bomb(self):
        c = zlib.compressobj(9, zlib.DEFLATED, -15)
        stream = b"".join(c.compress(bytes(1 << 20)) for _ in range(64)) + c.flush()
        self.assertLess(len(stream), 200_000)
        with self.assertRaises(BrisartInflateError):
            brisart_inflate(stream)
        self.assertEqual(DEFAULT_MAX_OUTPUT, 32 * 1024 * 1024)


class ChecksumAndReaderTests(unittest.TestCase):
    def test_adler32_matches_zlib(self):
        r = support.rng("checksums")
        for n in (0, 1, 2, 7, 64, 5551, 5552, 5553, 70000):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_adler32(data), zlib.adler32(data))
            for seed in (0, 1, 0xFFFF, 0xDEADBEEF, 0xFFFFFFFF):
                self.assertEqual(brisart_adler32(data, seed), zlib.adler32(data, seed))
        for bad in (-1, 2 ** 32, True, "0"):
            with self.assertRaises(ValueError):
                brisart_adler32(b"x", bad)

    def test_bit_reader(self):
        reader = BrisartBitReader(bytes([0b10110100, 0b00000001]))
        self.assertEqual(reader.read_bits(3), 0b100)
        self.assertEqual(reader.read_bits(5), 0b10110)
        self.assertEqual(reader.read_bit(), 1)
        with self.assertRaises(BrisartInflateError):
            BrisartBitReader(b"ab").read_raw_bytes(3)


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        r = support.rng("inflate-linear")
        support.assert_roughly_linear(self, lambda k: zlib.compress(support.random_bytes(r, 20_000 * k), 6),
                                      brisart_zlib_decompress)
        support.assert_roughly_linear(self, lambda k: zlib.compress(b"abcab" * (100_000 * k), 9),
                                      lambda s: brisart_zlib_decompress(s, max_output=None))


if __name__ == "__main__":
    unittest.main()
