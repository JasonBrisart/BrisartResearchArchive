"""
File: tests/test_aead_v3.py

Purpose
-------
Security-behaviour tests for the version 3 sealed format
(brisart_security_aead.py): round trips under every padding policy; binding of
context, associated data, key, and every header byte; truncation and extension;
canonical padding; reserved bits; size limits; armor; and, most importantly,
nonce-misuse resistance when the randomizer repeats (the scenario that broke
Alpha 2 and that Alpha 3 only mitigated).

Communication / relationships
-----------------------------
Imports brisart_security_aead.py and brisart_security_drbg.py; patches
``aead_module.system_entropy`` to force randomizer reuse.

Settings / parameters
---------------------
KEY = bytes(range(32)); CONTEXT = "aead:test"; AD = b"associated".

Edge cases
----------
Flips one bit in every byte position of a short sealed message and expects
rejection for all of them.

Known limitations
-----------------
Behavioural evidence only; the construction has not been analysed.

Examples
--------
    python -m unittest -v tests.test_aead_v3
"""
import unittest
from unittest.mock import patch

import brisart_security_aead as aead_module
from brisart_security_aead import (
    HEADER_BYTES,
    BrisartSealError,
    armor,
    dearmor,
    inspect_sealed,
    padme_length,
    seal,
    unseal,
)
from brisart_security_drbg import BrisartDRBG

KEY = bytes(range(32))
CONTEXT = "aead:test"
AD = b"associated"


class SealedFormatTests(unittest.TestCase):
    def test_round_trip_all_paddings_and_sizes(self) -> None:
        for padding in ("none", "padme", "block"):
            for size in (0, 1, 55, 56, 57, 300):
                with self.subTest(padding=padding, size=size):
                    plaintext = bytes(range(256))[:size] if size <= 256 else b"p" * size
                    blob = seal(KEY, plaintext, CONTEXT, associated_data=AD, padding=padding)
                    self.assertEqual(unseal(KEY, blob, CONTEXT, associated_data=AD), plaintext)
                    self.assertEqual(inspect_sealed(blob)["padding"], padding)

    def test_padding_hides_exact_length(self) -> None:
        a = seal(KEY, b"a" * 1000, CONTEXT, padding="padme")
        b = seal(KEY, b"a" * 1010, CONTEXT, padding="padme")
        self.assertEqual(len(a), len(b))
        self.assertEqual(padme_length(1008), 1024)

    def test_every_byte_is_authenticated(self) -> None:
        blob = seal(KEY, b"short message", CONTEXT, associated_data=AD)
        for index in range(len(blob)):
            changed = bytearray(blob)
            changed[index] ^= 0x01
            with self.subTest(index=index):
                with self.assertRaises(BrisartSealError):
                    unseal(KEY, bytes(changed), CONTEXT, associated_data=AD)

    def test_binding_and_truncation(self) -> None:
        blob = seal(KEY, b"bound", CONTEXT, associated_data=AD)
        cases = {
            "wrong key": lambda: unseal(bytes(reversed(KEY)), blob, CONTEXT, associated_data=AD),
            "wrong context": lambda: unseal(KEY, blob, CONTEXT + "x", associated_data=AD),
            "wrong ad": lambda: unseal(KEY, blob, CONTEXT, associated_data=AD + b"x"),
            "missing ad": lambda: unseal(KEY, blob, CONTEXT),
            "truncated": lambda: unseal(KEY, blob[:-1], CONTEXT, associated_data=AD),
            "extended": lambda: unseal(KEY, blob + b"\x00", CONTEXT, associated_data=AD),
            "header only": lambda: unseal(KEY, blob[:HEADER_BYTES], CONTEXT, associated_data=AD),
        }
        for name, action in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(BrisartSealError):
                    action()

    def test_errors_do_not_distinguish_key_from_tamper(self) -> None:
        blob = seal(KEY, b"oracle", CONTEXT)
        messages = set()
        for action in (
            lambda: unseal(bytes(reversed(KEY)), blob, CONTEXT),
            lambda: unseal(KEY, blob[:-1] + bytes([blob[-1] ^ 1]), CONTEXT),
            lambda: unseal(KEY, blob, "other"),
        ):
            with self.assertRaises(BrisartSealError) as captured:
                action()
            messages.add(str(captured.exception))
        self.assertEqual(messages, {"authentication failed"})

    def test_reserved_and_unknown_header_values(self) -> None:
        blob = seal(KEY, b"x", CONTEXT)
        for index, value in ((4, 9), (5, 9), (6, 1), (7, 7), (0, 0)):
            changed = bytearray(blob)
            changed[index] = value
            with self.subTest(index=index):
                with self.assertRaises(BrisartSealError):
                    inspect_sealed(bytes(changed))

    def test_randomizer_reuse_is_misuse_resistant(self) -> None:
        fixed = bytes(range(32))
        with patch.object(aead_module, "system_entropy", return_value=fixed):
            first = seal(KEY, b"attack at dawn!!", CONTEXT, rng=BrisartDRBG(bytes(64), b"BSR2 misuse test"))
            second = seal(KEY, b"retreat at dusk!", CONTEXT, rng=BrisartDRBG(bytes(64), b"BSR2 misuse test"))
            third = seal(KEY, b"attack at dawn!!", CONTEXT, rng=BrisartDRBG(bytes(64), b"BSR2 misuse test"))
        self.assertEqual(first[:40], second[:40])
        c1, c2 = first[HEADER_BYTES:], second[HEADER_BYTES:]
        recovered = bytes(a ^ b ^ k for a, b, k in zip(c1[8:], c2[8:], b"attack at dawn!!"))
        self.assertNotEqual(recovered, b"retreat at dusk!")
        self.assertEqual(first, third)
        self.assertEqual(unseal(KEY, second, CONTEXT), b"retreat at dusk!")

    def test_input_validation(self) -> None:
        for action in (
            lambda: seal(b"short", b"x", CONTEXT),
            lambda: seal(KEY, "text", CONTEXT),
            lambda: seal(KEY, b"x", ""),
            lambda: seal(KEY, b"x", CONTEXT, associated_data="ad"),
            lambda: seal(KEY, b"x", CONTEXT, padding="random"),
            lambda: seal(KEY, b"x", "bad\ud800"),
            lambda: unseal(KEY, "blob", CONTEXT),
            lambda: unseal(KEY, seal(KEY, b"x" * 10, CONTEXT), CONTEXT, max_plaintext_bytes=5),
        ):
            with self.assertRaises(BrisartSealError):
                action()

    def test_rng_contribution_is_validated(self) -> None:
        class Bad:
            def generate(self, length, additional_input):
                return b"x" * (length - 1)

        with self.assertRaises(BrisartSealError):
            seal(KEY, b"x", CONTEXT, rng=Bad())

    def test_armor_round_trip_and_checksum(self) -> None:
        blob = seal(KEY, b"armored", CONTEXT)
        text = armor(blob)
        self.assertEqual(dearmor(text), blob)
        lines = text.splitlines()
        lines[1] = ("0" if lines[1][0] != "0" else "1") + lines[1][1:]
        with self.assertRaises(BrisartSealError):
            dearmor("\n".join(lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
