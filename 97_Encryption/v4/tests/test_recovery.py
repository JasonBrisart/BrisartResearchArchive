"""
File: tests/test_recovery.py

Purpose
-------
Tests for BSRR-1 recovery records (brisart_security_recovery.py): single and
burst damage repair through interleaved parity, truncation repair, refusal on
two damaged chunks in one group, damaged parity handling, record integrity
checks, and empty data.

Communication / relationships
-----------------------------
Imports brisart_security_recovery.py only (key-free by design).

Settings / parameters
---------------------
DATA = 20,000 pseudo-random bytes; chunk size 256; redundancy 10 percent
(8 parity groups for 79 chunks).

Edge cases
----------
Damage in the last partial chunk, a burst exactly as long as the parity count,
and a burst one chunk longer than it.

Known limitations
-----------------
XOR parity only; Reed-Solomon-class repair is not implemented.

Examples
--------
    python -m unittest -v tests.test_recovery
"""
import random
import unittest

from brisart_security_recovery import BrisartRecoveryError, build_recovery, parse_recovery, repair

DATA = bytes(random.Random(5).getrandbits(8) for _ in range(20_000))
CHUNK = 256


class RecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = build_recovery(DATA, chunk_size=CHUNK, redundancy_percent=10, aux=b"aux")
        self.parsed = parse_recovery(self.record)

    def damage(self, chunks) -> bytes:
        data = bytearray(DATA)
        for index in chunks:
            data[min(index * CHUNK + 7, len(data) - 1)] ^= 0x5A
        return bytes(data)

    def test_single_chunk_and_last_chunk(self) -> None:
        for index in (0, 40, self.parsed.chunk_count - 1):
            with self.subTest(index=index):
                repaired, report = repair(self.damage([index]), self.record)
                self.assertEqual(repaired, DATA)
                self.assertEqual(report["repaired_chunks"], [index])

    def test_burst_up_to_parity_count(self) -> None:
        burst = list(range(10, 10 + self.parsed.parity_count))
        repaired, report = repair(self.damage(burst), self.record)
        self.assertEqual(repaired, DATA)
        self.assertEqual(sorted(report["repaired_chunks"]), burst)

    def test_burst_longer_than_parity_count_fails(self) -> None:
        burst = list(range(10, 11 + self.parsed.parity_count))
        with self.assertRaises(BrisartRecoveryError):
            repair(self.damage(burst), self.record)

    def test_truncation_repair(self) -> None:
        repaired, report = repair(DATA[:-100], self.record)
        self.assertEqual(repaired, DATA)
        self.assertTrue(report["length_adjusted"])

    def test_damaged_parity_only_matters_with_data_damage(self) -> None:
        blob = bytearray(self.record)
        blob[-1] ^= 1
        repaired, _ = repair(DATA, bytes(blob))
        self.assertEqual(repaired, DATA)
        last_group = (self.parsed.parity_count - 1)
        with self.assertRaises(BrisartRecoveryError):
            repair(self.damage([last_group]), bytes(blob))

    def test_record_integrity(self) -> None:
        blob = bytearray(self.record)
        blob[40] ^= 1
        with self.assertRaises(BrisartRecoveryError):
            parse_recovery(bytes(blob))
        with self.assertRaises(BrisartRecoveryError):
            parse_recovery(self.record[:-1])
        self.assertEqual(self.parsed.aux, b"aux")

    def test_empty_data_and_parameters(self) -> None:
        record = build_recovery(b"", chunk_size=CHUNK)
        self.assertEqual(repair(b"", record)[0], b"")
        for kwargs in ({"chunk_size": 10}, {"redundancy_percent": 0}, {"redundancy_percent": 51}, {"aux": b"x" * 300}):
            with self.assertRaises(BrisartRecoveryError):
                build_recovery(DATA, **kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
