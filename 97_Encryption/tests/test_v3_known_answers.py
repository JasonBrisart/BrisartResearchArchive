"""
File: tests/test_v3_known_answers.py

Purpose
-------
Frozen regression checks for the 0.4.0 constructions against
tests/v3_known_answer_vectors.json: BSR2-S64 hash, MAC, keystream and key
derivation; the version 3 sealed message; BSR-STREAM-1; and BSR2-MHF-1.
Any accidental change to a v3 wire format or derivation fails here.

Communication / relationships
-----------------------------
Reads tests/v3_known_answer_vectors.json (written by
tests/generate_v3_vectors.py); imports brisart_security_sponge.py,
brisart_security_aead.py, brisart_security_stream.py and brisart_security_kdf.py.

Settings / parameters
---------------------
The fixed randomizer stored in the vector file replaces OS entropy inside
this test only.

Edge cases
----------
Both directions are checked for sealed and stream vectors: the stored blob
opens, and regenerating with the fixed randomizer reproduces it byte for byte.

Known limitations
-----------------
Regression only; not evidence of security.

Examples
--------
    python -m unittest -v tests.test_v3_known_answers
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import brisart_security_aead as aead_module
import brisart_security_stream as stream_module
from brisart_security_kdf import KdfParams, derive_key
from brisart_security_sponge import derive_keys64, hash64, keystream64, mac64


class V3KnownAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.v = json.loads(Path(__file__).with_name("v3_known_answer_vectors.json").read_text(encoding="utf-8"))
        cls.key = bytes.fromhex(cls.v["key_hex"])
        cls.message = bytes.fromhex(cls.v["message_hex"])
        cls.randomizer = bytes.fromhex(cls.v["fixed_randomizer_hex"])

    def test_sponge_modes(self) -> None:
        self.assertEqual(hash64(self.message, b"BSR2/v3/kat", 48).hex(), self.v["hash64"])
        self.assertEqual(mac64(self.key, b"BSR2/v3/kat", self.message, b"part-two").hex(), self.v["mac64"])
        self.assertEqual(keystream64(self.key, b"kat-nonce", 200).hex(), self.v["keystream64"])
        self.assertEqual([k.hex() for k in derive_keys64(self.key, b"BSR2/v3/kat", b"label", count=2)], self.v["derive_keys64"])

    def test_sealed_vector(self) -> None:
        sealed = bytes.fromhex(self.v["sealed_hex"])
        self.assertEqual(aead_module.unseal(self.key, sealed, "kat:v3:seal", associated_data=b"kat-ad"), self.message)
        with patch.object(aead_module, "system_entropy", return_value=self.randomizer):
            again = aead_module.seal(self.key, self.message, "kat:v3:seal", associated_data=b"kat-ad", padding="padme")
        self.assertEqual(again, sealed)

    def test_stream_vector(self) -> None:
        blob = bytes.fromhex(self.v["stream_hex"])
        self.assertEqual(stream_module.decrypt_bytes(self.key, blob, context="kat:v3:stream"), self.message * 3)
        with patch.object(stream_module, "system_entropy", return_value=self.randomizer):
            again = stream_module.encrypt_bytes(self.key, self.message * 3, context="kat:v3:stream", chunk_size=64)
        self.assertEqual(again, blob)

    def test_mhf_vector(self) -> None:
        m = self.v["mhf"]
        params = KdfParams(memory_blocks=m["memory_blocks"], passes=m["passes"], salt=bytes.fromhex(m["salt_hex"]))
        self.assertEqual(derive_key(m["password"], params, 32).hex(), m["output_hex"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
