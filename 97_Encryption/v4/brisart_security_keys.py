"""
File: brisart_security_keys.py

Purpose
-------
Key material handling for the Brisart Research Archive 97_Encryption tooling:
generation of fresh symmetric keys, human-comparable fingerprints, and the
BSR2-KEYFILE version 1 on-disk format with integrity checks and owner-only
permissions.

Communication / relationships
-----------------------------
Imports ``system_entropy`` (brisart_security_entropy.py), ``hash64``/``xor_into``
(brisart_security_sponge.py), and hex helpers (brisart_security_primitives.py).
Used by brisart_security_cli.py (``keygen``, ``fingerprint``, every
``--key-file`` option) and tests/test_keys_and_cli.py.

Settings / parameters
---------------------
KEYFILE_FORMAT "BSR2-KEYFILE", KEYFILE_VERSION 1
DEFAULT_KEY_BYTES 32; MIN_KEY_BYTES 32; MAX_KEY_BYTES 128
MAX_KEYFILE_BYTES 65,536
FINGERPRINT_BYTES 16, printed as eight dash-separated 4-hex-digit groups

Edge cases
----------
* Key files are created with O_CREAT | O_EXCL and mode 0600; an existing file
  is never overwritten unless ``overwrite=True``.
* Loading verifies format, version, canonical hex, key length, the stored
  fingerprint, and a checksum over every field, so a hand-edited or truncated
  file is rejected instead of silently producing a different key.
* ``permission_warning`` reports group/other-readable key files on POSIX.

Known limitations
-----------------
Key files are stored unencrypted; protect them with filesystem permissions or
keep them on removable media in air-gapped workflows. Python cannot reliably
erase key copies from memory.

Examples
--------
>>> from brisart_security_keys import generate_key, fingerprint
>>> key = generate_key()
>>> len(key), len(fingerprint(key))
(32, 39)
"""
import json
import os
import stat

from brisart_security_entropy import system_entropy
from brisart_security_primitives import BrisartPrimitiveError, constant_time_equal, hex_decode, hex_encode
from brisart_security_sponge import hash64, xor_into

KEYFILE_FORMAT = "BSR2-KEYFILE"
KEYFILE_VERSION = 1
DEFAULT_KEY_BYTES = 32
MIN_KEY_BYTES = 32
MAX_KEY_BYTES = 128
MAX_KEYFILE_BYTES = 64 * 1024
FINGERPRINT_BYTES = 16
MAX_LABEL_CHARS = 256


class BrisartKeyError(Exception):
    """Raised for invalid keys or key files."""


def generate_key(length: int = DEFAULT_KEY_BYTES, rng=None) -> bytes:
    """Fresh key from OS entropy, optionally XORed with a caller DRBG."""
    if type(length) is not int or not MIN_KEY_BYTES <= length <= MAX_KEY_BYTES:
        raise BrisartKeyError("key length must be between 32 and 128 bytes")
    key = system_entropy(length)
    if rng is not None:
        key = xor_into(key, rng.generate(length, b"BSR2/v3/keygen"))
    return key


def fingerprint(key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
        raise BrisartKeyError("key must be at least 32 bytes")
    digest = hex_encode(hash64(key, b"BSR2/v3/key-fingerprint", FINGERPRINT_BYTES))
    return "-".join(digest[i:i + 4] for i in range(0, len(digest), 4))


def _checksum(label: str, key_hex: str, fingerprint_text: str) -> str:
    material = json.dumps([KEYFILE_FORMAT, KEYFILE_VERSION, label, key_hex, fingerprint_text]).encode("utf-8")
    return hex_encode(hash64(material, b"BSR2/v3/keyfile-check", 8))


def serialize_keyfile(key: bytes, *, label: str = "") -> bytes:
    if not isinstance(label, str) or len(label) > MAX_LABEL_CHARS or any(ord(c) < 32 for c in label):
        raise BrisartKeyError("label must be printable text of at most 256 characters")
    fp = fingerprint(key)
    if len(key) > MAX_KEY_BYTES:
        raise BrisartKeyError("key exceeds the size limit")
    key_hex = hex_encode(key)
    document = {
        "format": KEYFILE_FORMAT,
        "version": KEYFILE_VERSION,
        "label": label,
        "key": key_hex,
        "fingerprint": fp,
        "check": _checksum(label, key_hex, fp),
    }
    return (json.dumps(document, indent=2) + "\n").encode("utf-8")


def save_keyfile(path: str, key: bytes, *, label: str = "", overwrite: bool = False) -> str:
    data = serialize_keyfile(key, label=label)
    path = os.fspath(path)
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_BINARY", 0)
    flags |= os.O_TRUNC if overwrite else os.O_EXCL
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise BrisartKeyError(f"refusing to overwrite existing key file: {path}") from exc
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    if os.name == "posix":
        os.chmod(path, 0o600)
    return fingerprint(key)


def parse_keyfile(data: bytes) -> tuple[bytes, dict]:
    if not isinstance(data, bytes) or len(data) > MAX_KEYFILE_BYTES:
        raise BrisartKeyError("key file is too large")
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BrisartKeyError("key file is not valid JSON") from exc
    expected = {"format", "version", "label", "key", "fingerprint", "check"}
    if not isinstance(document, dict) or set(document) != expected:
        raise BrisartKeyError("key file fields are invalid")
    if document["format"] != KEYFILE_FORMAT or document["version"] != KEYFILE_VERSION or type(document["version"]) is not int:
        raise BrisartKeyError("unsupported key file format")
    if not all(isinstance(document[k], str) for k in ("label", "key", "fingerprint", "check")):
        raise BrisartKeyError("key file fields have the wrong types")
    try:
        key = hex_decode(document["key"])
    except BrisartPrimitiveError as exc:
        raise BrisartKeyError("key file key is not canonical hex") from exc
    if not MIN_KEY_BYTES <= len(key) <= MAX_KEY_BYTES:
        raise BrisartKeyError("key file key has an invalid length")
    check = _checksum(document["label"], document["key"], document["fingerprint"])
    if not constant_time_equal(check.encode(), document["check"].encode()):
        raise BrisartKeyError("key file checksum mismatch (file edited or damaged)")
    if fingerprint(key) != document["fingerprint"]:
        raise BrisartKeyError("key file fingerprint mismatch")
    return key, {"label": document["label"], "fingerprint": document["fingerprint"]}


def load_keyfile(path: str) -> bytes:
    with open(os.fspath(path), "rb") as handle:
        data = handle.read(MAX_KEYFILE_BYTES + 1)
    return parse_keyfile(data)[0]


def permission_warning(path: str) -> str | None:
    if os.name != "posix":
        return None
    mode = os.stat(os.fspath(path)).st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return f"key file {path} is accessible by group/other (mode {oct(mode & 0o777)}); chmod 600 recommended"
    return None
