"""Regression checks for known_answer_vectors.json."""

import json
import unittest
from pathlib import Path

from brisart_security_drbg import BrisartDRBG
from brisart_security_envelope import decrypt, encrypt
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes


class KnownAnswerVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vector_path = Path(__file__).with_name("known_answer_vectors.json")
        cls.vectors = json.loads(vector_path.read_text(encoding="utf-8"))

    def test_hash_vector(self):
        vector = self.vectors["hash"]
        self.assertEqual(sponge_hash(bytes.fromhex(vector["message_hex"])).hex(), vector["digest_hex"])

    def test_mac_vector(self):
        vector = self.vectors["mac"]
        self.assertEqual(keyed_mac(bytes.fromhex(vector["key_hex"]), bytes.fromhex(vector["message_hex"])).hex(), vector["tag_hex"])

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
        regenerated = encrypt(key, plaintext, vector["context"], BrisartDRBG(bytes(range(64)), b"BSR1 known answer vector"))
        self.assertEqual(regenerated, envelope)


if __name__ == "__main__":
    unittest.main(verbosity=2)
