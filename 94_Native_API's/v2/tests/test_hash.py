"""
File: v2/tests/test_hash.py

Purpose
-------
Verify v2/brisart_hash.py: NIST SHA-256 vectors (including one million
'a'), byte-for-byte agreement with hashlib across padding boundaries and
random chunking, streaming semantics, hashlib-style type checks, the
string-fingerprint injectivity fix and linear time.

Communication / relationships
-----------------------------
Standard library: unittest, hashlib (reference only), plus support.py in
this folder.
Verifies: v2/brisart_hash.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED. The
one-million-'a' vector costs a few seconds and always runs.

Edge cases
----------
Boundary lengths around 55/56/64 and their multiples; chunk sizes of 0
and 1; digest() between updates; a running length that wraps past
2**64 bits.

Known limitations
-----------------
Equivalence with hashlib is tested, not proven. No side-channel testing
is performed (the module does not claim resistance).

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_hash.py
"""

import hashlib
import unittest

import support
from brisart_hash import BrisartHash256, brisart_sha256, brisart_stable_hash


class ShaTests(unittest.TestCase):
    def test_nist_vectors(self):
        for message, digest in (
                (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
                (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
                (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
                 "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")):
            self.assertEqual(brisart_sha256(message).hexdigest(), digest)

    def test_one_million_a(self):
        h = BrisartHash256()
        for _ in range(1000):
            h.update(b"a" * 1000)
        self.assertEqual(h.hexdigest(), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")

    def test_matches_hashlib_at_every_boundary_and_with_random_chunks(self):
        r = support.rng("sha")
        for n in list(range(0, 200)) + [255, 256, 257, 511, 512, 513, 1023, 1024, 4097]:
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_sha256(data).hexdigest(), hashlib.sha256(data).hexdigest())
        for _ in range(support.scaled(40)):
            data = support.random_bytes(r, r.randint(0, 900))
            ours, ref = BrisartHash256(), hashlib.sha256()
            position = 0
            while position < len(data):
                step = r.choice([0, 1, 3, 63, 64, 65, 200])
                ours.update(data[position:position + step])
                ref.update(data[position:position + step])
                position += step
            self.assertEqual(ours.hexdigest(), ref.hexdigest())

    def test_streaming_semantics(self):
        h = BrisartHash256(b"a" * 70)
        clone = h.copy()
        h.update(b"more")
        self.assertEqual(clone.hexdigest(), hashlib.sha256(b"a" * 70).hexdigest())
        self.assertEqual(h.hexdigest(), hashlib.sha256(b"a" * 70 + b"more").hexdigest())
        self.assertEqual(h.hexdigest(), h.hexdigest())
        self.assertIs(h.update(b""), h)
        self.assertEqual((h.digest_size, h.block_size), (32, 64))

    def test_length_counter_wraps_modulo_2_to_the_64_bits(self):
        h = brisart_sha256(b"abc")
        h._total_length += 1 << 61
        self.assertEqual(h.digest(), brisart_sha256(b"abc").digest())

    def test_type_checks_match_hashlib(self):
        for bad in ("text", 5, None, 0, "", [1]):
            with self.assertRaises(TypeError):
                brisart_sha256(bad)
        for good in (bytearray(b"abc"), memoryview(b"abc")):
            self.assertEqual(brisart_sha256(good).hexdigest(), hashlib.sha256(b"abc").hexdigest())

    def test_stable_hash_is_injective_including_lone_surrogates(self):
        samples = ["?", "\ud800", "\udc00", "\ud83d\ude00", "\U0001f600", "\ufffd", "a?b", "a\ud800b"]
        self.assertEqual(len({brisart_stable_hash(s) for s in samples}), len(samples))
        self.assertEqual(brisart_stable_hash("abc"), hashlib.sha256(b"abc").hexdigest())
        with self.assertRaises(TypeError):
            brisart_stable_hash(b"abc")


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: b"x" * (30_000 * k), lambda b: brisart_sha256(b).digest())

        def tiny_updates(count):
            h = BrisartHash256()
            for _ in range(count):
                h.update(b"abc")
            h.digest()
        support.assert_roughly_linear(self, lambda k: 10_000 * k, tiny_updates)


if __name__ == "__main__":
    unittest.main()
