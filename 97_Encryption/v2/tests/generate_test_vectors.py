"""Generate deterministic known-answer vectors for BSR2 regression tests.

Run this only when intentionally changing the algorithm or envelope format.
Do not run it before ordinary regression testing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from brisart_security_drbg import BrisartDRBG
from brisart_security_envelope import decrypt, encrypt
from brisart_security_primitives import keyed_mac, sponge_hash, stream_bytes


def main() -> None:
    key = bytes(range(32))
    seed = bytes(range(64))
    nonce = bytes(reversed(range(32)))
    message = b"BrisartSecurityResearch known-answer vector v2"
    context = "known-answer-vector:v2"

    generator = BrisartDRBG(seed, b"BSR2 known answer vector")
    envelope = encrypt(key, message, context, generator)
    if decrypt(key, envelope, context) != message:
        raise RuntimeError("known-answer envelope failed its own round trip")

    vectors = {
        "warning": "Regression vectors freeze behavior; they do not establish cryptographic security.",
        "format_version": 2,
        "hash": {
            "message_hex": message.hex(),
            "digest_hex": sponge_hash(message).hex(),
        },
        "mac": {
            "key_hex": key.hex(),
            "message_hex": message.hex(),
            "tag_hex": keyed_mac(key, message).hex(),
        },
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
            "output_hex": BrisartDRBG(
                seed,
                b"BSR2 known answer DRBG",
            ).generate(128, b"first request").hex(),
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
