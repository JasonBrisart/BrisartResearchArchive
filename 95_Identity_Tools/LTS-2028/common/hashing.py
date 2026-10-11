"""
File: common/hashing.py

Purpose
-------
SHA-256 helpers, the single canonical copy.

Public interface:
- sha256_bytes(data) -- Return the SHA-256 hex digest of a bytes object.
- sha256_file(path) -- Return the SHA-256 hex digest of a file, read in 1 MiB
  chunks.

Design notes:

Replaces the byte-identical sha256_bytes/sha256_file that were pasted into five
LabID feature modules. These are integrity fingerprints over non-secret
content; secret material goes through the BSR2 factor and envelope layers
instead.

Communication / relationships
-----------------------------
Standard library: hashlib, pathlib, typing.
Imported by:
- biometrics/engine/attachments.py
- biometrics/engine/bulk_attachments.py
- packages/custody.py
- vault/store/bulk_file_service.py
- vault/store/vault_service.py
Covered by tests: common/tests/test_common_utils.py.

Settings / parameters
---------------------
- _CHUNK_BYTES = 1024 * 1024

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- The 1 MiB streaming read is preserved so a large biometric sample is never
  loaded whole into memory.

Examples
--------
Run from the repository root.

::

    import tempfile
    from pathlib import Path

    from common.hashing import sha256_bytes, sha256_file

    print(sha256_bytes(b"hello"))

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "blob.bin"
        path.write_bytes(b"hello")
        print(sha256_file(path) == sha256_bytes(b"hello"))
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




