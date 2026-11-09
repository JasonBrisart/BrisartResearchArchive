"""
File: crypto/tests/test_envelope.py

Purpose
-------
Tests for crypto.envelope: round trips in the v3 sealed format, the switch to
BSR-STREAM-1 above the v3 limit, length-hiding padding, context binding,
uniform authentication failure, and input validation. Legacy v2 payloads are
covered by crypto/tests/test_encryption_link.py, which holds payloads sealed
by 1.9.2.

Verifies: crypto/envelope.py, crypto/errors.py, crypto/rng.py.
Contains 18 test case(s) across 5 TestCase class(es).

Design notes:

These use a random 32-byte master key and a real crypto.rng generator, not a
passphrase, so they run the full BSR2 seal/open path without any
KDF cost. The stream-selection test lowers the linked ``aead`` limit with
unittest.mock rather than sealing 16 MiB, which would take minutes in pure
Python; the stream path itself is real.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.rng (crypto/rng.py)
- crypto.tests.legacy_fixtures (crypto/tests/legacy_fixtures.py)
Standard library: base64, secrets, unittest, unittest.mock.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
None.

Edge cases
----------
EnvelopeRoundTripTests:
- Bytes, empty bytes, and a JSON object round trip.
- A new seal is a v3 sealed payload and reports as an envelope.
- Junk and partial shapes do not report as envelopes.
- Content above the v3 limit is sealed as BSR-STREAM-1 and opens.
EnvelopeAuthenticationTests:
- A modified v3 payload, the wrong key, and the wrong context all raise
  EnvelopeAuthenticationError.
- A modified stream payload raises EnvelopeAuthenticationError.
EnvelopePaddingTests:
- 1-byte and 40-byte plaintexts seal to the same size.
ResealTests:
- Legacy byte and JSON envelopes reseal to v3 and open to the same content.
- A current payload is returned unchanged.
- A wrong key or context raises EnvelopeAuthenticationError instead of
  resealing.
InputTests:
- Non-bytes plaintext, a non-dict JSON payload, invalid base64, and a value
  that is not a sealed payload are rejected with Bsr2IntegrationError.
- Opening non-JSON bytes as JSON fails after authentication.

Known limitations
-----------------
- Passing proves only the scenarios listed above.

Examples
--------
::

    python -m unittest crypto.tests.test_envelope -v
"""

import base64
import secrets
import unittest
from unittest import mock

from crypto import encryption
from crypto.envelope import (
    SEALED_FORMAT,
    STREAM_FORMAT,
    is_envelope,
    is_legacy,
    reseal,
    open_bytes,
    open_json,
    seal_bytes,
    seal_json,
)
from crypto.errors import Bsr2IntegrationError, EnvelopeAuthenticationError
from crypto.rng import new_generator
from crypto.tests.legacy_fixtures import seal_legacy_bytes, seal_legacy_json


def _rng():
    return new_generator("envelope-test")


def _flip_last_byte(envelope):
    data = bytearray(base64.b64decode(envelope["data"]))
    data[-1] ^= 1
    return {**envelope, "data": base64.b64encode(bytes(data)).decode("ascii")}


class EnvelopeRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)

    def test_bytes_round_trip_exactly(self):
        data = secrets.token_bytes(1000)
        self.assertEqual(open_bytes(self.key, seal_bytes(self.key, data, "ctx", _rng()), "ctx"), data)

    def test_empty_bytes_round_trip(self):
        self.assertEqual(open_bytes(self.key, seal_bytes(self.key, b"", "ctx", _rng()), "ctx"), b"")

    def test_json_round_trips(self):
        payload = {"b": 2, "a": [1, 2, 3], "nested": {"x": True}}
        self.assertEqual(open_json(self.key, seal_json(self.key, payload, "ctx", _rng()), "ctx"), payload)

    def test_new_seal_is_a_v3_sealed_payload(self):
        envelope = seal_bytes(self.key, b"hi", "ctx", _rng())
        self.assertEqual(envelope["format"], SEALED_FORMAT)
        self.assertTrue(is_envelope(envelope))

    def test_junk_is_not_an_envelope(self):
        self.assertFalse(is_envelope({"not": "an envelope"}))
        self.assertFalse(is_envelope("string"))
        self.assertFalse(is_envelope({"format": SEALED_FORMAT}))
        self.assertFalse(is_envelope({"format": "other", "data": ""}))
        self.assertFalse(is_envelope({"algorithm": "BSR2-ARX-SPONGE-ETM"}))

    def test_content_above_the_v3_limit_is_sealed_as_a_stream(self):
        aead = encryption.require().aead
        data = secrets.token_bytes(5000)
        with mock.patch.object(aead, "MAX_PLAINTEXT_BYTES", 1024):
            envelope = seal_bytes(self.key, data, "ctx", _rng())
        self.assertEqual(envelope["format"], STREAM_FORMAT)
        self.assertEqual(open_bytes(self.key, envelope, "ctx"), data)


class EnvelopeAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)
        self.envelope = seal_bytes(self.key, b"secret payload", "ctx", _rng())

    def test_modified_payload_fails_authentication(self):
        with self.assertRaises(EnvelopeAuthenticationError):
            open_bytes(self.key, _flip_last_byte(self.envelope), "ctx")

    def test_wrong_key_fails_authentication(self):
        with self.assertRaises(EnvelopeAuthenticationError):
            open_bytes(secrets.token_bytes(32), self.envelope, "ctx")

    def test_wrong_context_fails_authentication(self):
        with self.assertRaises(EnvelopeAuthenticationError):
            open_bytes(self.key, self.envelope, "different-context")

    def test_modified_stream_fails_authentication(self):
        stream = encryption.require().stream
        blob = stream.encrypt_bytes(self.key, b"x" * 300, context="ctx")
        envelope = {"format": STREAM_FORMAT, "data": base64.b64encode(blob).decode("ascii")}
        self.assertEqual(open_bytes(self.key, envelope, "ctx"), b"x" * 300)
        with self.assertRaises(EnvelopeAuthenticationError):
            open_bytes(self.key, _flip_last_byte(envelope), "ctx")


class EnvelopePaddingTests(unittest.TestCase):
    def test_short_plaintexts_share_a_size_bucket(self):
        key = secrets.token_bytes(32)
        short = seal_bytes(key, b"x", "ctx", _rng())
        longer = seal_bytes(key, b"x" * 40, "ctx", _rng())
        self.assertEqual(len(short["data"]), len(longer["data"]))


class ResealTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)

    def test_legacy_bytes_and_json_reseal_to_v3(self):
        legacy_bytes = seal_legacy_bytes(self.key, b"\x00raw\xff", "ctx")
        legacy_json = seal_legacy_json(self.key, {"b": 1, "a": [2]}, "ctx")
        self.assertTrue(is_legacy(legacy_bytes) and is_legacy(legacy_json))
        new_bytes = reseal(self.key, legacy_bytes, "ctx", _rng())
        new_json = reseal(self.key, legacy_json, "ctx", _rng())
        self.assertEqual(new_bytes["format"], SEALED_FORMAT)
        self.assertEqual(open_bytes(self.key, new_bytes, "ctx"), b"\x00raw\xff")
        self.assertEqual(open_json(self.key, new_json, "ctx"), {"b": 1, "a": [2]})

    def test_current_payload_is_returned_unchanged(self):
        current = seal_bytes(self.key, b"x", "ctx", _rng())
        self.assertIs(reseal(self.key, current, "ctx", _rng()), current)
        self.assertFalse(is_legacy(current))

    def test_wrong_key_or_context_never_reseals(self):
        legacy = seal_legacy_bytes(self.key, b"x", "ctx")
        with self.assertRaises(EnvelopeAuthenticationError):
            reseal(secrets.token_bytes(32), legacy, "ctx", _rng())
        with self.assertRaises(EnvelopeAuthenticationError):
            reseal(self.key, legacy, "other", _rng())


class InputTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)

    def test_seal_bytes_rejects_non_bytes(self):
        with self.assertRaises(Bsr2IntegrationError):
            seal_bytes(self.key, "a string, not bytes", "ctx", _rng())

    def test_seal_json_rejects_non_dict(self):
        with self.assertRaises(Bsr2IntegrationError):
            seal_json(self.key, ["not", "an", "object"], "ctx", _rng())

    def test_invalid_base64_and_non_envelopes_are_rejected(self):
        with self.assertRaises(Bsr2IntegrationError):
            open_bytes(self.key, {"format": SEALED_FORMAT, "data": "not base64!"}, "ctx")
        with self.assertRaises(Bsr2IntegrationError):
            open_bytes(self.key, {"plain": "data"}, "ctx")

    def test_open_json_on_non_json_payload_raises_after_auth(self):
        envelope = seal_bytes(self.key, b"\xff\xfe\x00 not json", "ctx", _rng())
        with self.assertRaises(Bsr2IntegrationError):
            open_json(self.key, envelope, "ctx")


if __name__ == "__main__":
    unittest.main()
