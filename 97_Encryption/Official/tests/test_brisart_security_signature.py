"""
File: tests/test_brisart_security_signature.py

Purpose
-------
Behaviour tests for the Ed25519 signature module
(brisart_security_signature.py): it reproduces the RFC 8032 section 7.1 test
vectors byte for byte, round-trips random keys and messages, rejects every
malformed, modified or malleated input without raising, takes new keys from the
project's entropy source, and, when an independent implementation is installed,
agrees with it.

Communication / relationships
-----------------------------
Imports brisart_security_signature.py and brisart_security_entropy.py (patches
``system_entropy`` as the signature module sees it). The optional cross-check
imports the third-party ``cryptography`` package only if it is installed; nothing
else in this suite needs it, and the other tests need only the standard library.

Settings / parameters
---------------------
VECTORS holds RFC 8032 section 7.1 TEST 1, TEST 2, TEST 3 and TEST SHA(abc)
as (seed, public key, message, signature) in hex. The random round-trip uses a
fixed ``random.Random`` seed so it is deterministic. L is the group order.

Edge cases
----------
Covers the empty message, messages of 1 to 1023 bytes, a signature whose S was
replaced by S + L (the malleated twin of a valid signature), a public key with
y >= p, a public key that is not on the curve, small-order public keys (the
identity and the point of order two, under which anyone could forge), wrong
lengths and types of key, message and signature, bytearray input, seeds of the
wrong length for signing, and a failing entropy health check during key
generation.

Known limitations
-----------------
Timing behaviour is not tested (Python integers are not constant-time; see the
module header). Agreement with an independent implementation is checked only
when ``cryptography`` is installed.

Examples
--------
    python -m unittest -v tests.test_brisart_security_signature
    python -m unittest discover -s tests -p "test_*.py"
"""
import hashlib
import random
import unittest
from unittest.mock import patch

import brisart_security_signature as ed25519
from brisart_security_entropy import BrisartEntropyError
from brisart_security_signature import BrisartSignatureError

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # optional: only the cross-check needs it
    Ed25519PrivateKey = None

VECTORS = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
    (
        "833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b58909351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704",
    ),
]
L = 2**252 + 27742317777372353535851937790883648493


def _vector(index):
    return tuple(bytes.fromhex(field) for field in VECTORS[index])


class Rfc8032VectorTests(unittest.TestCase):
    def test_every_rfc_vector_is_reproduced_exactly(self):
        for index in range(len(VECTORS)):
            with self.subTest(vector=index):
                seed, public, message, signature = _vector(index)
                self.assertEqual(ed25519.public_key(seed), public)
                self.assertEqual(ed25519.sign(seed, message), signature)
                self.assertIs(ed25519.verify(public, message, signature), True)

    def test_the_sha_abc_vector_signs_the_sha512_of_abc(self):
        self.assertEqual(_vector(3)[2], hashlib.sha512(b"abc").digest())

    def test_each_rfc_vector_is_refused_for_a_different_message_or_key(self):
        for index in range(len(VECTORS)):
            with self.subTest(vector=index):
                _, public, message, signature = _vector(index)
                self.assertIs(ed25519.verify(public, message + b"x", signature), False)
                other_public = _vector((index + 1) % len(VECTORS))[1]
                self.assertIs(ed25519.verify(other_public, message, signature), False)


class RoundTripTests(unittest.TestCase):
    def test_random_keys_and_messages_round_trip_and_any_change_is_refused(self):
        rng = random.Random(8032)
        for length in (0, 1, 31, 32, 64, 1023):
            with self.subTest(length=length):
                seed = bytes(rng.getrandbits(8) for _ in range(32))
                message = bytes(rng.getrandbits(8) for _ in range(length))
                public, signature = ed25519.public_key(seed), ed25519.sign(seed, message)
                self.assertIs(ed25519.verify(public, message, signature), True)
                self.assertIs(ed25519.verify(public, message + b"x", signature), False)
                for index in (0, 31, 32, 63):
                    flipped = bytearray(signature)
                    flipped[index] ^= 0x01
                    self.assertIs(ed25519.verify(public, message, bytes(flipped)), False)

    def test_signing_is_deterministic(self):
        seed = hashlib.sha256(b"deterministic").digest()
        self.assertEqual(ed25519.sign(seed, b"m"), ed25519.sign(seed, b"m"))

    def test_bytearray_input_is_accepted(self):
        seed, public, message, signature = _vector(1)
        self.assertIs(ed25519.verify(bytearray(public), message, bytearray(signature)), True)
        self.assertEqual(ed25519.sign(bytearray(seed), message), signature)


class RefusalTests(unittest.TestCase):
    def test_the_malleated_twin_of_a_valid_signature_is_refused(self):
        _, public, message, signature = _vector(0)
        s = int.from_bytes(signature[32:], "little")
        twin = signature[:32] + int.to_bytes(s + L, 32, "little")
        self.assertIs(ed25519.verify(public, message, twin), False)

    def test_public_keys_that_are_not_canonical_curve_points_are_refused(self):
        _, _, message, signature = _vector(0)
        for name, public in (
            ("y >= p", b"\xff" * 31 + b"\x7f"),
            ("not on the curve", (2).to_bytes(32, "little")),
        ):
            with self.subTest(public=name):
                self.assertIs(ed25519.verify(public, message, signature), False)

    def test_a_non_canonical_point_encoding_is_not_decoded(self):
        # y = p + 1 encodes the same point as y = 1 but is not the canonical encoding.
        self.assertIsNone(ed25519._decompress((ed25519._P + 1).to_bytes(32, "little")))
        self.assertIsNotNone(ed25519._decompress((1).to_bytes(32, "little")))

    def test_a_small_order_public_key_is_refused_though_the_equation_would_hold(self):
        # Under the identity key (y = 1), R = [k]B with S = k satisfies the verification
        # equation for ANY message, so anyone could forge; verify() must not trust such a key.
        k = 5
        r = ed25519._compress(ed25519._multiply(k, ed25519._G))
        forged = r + k.to_bytes(32, "little")
        identity = (1).to_bytes(32, "little")
        order_two = (ed25519._P - 1).to_bytes(32, "little")
        for name, public in (("identity", identity), ("order two", order_two)):
            with self.subTest(public=name):
                self.assertIs(ed25519.verify(public, b"any message", forged), False)

    def test_valid_public_keys_are_never_small_order(self):
        for index in range(len(VECTORS)):
            with self.subTest(vector=index):
                point = ed25519._decompress(_vector(index)[1])
                self.assertFalse(ed25519._is_small_order(point))

    def test_a_signature_whose_r_is_not_a_curve_point_is_refused(self):
        _, public, message, signature = _vector(0)
        broken = (2).to_bytes(32, "little") + signature[32:]
        self.assertIs(ed25519.verify(public, message, broken), False)

    def test_malformed_input_is_refused_without_raising(self):
        good_public, good_signature = b"\x00" * 32, b"\x00" * 64
        cases = (
            (b"\x00" * 31, b"", good_signature),
            (good_public, b"", b"\x00" * 63),
            ("text", b"", good_signature),
            (good_public, b"", None),
            (None, b"", good_signature),
            (good_public, None, good_signature),
            (good_public, "text", good_signature),
        )
        for index, (public, message, signature) in enumerate(cases):
            with self.subTest(case=index):
                self.assertIs(ed25519.verify(public, message, signature), False)

    def test_signing_needs_a_32_byte_seed(self):
        for bad in (b"", b"short", bytes(33), "not bytes", None, 7):
            with self.subTest(seed=bad):
                with self.assertRaises(BrisartSignatureError):
                    ed25519.sign(bad, b"m")
                with self.assertRaises(BrisartSignatureError):
                    ed25519.public_key(bad)


class KeyGenerationTests(unittest.TestCase):
    def test_a_new_seed_is_32_bytes_and_different_each_time(self):
        first, second = ed25519.generate_seed(), ed25519.generate_seed()
        self.assertEqual((len(first), len(second)), (32, 32))
        self.assertNotEqual(first, second)
        self.assertIs(ed25519.verify(ed25519.public_key(first), b"m", ed25519.sign(first, b"m")), True)

    def test_a_new_seed_comes_from_the_project_entropy_source(self):
        fixed = bytes(range(32))
        with patch.object(ed25519, "system_entropy", return_value=fixed) as source:
            self.assertEqual(ed25519.generate_seed(), fixed)
        source.assert_called_once_with(32)

    def test_a_failed_entropy_health_check_is_reported_not_swallowed(self):
        with patch.object(ed25519, "system_entropy", side_effect=BrisartEntropyError("stuck source")):
            with self.assertRaises(BrisartSignatureError) as caught:
                ed25519.generate_seed()
        self.assertIsInstance(caught.exception.__cause__, BrisartEntropyError)


@unittest.skipIf(Ed25519PrivateKey is None, "the optional 'cryptography' package is not installed")
class IndependentImplementationTests(unittest.TestCase):
    def test_keys_and_signatures_agree_with_the_cryptography_package(self):
        rng = random.Random(25519)
        for _ in range(25):
            seed = bytes(rng.getrandbits(8) for _ in range(32))
            message = bytes(rng.getrandbits(8) for _ in range(rng.randrange(200)))
            reference = Ed25519PrivateKey.from_private_bytes(seed)
            self.assertEqual(reference.sign(message), ed25519.sign(seed, message))
            reference.public_key().verify(ed25519.sign(seed, message), message)


if __name__ == "__main__":
    unittest.main()
