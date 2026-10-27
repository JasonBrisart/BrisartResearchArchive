"""
File: tests/test_sponge64.py

Purpose
-------
Behavioural tests for BSR2-S64 (brisart_security_sponge.py): incremental
absorption equals one-shot absorption, squeezing in pieces equals one squeeze,
domains and framing separate inputs, padding distinguishes trailing 0x80, the
IV tweak separates S64 from the legacy sponge, and keyed modes validate
their inputs.

Communication / relationships
-----------------------------
Imports brisart_security_sponge.py and ``sponge_hash`` from
brisart_security_primitives.py for the separation check.

Settings / parameters
---------------------
Fixed keys bytes(32)/bytes(range(32)); split points cover the 64-byte rate.

Edge cases
----------
Empty input, exactly-one-block input, 63/64/65-byte boundaries, zero-length
keystream, absorb-after-squeeze, and pickling refusal.

Known limitations
-----------------
Structural behaviour only; no statistical or cryptanalytic claim.

Examples
--------
    python -m unittest -v tests.test_sponge64
"""
import pickle
import unittest

from brisart_security_primitives import BrisartPrimitiveError, sponge_hash
from brisart_security_sponge import Sponge64, derive_keys64, hash64, keystream64, mac64


class Sponge64Tests(unittest.TestCase):
    def test_incremental_absorb_matches_one_shot(self) -> None:
        data = bytes(range(256)) * 3
        expected = hash64(data, b"BSR2/test", 64)
        for split in (0, 1, 63, 64, 65, 500):
            sponge = Sponge64(b"BSR2/test")
            sponge.absorb(data[:split]).absorb(data[split:])
            self.assertEqual(sponge.squeeze(64), expected)

    def test_piecewise_squeeze_matches_single(self) -> None:
        whole = Sponge64(b"BSR2/test").absorb(b"x").squeeze(300)
        sponge = Sponge64(b"BSR2/test").absorb(b"x")
        parts = sponge.squeeze(1) + sponge.squeeze(63) + sponge.squeeze(64) + sponge.squeeze(172)
        self.assertEqual(parts, whole)

    def test_boundaries_and_padding(self) -> None:
        outputs = {hash64(b"\x00" * n, b"BSR2/test") for n in (0, 1, 62, 63, 64, 65, 128)}
        self.assertEqual(len(outputs), 7)
        self.assertNotEqual(hash64(b"", b"BSR2/test"), hash64(b"\x80", b"BSR2/test"))

    def test_domain_and_framing_separation(self) -> None:
        self.assertNotEqual(hash64(b"m", b"BSR2/a"), hash64(b"m", b"BSR2/b"))
        key = bytes(range(32))
        self.assertNotEqual(mac64(key, b"BSR2/t", b"ab", b"c"), mac64(key, b"BSR2/t", b"a", b"bc"))

    def test_separated_from_legacy_sponge(self) -> None:
        self.assertNotEqual(hash64(b"m", b"BSR2/hash", 32), sponge_hash(b"m", 32, b"BSR2/hash"))

    def test_keystream(self) -> None:
        key = bytes(range(32))
        self.assertEqual(keystream64(key, b"n", 0), b"")
        long = keystream64(key, b"n", 300)
        self.assertEqual(keystream64(key, b"n", 100), long[:100])
        self.assertNotEqual(keystream64(key, b"m", 100), long[:100])
        with self.assertRaises(BrisartPrimitiveError):
            keystream64(key, b"n", -1)
        with self.assertRaises(BrisartPrimitiveError):
            keystream64(bytes(8), b"n", 1)

    def test_derive_keys(self) -> None:
        keys = derive_keys64(bytes(range(32)), b"BSR2/t", b"x", count=3)
        self.assertEqual(len(set(keys)), 3)
        self.assertTrue(all(len(k) == 32 for k in keys))
        with self.assertRaises(BrisartPrimitiveError):
            derive_keys64(bytes(range(32)), b"BSR2/t", count=0)

    def test_state_rules(self) -> None:
        sponge = Sponge64(b"BSR2/test")
        sponge.squeeze(8)
        with self.assertRaises(BrisartPrimitiveError):
            sponge.absorb(b"late")
        with self.assertRaises(TypeError):
            pickle.dumps(sponge)
        with self.assertRaises(BrisartPrimitiveError):
            Sponge64(b"")
        with self.assertRaises(BrisartPrimitiveError):
            sponge.squeeze(True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
