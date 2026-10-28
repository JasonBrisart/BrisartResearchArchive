"""Focused boundary tests for BSR2 envelope defensive hardening.

These checks validate failure behavior and resource limits. Passing them does
not establish cryptographic security.
"""

import unittest
from unittest.mock import patch

import brisart_security_envelope as envelope_module
from brisart_security_drbg import BrisartDRBG
from brisart_security_envelope import BrisartEnvelopeError, decrypt, encrypt


class FailingGenerator:
    def generate(self, length, additional_input):
        raise RuntimeError("internal generator detail")


class EnvelopeHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.master_key = bytes(range(32))
        cls.seed = bytes(range(64))
        cls.context = "hardening:test"
        cls.plaintext = b"defensive envelope boundary test"

    def generator(self) -> BrisartDRBG:
        return BrisartDRBG(self.seed, b"BSR2 envelope hardening tests")

    def envelope(self) -> dict:
        return encrypt(
            self.master_key,
            self.plaintext,
            self.context,
            self.generator(),
        )

    def test_generator_failure_is_wrapped(self) -> None:
        with self.assertRaises(BrisartEnvelopeError) as captured:
            encrypt(
                self.master_key,
                self.plaintext,
                self.context,
                FailingGenerator(),
            )
        self.assertEqual(
            str(captured.exception),
            "generator failed while producing salt",
        )
        self.assertIsInstance(captured.exception.__cause__, RuntimeError)

    def test_encrypt_rejects_oversized_context(self) -> None:
        with patch.object(envelope_module, "MAX_CONTEXT_BYTES", 8):
            with self.assertRaises(BrisartEnvelopeError):
                encrypt(
                    self.master_key,
                    self.plaintext,
                    "context-too-large",
                    self.generator(),
                )

    def test_decrypt_rejects_oversized_context(self) -> None:
        envelope = self.envelope()
        with patch.object(envelope_module, "MAX_CONTEXT_BYTES", 8):
            with self.assertRaises(BrisartEnvelopeError):
                decrypt(
                    self.master_key,
                    envelope,
                    "context-too-large",
                )

    def test_context_rejects_unencodable_surrogate(self) -> None:
        invalid_context = "invalid\ud800context"
        with self.assertRaises(BrisartEnvelopeError):
            encrypt(
                self.master_key,
                self.plaintext,
                invalid_context,
                self.generator(),
            )
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(
                self.master_key,
                self.envelope(),
                invalid_context,
            )

    def test_decrypt_rejects_non_text_algorithm(self) -> None:
        envelope = self.envelope()
        envelope["algorithm"] = 2
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_non_integer_version(self) -> None:
        for value in ("2", 2.0, None, True):
            with self.subTest(value=value):
                envelope = self.envelope()
                envelope["version"] = value
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_oversized_ciphertext_before_hex_decode(self) -> None:
        envelope = self.envelope()
        envelope["ciphertext"] = "00" * 9
        with patch.object(envelope_module, "MAX_PLAINTEXT_BYTES", 8):
            with patch.object(
                envelope_module,
                "hex_decode",
                side_effect=AssertionError("hex decoder should not be called"),
            ):
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_wrong_fixed_field_lengths_before_decode(self) -> None:
        for field in ("salt", "nonce", "tag"):
            with self.subTest(field=field):
                envelope = self.envelope()
                envelope[field] = "00"
                with patch.object(
                    envelope_module,
                    "hex_decode",
                    side_effect=AssertionError(
                        "hex decoder should not be called"
                    ),
                ):
                    with self.assertRaises(BrisartEnvelopeError):
                        decrypt(self.master_key, envelope, self.context)

    def test_valid_envelope_behavior_is_unchanged(self) -> None:
        envelope = self.envelope()
        self.assertEqual(
            decrypt(self.master_key, envelope, self.context),
            self.plaintext,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
