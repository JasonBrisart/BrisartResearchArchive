"""
File: tests/test_stream_v3.py

Purpose
-------
Tests for BSR-STREAM-1 (brisart_security_stream.py): round trips at every
chunk-boundary size, and rejection of truncation at a chunk boundary, dropped,
duplicated, reordered or modified chunks, appended data, wrong key/context/
associated data, header tampering, hostile chunk sizes, and plaintext limits.

Communication / relationships
-----------------------------
Imports brisart_security_stream.py.

Settings / parameters
---------------------
KEY = bytes(range(32)); chunk size 64 so multi-chunk cases stay small.
RECORD = 32-byte tag + 64-byte chunk.

Edge cases
----------
Sizes 0, 1, 63, 64, 65, 128, 129 and 640 cover empty, partial, exact and
multi-chunk endings.

Known limitations
-----------------
Behavioural only. Partial output before a late failure is a documented API
property and is not tested here (the CLI tests cover atomic output).

Examples
--------
    python -m unittest -v tests.test_stream_v3
"""
import io
import unittest

from brisart_security_stream import (
    HEADER_BYTES,
    BrisartStreamError,
    decrypt_bytes,
    decrypt_stream,
    encrypt_bytes,
)

KEY = bytes(range(32))
CHUNK = 64
RECORD = 32 + CHUNK


def enc(data: bytes, **kwargs) -> bytes:
    return encrypt_bytes(KEY, data, context="stream:test", chunk_size=CHUNK, **kwargs)


class StreamTests(unittest.TestCase):
    def test_round_trips(self) -> None:
        for size in (0, 1, 63, 64, 65, 128, 129, 640):
            data = bytes(i % 256 for i in range(size))
            with self.subTest(size=size):
                self.assertEqual(decrypt_bytes(KEY, enc(data), context="stream:test"), data)

    def test_structural_attacks_rejected(self) -> None:
        data = bytes(range(256))
        blob = enc(data)
        header, body = blob[:HEADER_BYTES], blob[HEADER_BYTES:]
        records = [body[i:i + RECORD] for i in range(0, len(body), RECORD)]
        attacks = {
            "truncate at boundary": header + b"".join(records[:2]),
            "drop middle": header + records[0] + b"".join(records[2:]),
            "duplicate": header + records[0] + records[0] + b"".join(records[1:]),
            "reorder": header + records[1] + records[0] + b"".join(records[2:]),
            "append": blob + b"\x00",
            "flip body": blob[:-1] + bytes([blob[-1] ^ 1]),
            "flip header": blob[:20] + bytes([blob[20] ^ 1]) + blob[21:],
            "header only": header,
        }
        for name, candidate in attacks.items():
            with self.subTest(attack=name):
                with self.assertRaises(BrisartStreamError):
                    decrypt_bytes(KEY, candidate, context="stream:test")

    def test_exact_multiple_truncation(self) -> None:
        blob = enc(b"z" * 128)
        with self.assertRaises(BrisartStreamError):
            decrypt_bytes(KEY, blob[:HEADER_BYTES + RECORD], context="stream:test")

    def test_binding(self) -> None:
        blob = enc(b"bound", associated_data=b"ad")
        for kwargs in (
            {"context": "stream:other", "associated_data": b"ad"},
            {"context": "stream:test", "associated_data": b"other"},
            {"context": "stream:test"},
        ):
            with self.assertRaises(BrisartStreamError):
                decrypt_bytes(KEY, blob, **kwargs)
        with self.assertRaises(BrisartStreamError):
            decrypt_bytes(bytes(reversed(KEY)), blob, context="stream:test", associated_data=b"ad")

    def test_hostile_chunk_size_rejected_before_allocation(self) -> None:
        blob = bytearray(enc(b"x"))
        blob[8:12] = (1 << 30).to_bytes(4, "big")
        with self.assertRaises(BrisartStreamError):
            decrypt_bytes(KEY, bytes(blob), context="stream:test")
        good = enc(b"x" * 100)
        with self.assertRaises(BrisartStreamError):
            decrypt_stream(KEY, io.BytesIO(good), io.BytesIO(), context="stream:test", max_chunk_size=32)

    def test_plaintext_limit(self) -> None:
        with self.assertRaises(BrisartStreamError):
            decrypt_bytes(KEY, enc(b"x" * 200), context="stream:test", max_plaintext_bytes=100)

    def test_parameter_validation(self) -> None:
        for action in (
            lambda: encrypt_bytes(KEY, b"x", context="c", chunk_size=10),
            lambda: encrypt_bytes(KEY, b"x", context="c", chunk_size=True),
            lambda: encrypt_bytes(b"short", b"x", context="c"),
            lambda: encrypt_bytes(KEY, "x", context="c"),
            lambda: encrypt_bytes(KEY, b"x", context=""),
        ):
            with self.assertRaises(BrisartStreamError):
                action()

    def test_randomized_output(self) -> None:
        self.assertNotEqual(enc(b"same"), enc(b"same"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
