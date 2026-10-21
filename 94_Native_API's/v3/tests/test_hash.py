"""
File: v3/tests/test_hash.py

Purpose
-------
Verify v3/brisart_hash.py: NIST SHA-256 and SHA-224 vectors (including
one million 'a'), byte-for-byte agreement with hashlib across padding
boundaries and random chunking, HMAC against RFC 4231 and the hmac
module, the non-short-circuiting comparison, the string-fingerprint
injectivity fix and linear time.

Communication / relationships
-----------------------------
Standard library: unittest, hashlib and hmac (reference only), plus
support.py in this folder.
Verifies: v3/brisart_hash.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED. The
one-million-'a' SHA-256 vector costs a few seconds and always runs.

Edge cases
----------
HMAC keys shorter than, equal to and longer than the 64-byte block;
empty keys and messages; copy() before and after updates.

Known limitations
-----------------
No timing side-channel measurement of brisart_compare_digest is
attempted; only its result and its no-early-exit structure are checked.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_hash.py
"""

import hashlib
import hmac
import inspect
import unittest

import support
from brisart_hash import (
    BrisartHash224, BrisartHash256, BrisartHMAC, brisart_compare_digest, brisart_hmac, brisart_sha224,
    brisart_sha256, brisart_stable_hash)

RFC4231 = [  # (key, data, sha224, sha256) for test cases 1-4, 6 and 7
    (b"\x0b" * 20, b"Hi There",
     "896fb1128abbdf196832107cd49df33f47b4b1169912ba4f53684b22",
     "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"),
    (b"Jefe", b"what do ya want for nothing?",
     "a30e01098bc6dbbf45690f3a7e9e6d0f8bbea2a39e6148008fd05e44",
     "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"),
    (b"\xaa" * 20, b"\xdd" * 50,
     "7fb3cb3588c6c1f6ffa9694d7d6ad2649365b0c1f65d69d1ec8333ea",
     "773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe"),
    (bytes(range(1, 26)), b"\xcd" * 50,
     "6c11506874013cac6a2abc1bb382627cec6a90d86efc012de7afec5a",
     "82558a389a443c0ea4cc819899f2083a85f0faa3e578f8077a2e3ff46729665b"),
    (b"\xaa" * 131, b"Test Using Larger Than Block-Size Key - Hash Key First",
     "95e9a0db962095adaebe9b2d6f0dbce2d499f112f2d2b7273fa6870e",
     "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"),
    (b"\xaa" * 131, b"This is a test using a larger than block-size key and a larger than block-size data. "
                    b"The key needs to be hashed before being used by the HMAC algorithm.",
     "3a854166ac5d9f023f54d517d0b39dbd946770db9c2b95c9f6f565d1",
     "9b09ffa71b942fcb27635fbcd5b0e944bfdc63644f0713938a7f51535c3a35e2"),
]


class ShaTests(unittest.TestCase):
    def test_nist_vectors(self):
        cases = [(b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                  "d14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f"),
                 (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                  "23097d223405d8228642a477bda255b32aadbce4bda0b3f7e36c9da7"),
                 (b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
                  "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
                  "75388b16512776cc5dba5da1fd890150b0c6455cb4f58b1952522525")]
        for message, sha256, sha224 in cases:
            self.assertEqual(brisart_sha256(message).hexdigest(), sha256)
            self.assertEqual(brisart_sha224(message).hexdigest(), sha224)

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
            self.assertEqual(brisart_sha224(data).hexdigest(), hashlib.sha224(data).hexdigest())
        for _ in range(support.scaled(40)):
            data = support.random_bytes(r, r.randint(0, 900))
            for ours, ref in ((BrisartHash256(), hashlib.sha256()), (BrisartHash224(), hashlib.sha224())):
                position = 0
                while position < len(data):
                    step = r.choice([0, 1, 3, 63, 64, 65, 200])
                    ours.update(data[position:position + step])
                    ref.update(data[position:position + step])
                    position += step
                self.assertEqual(ours.hexdigest(), ref.hexdigest())

    def test_streaming_semantics(self):
        for factory, ref in ((BrisartHash256, hashlib.sha256), (BrisartHash224, hashlib.sha224)):
            h = factory(b"a" * 70)
            clone = h.copy()
            self.assertIs(type(clone), factory)
            h.update(b"more")
            self.assertEqual(clone.hexdigest(), ref(b"a" * 70).hexdigest())
            self.assertEqual(h.hexdigest(), ref(b"a" * 70 + b"more").hexdigest())
            self.assertEqual(h.hexdigest(), h.hexdigest())
        self.assertEqual((BrisartHash224.digest_size, BrisartHash224.block_size), (28, 64))
        self.assertEqual(len(brisart_sha224(b"x").digest()), 28)

    def test_type_checks_match_hashlib(self):
        for bad in ("text", 5, None, 0, "", [1]):
            with self.assertRaises(TypeError):
                brisart_sha256(bad)
            with self.assertRaises(TypeError):
                brisart_sha224(bad)

    def test_stable_hash_is_injective_including_lone_surrogates(self):
        samples = ["?", "\ud800", "\udc00", "\ud83d\ude00", "\U0001f600", "\ufffd", "a?b", "a\ud800b"]
        self.assertEqual(len({brisart_stable_hash(s) for s in samples}), len(samples))
        self.assertEqual(brisart_stable_hash("abc"), hashlib.sha256(b"abc").hexdigest())


class HmacTests(unittest.TestCase):
    def test_rfc4231_vectors(self):
        for key, data, sha224, sha256 in RFC4231:
            self.assertEqual(brisart_hmac(key, data, "sha224").hexdigest(), sha224)
            self.assertEqual(brisart_hmac(key, data).hexdigest(), sha256)

    def test_rfc4231_truncated_case_5(self):
        mac = brisart_hmac(b"\x0c" * 20, b"Test With Truncation").hexdigest()
        self.assertEqual(mac[:32], "a3b6167473100ee06e0c796c2955552b")

    def test_matches_hmac_module(self):
        r = support.rng("hmac")
        for _ in range(support.scaled(150)):
            key = support.random_bytes(r, r.choice([0, 1, 20, 63, 64, 65, 200]))
            msg = support.random_bytes(r, r.randint(0, 300))
            for name in ("sha256", "sha224"):
                self.assertEqual(brisart_hmac(key, msg, name).digest(), hmac.new(key, msg, name).digest())

    def test_streaming_and_copy(self):
        mac = brisart_hmac(b"key", b"part one ")
        clone = mac.copy()
        mac.update(b"part two")
        self.assertEqual(mac.hexdigest(), hmac.new(b"key", b"part one part two", "sha256").hexdigest())
        self.assertEqual(clone.hexdigest(), hmac.new(b"key", b"part one ", "sha256").hexdigest())
        self.assertEqual(mac.hexdigest(), mac.hexdigest())
        self.assertEqual(mac.digest_size, 32)
        self.assertEqual(BrisartHMAC(b"k", digestmod=BrisartHash224).digest_size, 28)

    def test_argument_validation(self):
        with self.assertRaises(TypeError):
            brisart_hmac("text key", b"m")
        for bad in ("md5", "sha1", "sha512", hashlib.sha256, 5):
            with self.assertRaises(ValueError):
                brisart_hmac(b"k", b"m", bad)
        with self.assertRaises(TypeError):
            brisart_hmac(b"k", "text message")


class CompareDigestTests(unittest.TestCase):
    def test_results_match_hmac_compare_digest(self):
        r = support.rng("compare")
        for _ in range(support.scaled(2000)):
            a = support.random_bytes(r, r.randint(0, 6))
            b = a if r.random() < 0.3 else support.random_bytes(r, r.randint(0, 6))
            self.assertEqual(brisart_compare_digest(a, b), hmac.compare_digest(a, b))
            self.assertEqual(brisart_compare_digest(a.hex(), b.hex()), hmac.compare_digest(a.hex(), b.hex()))
            self.assertEqual(brisart_compare_digest(bytearray(a), memoryview(b)), a == b)

    def test_type_rules_match_hmac_compare_digest(self):
        for a, b in ((b"a", "a"), ("a", b"a"), ("\u00e9", "\u00e9"), (5, 5)):
            with self.assertRaises(TypeError):
                brisart_compare_digest(a, b)
            with self.assertRaises(TypeError):
                hmac.compare_digest(a, b)

    def test_has_no_early_exit(self):
        source = inspect.getsource(brisart_compare_digest)
        self.assertNotIn("return False", source)
        self.assertNotIn("break", source)


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: b"x" * (30_000 * k), lambda b: brisart_sha256(b).digest())
        support.assert_roughly_linear(self, lambda k: b"x" * (30_000 * k), lambda b: brisart_hmac(b"k", b).digest())


if __name__ == "__main__":
    unittest.main()
