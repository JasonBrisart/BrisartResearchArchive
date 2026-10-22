"""
File: tests/generate_test_vectors.py

Purpose
-------
Regenerate tests/known_answer_vectors.json, the frozen legacy (format 2)
vectors for the rate-32 hash, MAC, stream, DRBG, and the v2 envelope. Run it
only when intentionally changing a legacy algorithm or the v2 envelope; never
before an ordinary regression run, or a silent algorithm change would be
rewritten as "expected".

Communication / relationships
-----------------------------
Imports brisart_security_envelope.py (patched ``system_entropy``),
brisart_security_drbg.py and brisart_security_primitives.py. The v3 vectors
have their own generator, tests/generate_v3_vectors.py.

Settings / parameters
---------------------
REPOSITORY_ROOT is inserted into ``sys.path`` so the script runs from anywhere.
Fixed inputs: key bytes(range(32)), seed bytes(range(64)), nonce reversed
bytes(range(32)), context "known-answer-vector:v2".

Edge cases
----------
Injects all-zero entropy for the envelope strictly inside this script and
round-trips the envelope before writing anything.

Known limitations
-----------------
Freezes behaviour; does not establish security. Unchanged in 0.4.0 apart from
this header (the committed JSON was verified, not regenerated).

Examples
--------
    python tests/generate_test_vectors.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import brisart_security_envelope as envelope_module  # noqa: E402
from brisart_security_drbg import BrisartDRBG  # noqa: E402
from brisart_security_envelope import decrypt, encrypt  # noqa: E402
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes  # noqa: E402


def main() -> None:
    key = bytes(range(32))
    seed = bytes(range(64))
    nonce = bytes(reversed(range(32)))
    message = b"BrisartSecurityResearch known-answer vector v2"
    context = "known-answer-vector:v2"
    generator = BrisartDRBG(seed, b"BSR2 known answer vector")
    with patch.object(envelope_module, "system_entropy", side_effect=(b"\x00" * 32, b"\x00" * 32)):
        envelope = encrypt(key, message, context, generator)
    if decrypt(key, envelope, context) != message:
        raise RuntimeError("known-answer envelope failed its own round trip")
    vectors = {
        "warning": (
            "Regression vectors freeze behavior; they do not establish "
            "cryptographic security. Envelope generation uses test-only "
            "zero entropy injection for reproducibility."
        ),
        "format_version": 2,
        "hash": {"message_hex": message.hex(), "digest_hex": sponge_hash(message).hex()},
        "mac": {"key_hex": key.hex(), "message_hex": message.hex(), "tag_hex": keyed_mac(key, message).hex()},
        "stream": {
            "key_hex": key.hex(),
            "nonce_hex": nonce.hex(),
            "length": 128,
            "output_hex": stream_bytes(key, nonce, 128).hex(),
        },
        "drbg": {
            "seed_hex": seed.hex(),
            "personalization_hex": b"BSR2 known answer DRBG".hex(),
            "additional_input_hex": b"first request".hex(),
            "length": 128,
            "output_hex": BrisartDRBG(seed, b"BSR2 known answer DRBG").generate(128, b"first request").hex(),
        },
        "envelope": {
            "master_key_hex": key.hex(),
            "plaintext_hex": message.hex(),
            "context": context,
            "value": envelope,
        },
    }
    vector_path = Path(__file__).resolve().with_name("known_answer_vectors.json")
    vector_path.write_text(json.dumps(vectors, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {vector_path}")


if __name__ == "__main__":
    main()
