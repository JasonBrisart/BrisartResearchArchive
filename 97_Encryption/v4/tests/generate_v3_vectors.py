"""
File: tests/generate_v3_vectors.py

Purpose
-------
Write tests/v3_known_answer_vectors.json, the frozen vectors for the 0.4.0
constructions: BSR2-S64 hash/MAC/keystream/key derivation, the version 3
sealed message, the BSR-STREAM-1 stream, and BSR2-MHF-1. Same policy as the
legacy generator: run only when deliberately changing one of these formats.

Communication / relationships
-----------------------------
Imports brisart_security_sponge.py, brisart_security_aead.py,
brisart_security_stream.py and brisart_security_kdf.py. Consumed by
tests/test_v3_known_answers.py.

Settings / parameters
---------------------
FIXED_RANDOMIZER = bytes(range(100, 132)) replaces OS entropy inside this
script only, so sealed and stream outputs are reproducible.

Edge cases
----------
Each generated sealed/stream vector is opened again before the file is written.

Known limitations
-----------------
Freezes behaviour; does not establish security.

Examples
--------
    python tests/generate_v3_vectors.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

import brisart_security_aead as aead_module  # noqa: E402
import brisart_security_stream as stream_module  # noqa: E402
from brisart_security_kdf import KdfParams, derive_key  # noqa: E402
from brisart_security_sponge import derive_keys64, hash64, keystream64, mac64  # noqa: E402

FIXED_RANDOMIZER = bytes(range(100, 132))
KEY = bytes(range(32))
MESSAGE = b"BrisartSecurityResearch known-answer vector v3"


def build() -> dict:
    with patch.object(aead_module, "system_entropy", return_value=FIXED_RANDOMIZER):
        sealed = aead_module.seal(KEY, MESSAGE, "kat:v3:seal", associated_data=b"kat-ad", padding="padme")
    with patch.object(stream_module, "system_entropy", return_value=FIXED_RANDOMIZER):
        stream = stream_module.encrypt_bytes(KEY, MESSAGE * 3, context="kat:v3:stream", chunk_size=64)
    if aead_module.unseal(KEY, sealed, "kat:v3:seal", associated_data=b"kat-ad") != MESSAGE:
        raise RuntimeError("sealed vector failed its own round trip")
    if stream_module.decrypt_bytes(KEY, stream, context="kat:v3:stream") != MESSAGE * 3:
        raise RuntimeError("stream vector failed its own round trip")
    params = KdfParams(memory_blocks=64, passes=2, salt=bytes(range(32)))
    return {
        "warning": "Regression vectors freeze behavior; they do not establish cryptographic security.",
        "format": "BSR2-v3-KAT",
        "version": 1,
        "key_hex": KEY.hex(),
        "message_hex": MESSAGE.hex(),
        "fixed_randomizer_hex": FIXED_RANDOMIZER.hex(),
        "hash64": hash64(MESSAGE, b"BSR2/v3/kat", 48).hex(),
        "mac64": mac64(KEY, b"BSR2/v3/kat", MESSAGE, b"part-two", output_bytes=32).hex(),
        "keystream64": keystream64(KEY, b"kat-nonce", 200).hex(),
        "derive_keys64": [k.hex() for k in derive_keys64(KEY, b"BSR2/v3/kat", b"label", count=2)],
        "sealed_hex": sealed.hex(),
        "stream_hex": stream.hex(),
        "mhf": {
            "password": "correct horse battery staple",
            "memory_blocks": params.memory_blocks,
            "passes": params.passes,
            "salt_hex": params.salt.hex(),
            "output_hex": derive_key("correct horse battery staple", params, 32).hex(),
        },
    }


def main() -> None:
    path = Path(__file__).resolve().with_name("v3_known_answer_vectors.json")
    path.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
