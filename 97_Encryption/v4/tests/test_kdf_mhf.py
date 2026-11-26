"""
File: tests/test_kdf_mhf.py

Purpose
-------
Tests for BSR2-MHF-1 (brisart_security_kdf.py): determinism; sensitivity to
password, salt, memory, passes and output length; Unicode NFC normalisation;
parameter validation and the fixed 73-byte encoding; and the decode-time
ceilings that stop hostile headers from forcing huge work.

Communication / relationships
-----------------------------
Imports brisart_security_kdf.py only.

Settings / parameters
---------------------
All derivations use memory_blocks=64 (the test floor) to stay fast.

Edge cases
----------
Non-power-of-two memory, bool/float parameters, unknown round count, short
salt, non-zero salt filler bytes, unknown KDF id, empty/oversize passwords.

Known limitations
-----------------
Does not measure memory-hardness or time-memory trade-off resistance.

Examples
--------
    python -m unittest -v tests.test_kdf_mhf
"""
import unittest

from brisart_security_kdf import MAX_PASSWORD_BYTES, BrisartKdfError, KdfParams, derive_key, new_params

SALT = bytes(range(32))


def params(**overrides) -> KdfParams:
    values = {"memory_blocks": 64, "passes": 1, "salt": SALT}
    values.update(overrides)
    return KdfParams(**values)


class KdfTests(unittest.TestCase):
    def test_deterministic(self) -> None:
        self.assertEqual(derive_key("pw", params()), derive_key("pw", params()))

    def test_sensitivity(self) -> None:
        base = derive_key("pw", params())
        variants = [
            derive_key("pX", params()),
            derive_key("pw", params(salt=bytes(32))),
            derive_key("pw", params(memory_blocks=128)),
            derive_key("pw", params(passes=2)),
            derive_key("pw", params(), 33)[:32],
        ]
        for value in variants:
            self.assertNotEqual(value, base)

    def test_unicode_normalisation(self) -> None:
        composed = "caf\u00e9"
        decomposed = "cafe\u0301"
        self.assertEqual(derive_key(composed, params()), derive_key(decomposed, params()))
        self.assertEqual(derive_key(composed, params()), derive_key(composed.encode("utf-8"), params()))

    def test_parameter_validation(self) -> None:
        bad = [
            params(memory_blocks=100),
            params(memory_blocks=32),
            params(memory_blocks=True),
            params(passes=0),
            params(passes=17),
            params(salt=bytes(8)),
            params(rounds=4),
            params(memory_blocks=64.0),
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(BrisartKdfError):
                    derive_key("pw", value)

    def test_password_validation(self) -> None:
        for password in ("", b"", None, 5, "x" * (MAX_PASSWORD_BYTES + 1), "bad\ud800"):
            with self.subTest(password=str(password)[:10]):
                with self.assertRaises(BrisartKdfError):
                    derive_key(password, params())

    def test_encoding_round_trip_and_rejections(self) -> None:
        original = params(memory_blocks=256, passes=3)
        encoded = original.encode()
        self.assertEqual(len(encoded), 73)
        self.assertEqual(KdfParams.decode(encoded), original)
        tampered_id = b"\x02" + encoded[1:]
        tampered_filler = encoded[:-1] + b"\x01"
        for blob in (tampered_id, tampered_filler, encoded[:-1]):
            with self.assertRaises(BrisartKdfError):
                KdfParams.decode(blob)

    def test_decode_ceiling_blocks_hostile_headers(self) -> None:
        heavy = params(memory_blocks=1 << 20).encode()
        with self.assertRaises(BrisartKdfError):
            KdfParams.decode(heavy, max_memory_blocks=1 << 16)
        with self.assertRaises(BrisartKdfError):
            derive_key("pw", params(memory_blocks=1 << 20), max_memory_blocks=1 << 16)

    def test_new_params_uses_fresh_salt(self) -> None:
        self.assertNotEqual(new_params(64).salt, new_params(64).salt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
