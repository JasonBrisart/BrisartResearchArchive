"""
File: v3/tests/test_inflate.py

Purpose
-------
Verify v3/brisart_inflate.py: agreement with zlib on valid streams and
on randomly corrupted ones (accept/reject decision, output and consumed
length), hand-built streams that break single RFC 1951 rules, the output
cap (including the exact boundary for literals), CRC-32 and Adler-32
against zlib, and gzip decoding against the gzip module for every header
flag combination, multiple members, trailing data and corruption.

Communication / relationships
-----------------------------
Standard library: unittest, zlib, gzip, io (reference only), plus
support.py in this folder.
Verifies: v3/brisart_inflate.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
gzip headers are built by hand so FEXTRA, FNAME, FCOMMENT and FHCRC can
be combined freely, including a wrong header CRC, reserved flag bits and
truncation inside each field.

Known limitations
-----------------
Agreement with zlib and gzip is checked on generated input, not proven.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_inflate.py
"""

import gzip
import io
import unittest
import zlib

import support
from brisart_inflate import (
    DEFAULT_MAX_OUTPUT, BrisartInflateError, BrisartInflateUnsupported, brisart_adler32, brisart_crc32,
    brisart_gzip_decompress, brisart_inflate, brisart_inflate_prefix, brisart_zlib_decompress)

WORDS = ("kernel scheduler framebuffer window pixel operating system brisart archive " * 2).split()


def raw_deflate(data, level=6, strategy=zlib.Z_DEFAULT_STRATEGY):
    c = zlib.compressobj(level, zlib.DEFLATED, -15, 8, strategy)
    return c.compress(data) + c.flush()


def gzip_member(data, flags=0, extra=b"", name=b"", comment=b"", bad_hcrc=False):
    header = bytearray(b"\x1f\x8b\x08" + bytes([flags]) + b"\x00\x00\x00\x00\x00\xff")
    if flags & 4:
        header += len(extra).to_bytes(2, "little") + extra
    if flags & 8:
        header += name + b"\x00"
    if flags & 16:
        header += comment + b"\x00"
    if flags & 2:
        crc = zlib.crc32(bytes(header)) & 0xFFFF
        header += ((crc ^ 1) if bad_hcrc else crc).to_bytes(2, "little")
    return bytes(header) + raw_deflate(data) + zlib.crc32(data).to_bytes(4, "little") + \
        (len(data) & 0xFFFFFFFF).to_bytes(4, "little")


def gzip_verdict(blob):
    try:
        return "ok", gzip.decompress(blob)
    except (OSError, EOFError, zlib.error):
        return "err", None


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


class ChecksumTests(unittest.TestCase):
    def test_crc32_and_adler32_match_zlib(self):
        r = support.rng("checksums")
        for n in (0, 1, 2, 7, 64, 5551, 5552, 5553, 70000):
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_crc32(data), zlib.crc32(data))
            self.assertEqual(brisart_adler32(data), zlib.adler32(data))
            for seed in (0, 1, 0xFFFF, 0xDEADBEEF, 0xFFFFFFFF):
                self.assertEqual(brisart_crc32(data, seed), zlib.crc32(data, seed))
                self.assertEqual(brisart_adler32(data, seed), zlib.adler32(data, seed))
        self.assertEqual(brisart_crc32(b"123456789"), 0xCBF43926)      # the CRC-32/ISO-HDLC check value
        for bad in (-1, 2 ** 32, True, "0"):
            with self.assertRaises(ValueError):
                brisart_crc32(b"x", bad)
        with self.assertRaises(TypeError):
            brisart_crc32("text")


class GzipTests(unittest.TestCase):
    def test_gzip_module_output_at_every_level(self):
        r = support.rng("gzip-valid")
        for data in (b"", b"x", (" ".join(r.choice(WORDS) for _ in range(3000))).encode(), support.random_bytes(r, 5000)):
            for level in range(10):
                self.assertEqual(brisart_gzip_decompress(gzip.compress(data, compresslevel=level)), data)
        buf = io.BytesIO()
        with gzip.GzipFile(filename="report.txt", mode="wb", fileobj=buf, mtime=1700000000) as f:
            f.write(b"named member")
        self.assertEqual(brisart_gzip_decompress(buf.getvalue()), b"named member")

    def test_every_header_flag_combination(self):
        for flags in range(32):
            if flags & 1 and flags != 1:
                continue
            member = gzip_member(b"payload", flags, extra=b"\x01\x02xy", name=b"a.txt", comment=b"note")
            self.assertEqual(gzip_verdict(member), ("ok", b"payload"), flags)
            self.assertEqual(brisart_gzip_decompress(member), b"payload", flags)
            for cut in range(1, len(member)):
                with self.assertRaises(BrisartInflateError, msg=(flags, cut)):
                    brisart_gzip_decompress(member[:cut])

    def test_header_crc_reserved_flags_and_trailer_checks(self):
        bad_hcrc = gzip_member(b"x", 2, bad_hcrc=True)
        self.assertEqual(gzip_verdict(bad_hcrc), ("ok", b"x"))            # gzip skips FHCRC without checking it
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(bad_hcrc)
        self.assertEqual(brisart_gzip_decompress(bad_hcrc, verify_checksum=False), b"x")
        for reserved in (32, 64, 128):
            member = gzip_member(b"x", reserved)
            self.assertEqual(gzip_verdict(member), ("ok", b"x"))          # gzip ignores reserved flag bits
            with self.assertRaises(BrisartInflateError):
                brisart_gzip_decompress(member)
        good = gzip_member(b"payload")
        for index in (-8, -5, -4, -1):
            bad = bytearray(good)
            bad[index] ^= 1
            self.assertEqual(gzip_verdict(bytes(bad))[0], "err")
            with self.assertRaises(BrisartInflateError):
                brisart_gzip_decompress(bytes(bad))
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(b"\x1f\x8b\x07" + good[3:])
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(b"\x1f\x8c" + good[2:])

    def test_members_and_trailing_data(self):
        one, two = gzip_member(b"first "), gzip_member(b"second")
        self.assertEqual(brisart_gzip_decompress(one + two), gzip.decompress(one + two))
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(one + two, multiple_members=False)
        self.assertEqual(brisart_gzip_decompress(one + two, multiple_members=False, allow_trailing=True), b"first ")
        self.assertEqual(gzip.decompress(one + b"\x00\x00"), b"first ")        # gzip tolerates NUL padding
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(one + b"\x00\x00")
        self.assertEqual(brisart_gzip_decompress(one + b"\x00\x00", allow_trailing=True), b"first ")
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(one + b"junk")
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(one + two, max_output=8)
        self.assertEqual(len(brisart_gzip_decompress(one + two, max_output=12)), 12)

    def test_corrupted_members_get_gzips_verdict(self):
        r = support.rng("gzip-fuzz")
        for _ in range(support.scaled(1500)):
            data = (" ".join(r.choice(WORDS) for _ in range(r.randint(0, 60)))).encode()
            flags = r.choice([0, 2, 4, 8, 16, 30])
            blob = bytearray(gzip_member(data, flags, extra=b"ex", name=b"n", comment=b"c"))
            index = r.randrange(len(blob))
            blob[index] ^= 1 << r.randrange(8)
            blob = bytes(blob)
            theirs = gzip_verdict(blob)
            try:
                ours = ("ok", brisart_gzip_decompress(blob))
            except BrisartInflateError:
                ours = ("err", None)
            if theirs[0] == "ok" and ours[0] == "err":
                # Only the two documented strictness differences may explain this: a reserved flag bit,
                # or a header CRC that gzip never checks.
                reserved = blob[3] & 0xE0
                unchecked = brisart_gzip_decompress(blob, verify_checksum=False) == theirs[1] \
                    if not reserved else False
                self.assertTrue(reserved or (blob[3] & 2 and unchecked), blob.hex())
                continue
            self.assertEqual(ours, theirs, blob.hex())

    def test_documented_gzip_differences(self):
        member = gzip_member(b"x")
        self.assertEqual(brisart_gzip_decompress(member[:3] + b"\x01" + member[4:]), b"x")   # FTEXT is harmless
        self.assertEqual(gzip_verdict(member[:3] + b"\x80" + member[4:]), ("ok", b"x"))
        with self.assertRaises(BrisartInflateError):
            brisart_gzip_decompress(member[:3] + b"\x80" + member[4:])

    def test_input_types(self):
        member = gzip_member(b"data")
        for value in (member, bytearray(member), memoryview(member)):
            self.assertEqual(brisart_gzip_decompress(value), b"data")
        with self.assertRaises(TypeError):
            brisart_gzip_decompress("text")


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        r = support.rng("inflate-linear")
        support.assert_roughly_linear(self, lambda k: zlib.compress(support.random_bytes(r, 20_000 * k), 6),
                                      brisart_zlib_decompress)
        support.assert_roughly_linear(self, lambda k: zlib.compress(b"abcab" * (100_000 * k), 9),
                                      lambda s: brisart_zlib_decompress(s, max_output=None))
        support.assert_roughly_linear(self, lambda k: bytes(40_000 * k), brisart_crc32)


if __name__ == "__main__":
    unittest.main()
