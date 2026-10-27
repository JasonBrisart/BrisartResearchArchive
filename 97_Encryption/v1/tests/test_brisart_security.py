"""Behavioral and boundary tests for the experimental BSR1 implementation.

These tests verify implemented behavior and fail-closed input handling. Passing
results do not establish cryptographic security or production suitability.
"""

import copy
import unittest
from unittest.mock import patch

import brisart_security_envelope as envelope_module
from brisart_security_drbg import (
    MAX_BYTES_BEFORE_RESEED,
    MAX_REQUEST_BYTES,
    RESEED_INTERVAL,
    BrisartDRBG,
    BrisartDRBGError,
)
from brisart_security_envelope import BrisartEnvelopeError, decrypt, encrypt
from brisart_security_primitives import (
    BrisartPrimitiveError,
    STATE_WORDS,
    derive_password_key,
    frame,
    hex_decode,
    hex_encode,
    keyed_mac,
    permute,
    sponge_hash,
    stream_bytes,
    xor_bytes,
)


class BrisartCipherResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.kdf_salt = bytes(range(32))
        cls.master_key = derive_password_key(
            "research-only-password",
            cls.kdf_salt,
            iterations=10_000,
        )
        cls.context = "research-record:test"
        cls.seed = bytes(range(64))
        cls.plaintext = "Custom cipher research: café archive".encode("utf-8")

    def new_generator(self, label: bytes = b"BSR1 test instance") -> BrisartDRBG:
        return BrisartDRBG(self.seed, label)

    def new_envelope(self) -> dict:
        return encrypt(
            self.master_key,
            self.plaintext,
            self.context,
            self.new_generator(),
        )

    # Core behavioral tests

    def test_round_trip(self) -> None:
        envelope = self.new_envelope()
        self.assertEqual(
            decrypt(self.master_key, envelope, self.context),
            self.plaintext,
        )

    def test_randomized_encryption(self) -> None:
        generator = self.new_generator()
        first = encrypt(self.master_key, self.plaintext, self.context, generator)
        second = encrypt(self.master_key, self.plaintext, self.context, generator)
        self.assertNotEqual(first["salt"], second["salt"])
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotEqual(first["ciphertext"], second["ciphertext"])

    def test_each_binary_field_tamper_fails(self) -> None:
        for field in ("salt", "nonce", "ciphertext", "tag"):
            with self.subTest(field=field):
                envelope = self.new_envelope()
                raw = bytearray(hex_decode(envelope[field]))
                if raw:
                    raw[0] ^= 1
                else:
                    raw.append(1)
                envelope[field] = hex_encode(bytes(raw))
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, envelope, self.context)

    def test_wrong_context_fails(self) -> None:
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, self.new_envelope(), "other-context")

    def test_wrong_key_fails(self) -> None:
        wrong_key = BrisartDRBG(
            bytes(reversed(self.seed)),
            b"BSR1 wrong key test",
        ).generate(32, b"wrong key generation")
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(wrong_key, self.new_envelope(), self.context)

    def test_unknown_missing_and_format_fields_fail(self) -> None:
        envelope = self.new_envelope()
        for mutation in ("extra", "missing", "algorithm", "version"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(envelope)
                if mutation == "extra":
                    changed["extra"] = 1
                elif mutation == "missing":
                    del changed["tag"]
                elif mutation == "algorithm":
                    changed["algorithm"] = "other"
                else:
                    changed["version"] = 2
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, changed, self.context)

    def test_empty_plaintext(self) -> None:
        envelope = encrypt(
            self.master_key,
            b"",
            self.context,
            self.new_generator(),
        )
        self.assertEqual(decrypt(self.master_key, envelope, self.context), b"")

    def test_custom_hex_codec(self) -> None:
        value = bytes(range(256))
        self.assertEqual(hex_decode(hex_encode(value)), value)

    def test_hash_is_deterministic(self) -> None:
        self.assertEqual(sponge_hash(b"message"), sponge_hash(b"message"))
        self.assertNotEqual(sponge_hash(b"message"), sponge_hash(b"messagf"))

    def test_avalanche_observation(self) -> None:
        first = sponge_hash(b"A" * 64)
        changed = bytearray(b"A" * 64)
        changed[0] ^= 1
        second = sponge_hash(bytes(changed))
        differing_bits = sum((a ^ b).bit_count() for a, b in zip(first, second))
        self.assertGreater(differing_bits, 80)
        self.assertLess(differing_bits, 176)

    def test_drbg_is_deterministic_for_same_seed(self) -> None:
        first = self.new_generator().generate(96, b"deterministic test")
        second = self.new_generator().generate(96, b"deterministic test")
        self.assertEqual(first, second)

    def test_drbg_changes_with_seed(self) -> None:
        first = self.new_generator().generate(96, b"deterministic test")
        second_seed = bytearray(self.seed)
        second_seed[0] ^= 1
        second = BrisartDRBG(
            bytes(second_seed),
            b"BSR1 test instance",
        ).generate(96, b"deterministic test")
        self.assertNotEqual(first, second)

    def test_drbg_rejects_short_seed(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            BrisartDRBG(b"short", b"BSR1 short seed test")

    def test_encryption_requires_explicit_generator(self) -> None:
        with self.assertRaises(BrisartEnvelopeError):
            encrypt(self.master_key, self.plaintext, self.context, None)

    def test_drbg_requires_personalization(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            BrisartDRBG(self.seed, b"short")

    def test_drbg_requires_additional_input(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            self.new_generator(b"BSR1 additional input").generate(32, b"")

    def test_destroyed_drbg_fails_closed(self) -> None:
        generator = self.new_generator(b"BSR1 destroy test")
        generator.destroy()
        with self.assertRaises(BrisartDRBGError):
            generator.generate(32, b"after destroy")

    def test_reseed_changes_output(self) -> None:
        generator = self.new_generator(b"BSR1 reseed test")
        before = generator.generate(64, b"before reseed")
        generator.reseed(bytes(reversed(self.seed)), b"reseed event")
        after = generator.generate(64, b"after reseed")
        self.assertNotEqual(before, after)

    # Envelope boundary tests

    def test_decrypt_rejects_non_dictionary_envelope(self) -> None:
        for value in (None, [], "envelope", b"envelope"):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, value, self.context)

    def test_encrypt_and_decrypt_reject_non_byte_master_key(self) -> None:
        with self.assertRaises(BrisartEnvelopeError):
            encrypt("not-bytes", self.plaintext, self.context, self.new_generator())
        with self.assertRaises(BrisartEnvelopeError):
            decrypt("not-bytes", self.new_envelope(), self.context)

    def test_encrypt_and_decrypt_reject_short_master_key(self) -> None:
        with self.assertRaises(BrisartEnvelopeError):
            encrypt(b"short", self.plaintext, self.context, self.new_generator())
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(b"short", self.new_envelope(), self.context)

    def test_encrypt_rejects_non_byte_plaintext(self) -> None:
        for value in ("plaintext", bytearray(b"plaintext"), None):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(BrisartEnvelopeError):
                    encrypt(self.master_key, value, self.context, self.new_generator())

    def test_encrypt_and_decrypt_reject_empty_context(self) -> None:
        with self.assertRaises(BrisartEnvelopeError):
            encrypt(self.master_key, self.plaintext, "", self.new_generator())
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, self.new_envelope(), "")

    def test_encrypt_and_decrypt_reject_non_string_context(self) -> None:
        for value in (None, b"context", 1):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(BrisartEnvelopeError):
                    encrypt(self.master_key, self.plaintext, value, self.new_generator())
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, self.new_envelope(), value)

    def test_decrypt_rejects_uppercase_hexadecimal(self) -> None:
        envelope = self.new_envelope()
        envelope["salt"] = envelope["salt"].upper()
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_odd_length_hexadecimal(self) -> None:
        envelope = self.new_envelope()
        envelope["nonce"] = envelope["nonce"][:-1]
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_invalid_hexadecimal_characters(self) -> None:
        envelope = self.new_envelope()
        envelope["tag"] = "zz" + envelope["tag"][2:]
        with self.assertRaises(BrisartEnvelopeError):
            decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_incorrect_binary_field_lengths(self) -> None:
        for field in ("salt", "nonce", "tag"):
            with self.subTest(field=field):
                envelope = self.new_envelope()
                envelope[field] = envelope[field][2:]
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, envelope, self.context)

    def test_encrypt_rejects_oversized_plaintext(self) -> None:
        with patch.object(envelope_module, "MAX_PLAINTEXT_BYTES", 8):
            with self.assertRaises(BrisartEnvelopeError):
                encrypt(self.master_key, b"A" * 9, self.context, self.new_generator())

    def test_decrypt_rejects_oversized_ciphertext(self) -> None:
        envelope = self.new_envelope()
        ciphertext_bytes = len(envelope["ciphertext"]) // 2
        with patch.object(
            envelope_module,
            "MAX_PLAINTEXT_BYTES",
            ciphertext_bytes - 1,
        ):
            with self.assertRaises(BrisartEnvelopeError):
                decrypt(self.master_key, envelope, self.context)

    def test_decrypt_rejects_wrong_binary_field_value_types(self) -> None:
        for field in ("salt", "nonce", "ciphertext", "tag"):
            with self.subTest(field=field):
                envelope = self.new_envelope()
                envelope[field] = 123
                with self.assertRaises(BrisartEnvelopeError):
                    decrypt(self.master_key, envelope, self.context)

    # Primitive boundary tests

    def test_permute_rejects_invalid_state_length(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            permute([0] * (STATE_WORDS - 1))

    def test_permute_rejects_zero_and_negative_rounds(self) -> None:
        for rounds in (0, -1):
            with self.subTest(rounds=rounds):
                with self.assertRaises(BrisartPrimitiveError):
                    permute([0] * STATE_WORDS, rounds)

    def test_sponge_rejects_invalid_output_lengths(self) -> None:
        for output_bytes in (0, -1, 1025):
            with self.subTest(output_bytes=output_bytes):
                with self.assertRaises(BrisartPrimitiveError):
                    sponge_hash(b"message", output_bytes)

    def test_mac_rejects_short_key(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            keyed_mac(b"short", b"message")

    def test_stream_rejects_negative_length(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            stream_bytes(b"K" * 32, b"N" * 32, -1)

    def test_xor_rejects_unequal_inputs(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            xor_bytes(b"one", b"two-two")

    def test_frame_rejects_invalid_input(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            frame("not-bytes")

    def test_hex_decode_rejects_invalid_input_type(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            hex_decode(b"00")

    def test_hex_decode_rejects_odd_length(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            hex_decode("0")

    def test_hex_decode_rejects_uppercase(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            hex_decode("AA")

    def test_hex_decode_rejects_invalid_characters(self) -> None:
        with self.assertRaises(BrisartPrimitiveError):
            hex_decode("zz")

    # DRBG boundary tests

    def test_drbg_rejects_zero_and_negative_request_lengths(self) -> None:
        for length in (0, -1):
            with self.subTest(length=length):
                with self.assertRaises(BrisartDRBGError):
                    self.new_generator().generate(length, b"request")

    def test_drbg_rejects_request_over_limit(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            self.new_generator().generate(MAX_REQUEST_BYTES + 1, b"request")

    def test_drbg_rejects_non_byte_seed(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            BrisartDRBG("not-bytes", b"BSR1 seed type test")

    def test_drbg_rejects_non_byte_personalization(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            BrisartDRBG(self.seed, "not-bytes")

    def test_drbg_rejects_non_byte_additional_input(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            self.new_generator().generate(32, "not-bytes")

    def test_drbg_reseed_rejects_empty_additional_input(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            self.new_generator().reseed(self.seed, b"")

    def test_drbg_reseed_rejects_short_material(self) -> None:
        with self.assertRaises(BrisartDRBGError):
            self.new_generator().reseed(b"short", b"reseed event")

    def test_drbg_reseed_after_destroy_reactivates_generator(self) -> None:
        generator = self.new_generator(b"BSR1 destroy reseed test")
        generator.destroy()
        generator.reseed(bytes(reversed(self.seed)), b"reseed after destroy")
        output = generator.generate(32, b"request after reseed")
        self.assertEqual(len(output), 32)

    def test_drbg_rejects_request_crossing_byte_limit(self) -> None:
        generator = self.new_generator(b"BSR1 byte limit test")
        generator._generated_bytes = MAX_BYTES_BEFORE_RESEED - 16
        with self.assertRaises(BrisartDRBGError):
            generator.generate(17, b"cross byte limit")

    def test_drbg_rejects_request_at_reseed_interval(self) -> None:
        generator = self.new_generator(b"BSR1 interval test")
        generator._requests = RESEED_INTERVAL
        with self.assertRaises(BrisartDRBGError):
            generator.generate(32, b"cross request interval")


if __name__ == "__main__":
    unittest.main(verbosity=2)
