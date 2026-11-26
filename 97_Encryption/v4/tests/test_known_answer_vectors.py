"""
File: tests/test_known_answer_vectors.py

Purpose
-------
Frozen regression checks against tests/known_answer_vectors.json for the
legacy BSR2 hash, MAC, stream, DRBG, and v2 envelope. In 0.4.0 these vectors
are the proof that the optimised permutation schedule, the domain initial-state
cache, and the big-integer XOR changed no output bit.

Communication / relationships
-----------------------------
Reads tests/known_answer_vectors.json; imports brisart_security_primitives.py,
brisart_security_drbg.py and brisart_security_envelope.py. The v3 formats are
pinned separately by tests/test_v3_known_answers.py.

Settings / parameters
---------------------
Vector format version 2; algorithm BSR2-ARX-SPONGE-ETM; envelope version 2.

Edge cases
----------
The envelope vector injects all-zero entropy strictly inside this test so the
frozen deterministic envelope path stays reproducible.

Known limitations
-----------------
Regression only. Matching vectors say nothing about security.

Examples
--------
    python -m unittest -v tests.test_known_answer_vectors
"""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import brisart_security_envelope as envelope_module
from brisart_security_drbg import BrisartDRBG
from brisart_security_envelope import ALGORITHM, VERSION, decrypt, encrypt
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes


class KnownAnswerVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vector_path = Path(__file__).with_name("known_answer_vectors.json")
        cls.vectors = json.loads(vector_path.read_text(encoding="utf-8"))

    def test_vector_format_version(self):
        self.assertEqual(self.vectors["format_version"], 2)

    def test_envelope_metadata(self):
        envelope = self.vectors["envelope"]["value"]
        self.assertEqual(envelope["algorithm"], ALGORITHM)
        self.assertEqual(envelope["version"], VERSION)

    def test_hash_vector(self):
        vector = self.vectors["hash"]
        actual = sponge_hash(bytes.fromhex(vector["message_hex"]))
        self.assertEqual(actual.hex(), vector["digest_hex"])

    def test_mac_vector(self):
        vector = self.vectors["mac"]
        actual = keyed_mac(bytes.fromhex(vector["key_hex"]), bytes.fromhex(vector["message_hex"]))
        self.assertEqual(actual.hex(), vector["tag_hex"])

    def test_stream_vector(self):
        vector = self.vectors["stream"]
        actual = stream_bytes(bytes.fromhex(vector["key_hex"]), bytes.fromhex(vector["nonce_hex"]), vector["length"])
        self.assertEqual(actual.hex(), vector["output_hex"])

    def test_drbg_vector(self):
        vector = self.vectors["drbg"]
        generator = BrisartDRBG(bytes.fromhex(vector["seed_hex"]), bytes.fromhex(vector["personalization_hex"]))
        actual = generator.generate(vector["length"], bytes.fromhex(vector["additional_input_hex"]))
        self.assertEqual(actual.hex(), vector["output_hex"])

    def test_envelope_vector(self):
        vector = self.vectors["envelope"]
        key = bytes.fromhex(vector["master_key_hex"])
        plaintext = bytes.fromhex(vector["plaintext_hex"])
        envelope = vector["value"]
        self.assertEqual(decrypt(key, envelope, vector["context"]), plaintext)
        with patch.object(envelope_module, "system_entropy", side_effect=(b"\x00" * 32, b"\x00" * 32)):
            regenerated = encrypt(
                key,
                plaintext,
                vector["context"],
                BrisartDRBG(bytes(range(64)), b"BSR2 known answer vector"),
            )
        self.assertEqual(regenerated, envelope)


if __name__ == "__main__":
    unittest.main(verbosity=2)
