"""
File: common/hashing.py

Purpose
-------
SHA-256 helpers, the single canonical copy.

Communication / relationships
-----------------------------
Direct module imports: hashlib, pathlib, typing.

Settings / parameters
---------------------
Module-level named settings: _CHUNK_BYTES. See their definitions below for values.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.

Additional module documentation
-------------------------------
SHA-256 helpers, the single canonical copy.

Replaces the byte-identical sha256_bytes/sha256_file that were pasted into five
LabID feature modules. The 1 MiB streaming read is preserved so a large
biometric sample is never loaded whole into memory. These are integrity
fingerprints over non-secret content; secret material goes through the BSR2
factor and envelope layers instead.
"""

import hashlib
from pathlib import Path
from typing import Union

_CHUNK_BYTES = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of a bytes object."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Union[str, Path]) -> str:
    """Return the SHA-256 hex digest of a file, read in 1 MiB chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()

