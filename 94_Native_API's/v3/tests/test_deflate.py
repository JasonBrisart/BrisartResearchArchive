"""
File: v3/tests/test_deflate.py

Purpose
-------
Verify v3/brisart_deflate.py: every stream it writes, at every level and
for many data shapes, decodes to the original with zlib, gzip and
v3/brisart_inflate.py; output is deterministic; compression ratio stays
close to zlib's at the same level; framing fields are correct; the
package-merge code lengths are complete and length-limited; and
compression time grows linearly.

Communication / relationships
-----------------------------
Standard library: unittest, zlib, gzip (reference only), plus support.py
in this folder.
Verifies: v3/brisart_deflate.py (and, through round trips,
v3/brisart_inflate.py).

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED. RATIO_MARGIN is
the largest allowed size relative to zlib at the same level.

Edge cases
----------
Empty input, single bytes, long runs (overlapping matches), random data
(stored blocks), data longer than one stored block and one Huffman block,
and data built to force every block type.

Known limitations
-----------------
Ratios are compared with zlib on generated data only. Speed is not
asserted, only linear growth.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_deflate.py
"""

import gzip
import unittest
import zlib

import support
import brisart_deflate
from brisart_deflate import DEFAULT_LEVEL, brisart_deflate as deflate, brisart_gzip_compress, brisart_zlib_compress
from brisart_inflate import brisart_gzip_decompress, brisart_inflate, brisart_zlib_decompress

WORDS = ("kernel scheduler framebuffer window pixel operating system brisart archive tooling " * 2).split()
RATIO_MARGIN = 1.05


def datasets(r):
    vocab = ["w%d" % i for i in range(800)]
    return [
        b"", b"a", b"ab", b"abc", b"ab" * 500, bytes(5000), b"x" * 70000,
        support.random_bytes(r, 3000), support.random_bytes(r, 70000),
        (" ".join(r.choice(WORDS) for _ in range(4000))).encode(),
        (" ".join(r.choice(vocab) for _ in range(3000))).encode(),
        bytes(range(256)) * 40, (b"abc" * 7 + support.random_bytes(r, 5)) * 400,
        bytes((x * 7 + y) & 255 for y in range(60) for x in range(600)),
    ]


class RoundTripTests(unittest.TestCase):
    def test_every_level_and_shape_round_trips_through_three_decoders(self):
        r = support.rng("deflate-shapes")
        for data in datasets(r):
            for level in range(10):
                raw = deflate(data, level)
                self.assertEqual(zlib.decompressobj(-15).decompress(raw), data, (len(data), level))
                self.assertEqual(brisart_inflate(raw), data)
                z = brisart_zlib_compress(data, level)
                self.assertEqual(zlib.decompress(z), data)
                self.assertEqual(brisart_zlib_decompress(z), data)
                g = brisart_gzip_compress(data, level)
                self.assertEqual(gzip.decompress(g), data)
                self.assertEqual(brisart_gzip_decompress(g), data)

    def test_random_inputs_round_trip(self):
        r = support.rng("deflate-fuzz")
        for _ in range(support.scaled(150)):
            pieces = []
            for _ in range(r.randint(0, 12)):
                kind = r.random()
                if kind < 0.3:
                    pieces.append(support.random_bytes(r, r.randint(0, 200)))
                elif kind < 0.6:
                    pieces.append(r.choice(WORDS).encode() * r.randint(1, 40))
                elif kind < 0.8 and pieces:
                    source = b"".join(pieces)
                    start = r.randrange(len(source) + 1)
                    pieces.append(source[start:start + r.randint(0, 300)])
                else:
                    pieces.append(bytes([r.randint(0, 255)]) * r.randint(1, 600))
            data = b"".join(pieces)
            level = r.randint(0, 9)
            self.assertEqual(zlib.decompress(brisart_zlib_compress(data, level)), data)

    def test_input_types_and_level_validation(self):
        for value in (b"data", bytearray(b"data"), memoryview(b"data")):
            self.assertEqual(zlib.decompress(brisart_zlib_compress(value)), b"data")
        for bad in ("text", None, 5, [1]):
            with self.assertRaises(TypeError):
                brisart_zlib_compress(bad)
        for bad in (-1, 10, 1.5, True, "6", None):
            with self.assertRaises(ValueError):
                brisart_zlib_compress(b"x", bad)
        for bad in (-1, 2 ** 32, True, 1.0):
            with self.assertRaises(ValueError):
                brisart_gzip_compress(b"x", mtime=bad)
        self.assertEqual(DEFAULT_LEVEL, 6)


class OutputTests(unittest.TestCase):
    def test_deterministic(self):
        r = support.rng("deflate-det")
        data = (" ".join(r.choice(WORDS) for _ in range(2000))).encode()
        for level in (0, 1, 6, 9):
            self.assertEqual(brisart_gzip_compress(data, level), brisart_gzip_compress(data, level))

    def test_ratio_close_to_zlib(self):
        r = support.rng("deflate-ratio")
        for data in datasets(r):
            if len(data) < 1000:
                continue
            for level in (1, 6, 9):
                ours = len(brisart_zlib_compress(data, level))
                theirs = len(zlib.compress(data, level))
                self.assertLessEqual(ours, theirs * RATIO_MARGIN + 16, (len(data), level, ours, theirs))

    def test_never_much_larger_than_the_input(self):
        r = support.rng("deflate-bound")
        for n in (0, 1, 100, 65535, 65536, 140000):
            data = support.random_bytes(r, n)
            for level in (0, 1, 9):
                per_block = 65535 if level == 0 else brisart_deflate._BLOCK_TOKENS    # tokens never exceed bytes
                blocks = max(1, -(-n // per_block))
                self.assertLessEqual(len(deflate(data, level)), n + 5 * blocks + 1)

    def test_framing_fields(self):
        data = b"hello hello hello"
        z = brisart_zlib_compress(data, 6)
        self.assertEqual(z[0], 0x78)
        self.assertEqual((z[0] * 256 + z[1]) % 31, 0)
        self.assertEqual([brisart_zlib_compress(data, lv)[1] >> 6 for lv in (0, 1, 2, 5, 6, 7, 9)], [0, 0, 1, 1, 2, 3, 3])
        self.assertEqual(int.from_bytes(z[-4:], "big"), zlib.adler32(data))
        g = brisart_gzip_compress(data, 9, mtime=1234)
        self.assertEqual(g[:4], b"\x1f\x8b\x08\x00")
        self.assertEqual(int.from_bytes(g[4:8], "little"), 1234)
        self.assertEqual((g[8], g[9]), (2, 255))
        self.assertEqual(brisart_gzip_compress(data, 1)[8], 4)
        self.assertEqual(int.from_bytes(g[-8:-4], "little"), zlib.crc32(data))
        self.assertEqual(int.from_bytes(g[-4:], "little"), len(data))
        self.assertEqual(brisart_gzip_compress(data)[4:8], b"\x00\x00\x00\x00")

    def test_level_zero_is_stored_only(self):
        data = b"a" * 200000
        stream = deflate(data, 0)
        self.assertEqual(len(stream), len(data) + 5 * 4)
        self.assertEqual(stream[0] & 6, 0)

    def test_all_three_block_types_are_used_where_smallest(self):
        r = support.rng("deflate-types")
        types = set()
        for data in (support.random_bytes(r, 2000), b"abcabcabd" * 3, (" ".join(r.choice(WORDS) for _ in range(3000))).encode()):
            types.add((deflate(data, 6)[0] >> 1) & 3)
        self.assertEqual(types, {0, 1, 2})


class HuffmanTests(unittest.TestCase):
    def kraft(self, lengths):
        return sum(2 ** (15 - length) for length in lengths if length)

    def test_package_merge_gives_complete_limited_codes(self):
        r = support.rng("huffman")
        for _ in range(support.scaled(300)):
            size = r.choice([19, 30, 286])
            limit = 7 if size == 19 else 15
            freqs = [0] * size
            for s in r.sample(range(size), r.randint(2, size)):
                freqs[s] = r.choice([1, 1, 2, 3, r.randint(1, 10 ** r.randint(1, 6))])
            lengths = brisart_deflate._limited_lengths(freqs, limit)
            self.assertLessEqual(max(lengths), limit)
            self.assertEqual(self.kraft(lengths), 2 ** 15)
            self.assertEqual([bool(x) for x in lengths], [bool(f) for f in freqs])

    def test_fibonacci_frequencies_force_the_length_limit(self):
        fib = [1, 1]
        while len(fib) < 30:
            fib.append(fib[-1] + fib[-2])
        lengths = brisart_deflate._limited_lengths(fib, 15)
        self.assertEqual(max(lengths), 15)
        self.assertEqual(self.kraft(lengths), 2 ** 15)

    def test_package_merge_is_optimal_for_small_alphabets(self):
        r = support.rng("huffman-optimal")
        for _ in range(support.scaled(200)):
            freqs = [r.randint(1, 50) for _ in range(r.randint(2, 9))]
            lengths = brisart_deflate._limited_lengths(freqs, 15)
            nodes = sorted(freqs)                         # unrestricted Huffman cost for comparison
            cost = 0
            while len(nodes) > 1:
                a, b = nodes.pop(0), nodes.pop(0)
                cost += a + b
                nodes.append(a + b)
                nodes.sort()
            self.assertEqual(sum(f * l for f, l in zip(freqs, lengths)), cost)


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        r = support.rng("deflate-linear")
        text = (" ".join(r.choice(WORDS) for _ in range(40000))).encode()
        support.assert_roughly_linear(self, lambda k: text[:30_000 * k], lambda d: deflate(d, 1))
        support.assert_roughly_linear(self, lambda k: text[:15_000 * k], lambda d: deflate(d, 6))
        support.assert_roughly_linear(self, lambda k: support.random_bytes(r, 20_000 * k), lambda d: deflate(d, 6))
        support.assert_roughly_linear(self, lambda k: bytes(100_000 * k), lambda d: deflate(d, 9))


if __name__ == "__main__":
    unittest.main()
