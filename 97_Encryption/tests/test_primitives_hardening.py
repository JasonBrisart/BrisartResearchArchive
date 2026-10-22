"""
File: tests/test_primitives_hardening.py

Purpose
-------
Guard the 0.4.0 changes to brisart_security_primitives.py: the precomputed
round schedule must be bit-identical to the reference round function from
Alpha 3, the cached domain initial states must not be mutable from outside,
the big-integer XOR must match byte-wise XOR, and the new type/range
validation must reject booleans, floats, out-of-range words and oversize
requests.

Communication / relationships
-----------------------------
Imports brisart_security_primitives.py only. ``reference_permute`` below is a
verbatim copy of the Alpha 3 loop and acts as the oracle.

Settings / parameters
---------------------
Random states come from ``random.Random(20261022)`` so failures reproduce.

Edge cases
----------
Round counts 1..40 cross the 24-constant and 8-rotation periods; the 192-round
schedule period is crossed once with rounds=200.

Known limitations
-----------------
Equivalence is sampled, not proven; the frozen KATs add a second check.

Examples
--------
    python -m unittest -v tests.test_primitives_hardening
"""
import random
import unittest

import brisart_security_primitives as P
from brisart_security_primitives import (
    MASK64,
    BrisartPrimitiveError,
    derive_password_key,
    keyed_mac,
    permute,
    permute_unchecked,
    sponge_hash,
    stream_bytes,
    wipe,
    xor_bytes,
)


def reference_permute(state, rounds):
    for round_index in range(rounds):
        constant = P.ROUND_CONSTANTS[round_index % len(P.ROUND_CONSTANTS)]
        state[0] ^= constant
        state[15] ^= ((round_index + 1) * P.ROUND_INDEX_CONSTANT) & MASK64
        for index in range(0, 16, 2):
            P._mix_pair(state, index, index + 1, P.ROTATIONS[(index // 2) % 8])
        for index in range(8):
            P._mix_pair(state, index, index + 8, P.ROTATIONS[(index + round_index) % 8])
        for index in range(0, 16, 2):
            P._mix_pair(state, index, index + 1, P.ROTATIONS[(index // 2 + 3) % 8])
        state[:] = [state[index] for index in P.WORD_PERMUTATION]
        snapshot = state[:]
        for index in range(16):
            neighbor_mix = (snapshot[(index + 1) % 16] & snapshot[(index + 2) % 16]) ^ (
                (~snapshot[(index + 3) % 16]) & snapshot[(index + 5) % 16]
            )
            state[index] ^= P.rotate_left(neighbor_mix, P.ROTATIONS[(index + round_index) % 8])
            state[index] = (
                state[index]
                + P.rotate_left(constant ^ (index * P.LANE_INDEX_CONSTANT), (index * 7 + round_index) % 64)
            ) & MASK64


class PermutationEquivalenceTests(unittest.TestCase):
    def test_fast_schedule_matches_reference(self) -> None:
        rng = random.Random(20261022)
        for rounds in list(range(1, 41)) + [200]:
            for _ in range(3):
                state = [rng.getrandbits(64) for _ in range(16)]
                expected = state[:]
                reference_permute(expected, rounds)
                actual = state[:]
                permute_unchecked(actual, rounds)
                self.assertEqual(actual, expected, f"rounds={rounds}")

    def test_extreme_states_match_reference(self) -> None:
        for state in ([0] * 16, [MASK64] * 16, [1 << 63] * 16):
            expected = state[:]
            reference_permute(expected, 32)
            actual = state[:]
            permute(actual)
            self.assertEqual(actual, expected)


class ValidationTests(unittest.TestCase):
    def test_permute_rejects_bad_words_and_types(self) -> None:
        for state in ([0] * 15 + [-1], [0] * 15 + [1 << 64], [0] * 15 + [1.0], (0,) * 16):
            with self.subTest(state=state[-1]):
                with self.assertRaises(BrisartPrimitiveError):
                    permute(state)
        with self.assertRaises(BrisartPrimitiveError):
            permute([0] * 16, True)
        with self.assertRaises(BrisartPrimitiveError):
            permute([0] * 16, 2.0)

    def test_sponge_rejects_bool_and_non_bytes(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            sponge_hash(b"m", True)
        with self.assertRaises(BrisartPrimitiveError):
            sponge_hash("text")
        with self.assertRaises(BrisartPrimitiveError):
            sponge_hash(b"m", 32, "domain")

    def test_mac_rejects_non_bytes_message(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            keyed_mac(bytes(32), "message")

    def test_stream_limits(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            stream_bytes(bytes(32), bytes(32), True)
        with self.assertRaises(BrisartPrimitiveError):
            stream_bytes(bytes(32), bytes(32), P.MAX_STREAM_BYTES + 1)
        with self.assertRaises(BrisartPrimitiveError):
            stream_bytes(bytes(32), "nonce", 4)
        self.assertEqual(stream_bytes(bytes(32), bytes(32), 0), b"")

    def test_legacy_kdf_bounds_fail_before_work(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            derive_password_key("pw", bytes(16), iterations=P.MAX_LEGACY_KDF_ITERATIONS + 1)
        with self.assertRaises(BrisartPrimitiveError):
            derive_password_key("pw", bytes(16), iterations=True)
        with self.assertRaises(BrisartPrimitiveError):
            derive_password_key("pw\ud800", bytes(16), iterations=10_000)

    def test_xor_matches_bytewise(self) -> None:
        rng = random.Random(7)
        for size in (0, 1, 31, 32, 1000):
            left = bytes(rng.getrandbits(8) for _ in range(size))
            right = bytes(rng.getrandbits(8) for _ in range(size))
            self.assertEqual(xor_bytes(left, right), bytes(a ^ b for a, b in zip(left, right)))
        with self.assertRaises(BrisartPrimitiveError):
            xor_bytes("ab", "cd")

    def test_initial_state_cache_is_isolated(self) -> None:
        first = P._initial_state(b"BSR2/test/cache")
        first[0] ^= 1
        second = P._initial_state(b"BSR2/test/cache")
        self.assertNotEqual(first[0], second[0])
        self.assertEqual(sponge_hash(b"x", domain=b"BSR2/test/cache"), sponge_hash(b"x", domain=b"BSR2/test/cache"))

    def test_wipe(self) -> None:
        buffer = bytearray(b"secret")
        wipe(buffer)
        self.assertEqual(buffer, bytearray(6))
        with self.assertRaises(BrisartPrimitiveError):
            wipe(b"immutable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
