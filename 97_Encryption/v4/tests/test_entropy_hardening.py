"""
File: tests/test_entropy_hardening.py

Purpose
-------
Verify the operating-system entropy boundary (brisart_security_entropy.py) and
the Alpha 3 restart mitigation in the legacy v2 envelope: identical DRBG
restarts no longer repeat envelopes, the known-plaintext XOR recovery fails,
entropy failures stop encryption, and the health checks reject stuck sources.
0.4.0 adds checks for constant samples, short requests, length limits, and
fork handling of the previous-sample memory.

Communication / relationships
-----------------------------
Imports brisart_security_entropy.py, brisart_security_envelope.py and
brisart_security_drbg.py; patches ``secrets.token_bytes``, ``os.getpid`` and
``envelope_module.system_entropy`` to simulate failures.

Settings / parameters
---------------------
Fixed master key bytes(range(32)), seed bytes(range(64)), and personalization
b"BSR2 restart hardening test".

Edge cases
----------
Zero-entropy injection is exercised only inside ``patch`` blocks; production
encryption never sees it. Tests reset ``_PREVIOUS_SAMPLE`` so ordering does not
matter.

Known limitations
-----------------
Validates the mitigation and the failure handling, not the quality of the
operating-system generator.

Examples
--------
    python -m unittest -v tests.test_entropy_hardening
"""
import unittest
from unittest.mock import patch

import brisart_security_entropy as entropy_module
import brisart_security_envelope as envelope_module
from brisart_security_drbg import BrisartDRBG
from brisart_security_entropy import BrisartEntropyError, system_entropy
from brisart_security_envelope import BrisartEnvelopeError, decrypt, encrypt


class EntropyHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.master_key = bytes(range(32))
        cls.seed = bytes(range(64))
        cls.context = "restart-hardening:test"
        cls.plaintext = b"known plaintext for deterministic restart testing"
        cls.personalization = b"BSR2 restart hardening test"

    def setUp(self) -> None:
        entropy_module._PREVIOUS_SAMPLE = None

    def generator(self) -> BrisartDRBG:
        return BrisartDRBG(self.seed, self.personalization)

    def test_fresh_equal_drbg_states_do_not_repeat_envelopes(self) -> None:
        first = encrypt(self.master_key, self.plaintext, self.context, self.generator())
        second = encrypt(self.master_key, self.plaintext, self.context, self.generator())
        self.assertNotEqual(first["salt"], second["salt"])
        self.assertNotEqual(first["nonce"], second["nonce"])
        self.assertNotEqual(first["ciphertext"], second["ciphertext"])
        self.assertNotEqual(first["tag"], second["tag"])
        self.assertEqual(decrypt(self.master_key, first, self.context), self.plaintext)
        self.assertEqual(decrypt(self.master_key, second, self.context), self.plaintext)

    def test_known_plaintext_xor_attack_no_longer_recovers_second(self) -> None:
        second_plaintext = b"hidden plaintext differs from the first message"
        first = encrypt(self.master_key, self.plaintext, self.context, self.generator())
        second = encrypt(self.master_key, second_plaintext, self.context, self.generator())
        first_ciphertext = bytes.fromhex(first["ciphertext"])
        second_ciphertext = bytes.fromhex(second["ciphertext"])
        recovered_guess = bytes(
            left ^ right ^ known
            for left, right, known in zip(first_ciphertext, second_ciphertext, self.plaintext)
        )
        self.assertNotEqual(recovered_guess, second_plaintext[: len(recovered_guess)])

    def test_entropy_failure_fails_closed(self) -> None:
        with patch.object(envelope_module, "system_entropy", side_effect=BrisartEntropyError("simulated failure")):
            with self.assertRaises(BrisartEnvelopeError) as captured:
                encrypt(self.master_key, self.plaintext, self.context, self.generator())
        self.assertIn("fresh entropy failed", str(captured.exception))

    def test_entropy_rejects_all_zero_sample(self) -> None:
        with patch.object(entropy_module.secrets, "token_bytes", return_value=b"\x00" * 32):
            with self.assertRaises(BrisartEntropyError):
                system_entropy(32)

    def test_entropy_rejects_constant_sample(self) -> None:
        with patch.object(entropy_module.secrets, "token_bytes", return_value=b"\xa5" * 32):
            with self.assertRaises(BrisartEntropyError):
                system_entropy(32)

    def test_entropy_rejects_consecutive_duplicate_sample(self) -> None:
        sample = bytes(range(32))
        with patch.object(entropy_module.secrets, "token_bytes", return_value=sample):
            self.assertEqual(system_entropy(32), sample)
            with self.assertRaises(BrisartEntropyError):
                system_entropy(32)
        entropy_module._PREVIOUS_SAMPLE = None

    def test_short_requests_use_full_health_sample(self) -> None:
        requested = []

        def fake(length):
            requested.append(length)
            return bytes([0] * (length - 1) + [1])

        with patch.object(entropy_module.secrets, "token_bytes", side_effect=fake):
            value = system_entropy(1)
        self.assertEqual(requested, [entropy_module.HEALTH_SAMPLE_BYTES])
        self.assertEqual(value, b"\x00")

    def test_short_requests_do_not_fail_spuriously(self) -> None:
        for _ in range(2000):
            self.assertEqual(len(system_entropy(1)), 1)

    def test_entropy_rejects_bool_and_oversized_lengths(self) -> None:
        for value in (True, 0, -1, entropy_module.MAX_ENTROPY_REQUEST + 1, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(BrisartEntropyError):
                    system_entropy(value)

    def test_fork_resets_previous_sample_memory(self) -> None:
        sample = bytes(range(32))
        with patch.object(entropy_module.secrets, "token_bytes", return_value=sample):
            system_entropy(32)
            with patch.object(entropy_module.os, "getpid", return_value=entropy_module._OWNER_PID + 1):
                self.assertEqual(system_entropy(32), sample)
        entropy_module._PREVIOUS_SAMPLE = None
        entropy_module._OWNER_PID = entropy_module.os.getpid()

    def test_zero_entropy_injection_is_test_only_and_deterministic(self) -> None:
        with patch.object(envelope_module, "system_entropy", side_effect=(b"\x00" * 32, b"\x00" * 32)):
            first = encrypt(self.master_key, self.plaintext, self.context, self.generator())
        with patch.object(envelope_module, "system_entropy", side_effect=(b"\x00" * 32, b"\x00" * 32)):
            second = encrypt(self.master_key, self.plaintext, self.context, self.generator())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
