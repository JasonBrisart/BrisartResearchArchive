"""
File: v1/tests/test_hash.py

Purpose
-------
Characterise v1/brisart_hash.py: NIST SHA-256 vectors, agreement with
hashlib across padding boundaries and random chunking, streaming
semantics, the embedded self-test, and the known defects that v2 fixed.

Communication / relationships
-----------------------------
Standard library: unittest, hashlib (reference only), plus support.py in
this folder.
Verifies: v1/brisart_hash.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Boundary lengths 55, 56, 63, 64, 65, 119 and 128; chunk sizes down to 1;
digest() between updates. v1's constructor parameter is named
initial_data (v2 renamed it to data).

Known limitations
-----------------
v1 SHA-256 is slow (about 200 KB/s), so inputs are kept small.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_hash.py
"""

import hashlib
import unittest

import support
import brisart_hash
from brisart_hash import BrisartHash256, brisart_sha256, brisart_stable_hash


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_hash._self_test()

    def test_matches_hashlib_at_boundaries(self):
        r = support.rng("v1-sha")
        for n in list(range(0, 140)) + [255, 256, 257, 1000]:
            data = support.random_bytes(r, n)
            self.assertEqual(brisart_sha256(data).hexdigest(), hashlib.sha256(data).hexdigest(), n)

    def test_random_chunking(self):
        r = support.rng("v1-sha-chunk")
        for _ in range(support.scaled(20)):
            data = support.random_bytes(r, r.randint(0, 400))
            h, ref = BrisartHash256(), hashlib.sha256()
            position = 0
            while position < len(data):
                step = r.choice([1, 3, 63, 64, 65, 100])
                h.update(data[position:position + step])
                ref.update(data[position:position + step])
                position += step
            self.assertEqual(h.hexdigest(), ref.hexdigest())

    def test_streaming_semantics(self):
        h = BrisartHash256(initial_data=b"a" * 70)
        clone = h.copy()
        h.update(b"more")
        self.assertEqual(clone.hexdigest(), hashlib.sha256(b"a" * 70).hexdigest())
        self.assertEqual(h.hexdigest(), h.hexdigest())
        self.assertEqual((h.digest_size, h.block_size), (32, 64))
        with self.assertRaises(TypeError):
            h.update("text")

    def test_stable_hash_of_ordinary_text(self):
        for text in ("", "abc", "h\u00e9llo", "\U0001f600"):
            self.assertEqual(brisart_stable_hash(text), hashlib.sha256(text.encode("utf-8")).hexdigest())


class KnownDefectTests(unittest.TestCase):
    def test_H1_lone_surrogate_collides_with_question_mark(self):
        self.assertEqual(brisart_stable_hash("\ud800"), brisart_stable_hash("?"))

    def test_H2_falsy_non_bytes_input_is_accepted(self):
        empty = hashlib.sha256(b"").hexdigest()
        self.assertEqual(brisart_sha256(None).hexdigest(), empty)
        self.assertEqual(brisart_sha256(0).hexdigest(), empty)


if __name__ == "__main__":
    unittest.main()
