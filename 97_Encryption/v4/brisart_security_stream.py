"""
File: brisart_security_stream.py

Purpose
-------
BSR-STREAM-1: chunked authenticated encryption for inputs of any size, built on
BSR2-S64. Each chunk is sealed SIV-style with its index and a final-chunk flag
bound into the tag, so reordering, dropping, duplicating, truncating, or
extending chunks is detected (the STREAM construction pattern). Archive
entries and the CLI ``encrypt``/``decrypt`` commands use this format.

Wire format::

    header  = "BSRS" | ver=1 | suite=1 | flags=0 | rsv=0 | u32 chunk_size
              | randomizer(32) | commitment(32) | header_tag(32)      (108 bytes)
    record  = tag(32) | chunk ciphertext       (chunk_size bytes except last)
    keys    = derive_keys64(key, "BSR2/v3/stream/keys", header[:12], randomizer)
    tag_i   = mac64(mac, "BSR2/v3/stream/chunk", u64(i)|final, header_tag, p_i)
    c_i     = p_i XOR keystream64(enc, tag_i | u64(i) | final)

Communication / relationships
-----------------------------
Imports brisart_security_sponge.py, brisart_security_primitives.py
(``constant_time_equal``), and brisart_security_entropy.py. Used by
brisart_security_archive.py and brisart_security_cli.py; covered by
tests/test_stream_v3.py.

Settings / parameters
---------------------
DEFAULT_CHUNK_SIZE 65,536; MIN_CHUNK_SIZE 64; MAX_CHUNK_SIZE 16 MiB
MAX_CHUNKS 2**40; HEADER_BYTES 108; TAG_BYTES 32
MAX_CONTEXT_BYTES 4096; MAX_ASSOCIATED_DATA_BYTES 1 MiB

Edge cases
----------
* Empty input produces exactly one empty final chunk.
* An input whose length is a multiple of the chunk size ends with a full-size
  final chunk; the reader detects it by EOF look-ahead, and the final flag in
  the tag makes a cut at a chunk boundary fail authentication.
* ``decrypt_stream`` rejects a header chunk size above ``max_chunk_size`` before
  allocating anything, and rejects any byte after the final chunk.

Known limitations
-----------------
* ``decrypt_stream`` writes each chunk as soon as that chunk verifies. A
  truncated stream is reported at the end, after earlier chunks were written.
  Callers that need all-or-nothing output must write to a temporary file and
  rename on success (the CLI does this).
* Unanalysed construction; research use only.

Examples
--------
>>> from brisart_security_stream import encrypt_bytes, decrypt_bytes
>>> key = bytes(range(32))
>>> blob = encrypt_bytes(key, b"x" * 1000, context="file:demo", chunk_size=256)
>>> decrypt_bytes(key, blob, context="file:demo")[:3]
b'xxx'
"""
import io

from brisart_security_entropy import BrisartEntropyError, system_entropy
from brisart_security_primitives import constant_time_equal
from brisart_security_sponge import derive_keys64, keystream64, mac64, xor_into

MAGIC = b"BSRS"
FORMAT_VERSION = 1
SUITE_ID = 1
TAG_BYTES = 32
RANDOMIZER_BYTES = 32
HEADER_BYTES = 12 + RANDOMIZER_BYTES + 32 + TAG_BYTES
DEFAULT_CHUNK_SIZE = 64 * 1024
MIN_CHUNK_SIZE = 64
MAX_CHUNK_SIZE = 16 * 1024 * 1024
MAX_CHUNKS = 1 << 40
MIN_KEY_BYTES = 32
MAX_KEY_BYTES = 1024
MAX_CONTEXT_BYTES = 4096
MAX_ASSOCIATED_DATA_BYTES = 1024 * 1024


class BrisartStreamError(Exception):
    """Raised when stream encryption or decryption fails."""


def _require_key(key: bytes) -> None:
    if not isinstance(key, bytes) or not MIN_KEY_BYTES <= len(key) <= MAX_KEY_BYTES:
        raise BrisartStreamError("key must be 32 to 1024 bytes")


def _context(context: str) -> bytes:
    if not isinstance(context, str) or not context:
        raise BrisartStreamError("context must be a non-empty string")
    try:
        data = context.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BrisartStreamError("context is not valid UTF-8 text") from exc
    if len(data) > MAX_CONTEXT_BYTES:
        raise BrisartStreamError("context exceeds the size limit")
    return data


def _ad(value: bytes) -> bytes:
    if not isinstance(value, bytes):
        raise BrisartStreamError("associated data must be bytes")
    if len(value) > MAX_ASSOCIATED_DATA_BYTES:
        raise BrisartStreamError("associated data exceeds the size limit")
    return value


def _read_exact(source, size: int) -> bytes:
    parts = []
    remaining = size
    while remaining:
        block = source.read(remaining)
        if not block:
            break
        if not isinstance(block, (bytes, bytearray)):
            raise BrisartStreamError("source must be opened in binary mode")
        parts.append(bytes(block))
        remaining -= len(block)
    return b"".join(parts)


def _chunk_tag(mac_key: bytes, index: int, final: bool, header_tag: bytes, data: bytes) -> bytes:
    position = index.to_bytes(8, "big") + (b"\x01" if final else b"\x00")
    return mac64(mac_key, b"BSR2/v3/stream/chunk", position, header_tag, data, output_bytes=TAG_BYTES)


def _chunk_stream(enc_key: bytes, tag: bytes, index: int, final: bool, length: int) -> bytes:
    nonce = tag + index.to_bytes(8, "big") + (b"\x01" if final else b"\x00")
    return keystream64(enc_key, nonce, length, b"BSR2/v3/stream/keystream")


def _derive(key: bytes, prefix: bytes) -> list[bytes]:
    return derive_keys64(key, b"BSR2/v3/stream/keys", prefix[:12], prefix[12:44], count=3)


def _header_tag(mac_key: bytes, prefix: bytes, commitment: bytes, context: bytes, ad: bytes) -> bytes:
    return mac64(mac_key, b"BSR2/v3/stream/header", prefix + commitment, context, ad, output_bytes=TAG_BYTES)


def encrypt_stream(
    key: bytes,
    source,
    destination,
    *,
    context: str,
    associated_data: bytes = b"",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rng=None,
) -> int:
    """Encrypt everything readable from ``source`` into ``destination``.

    Returns the number of plaintext bytes processed.
    """
    _require_key(key)
    context_bytes = _context(context)
    ad = _ad(associated_data)
    if type(chunk_size) is not int or not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise BrisartStreamError("chunk size must be between 64 bytes and 16 MiB")
    try:
        randomizer = system_entropy(RANDOMIZER_BYTES)
    except BrisartEntropyError as exc:
        raise BrisartStreamError("fresh entropy failed while producing randomizer") from exc
    if rng is not None:
        try:
            contribution = rng.generate(RANDOMIZER_BYTES, b"BSR2/v3/stream/randomizer/" + context_bytes[:256])
        except Exception as exc:
            raise BrisartStreamError("generator failed while producing randomizer") from exc
        if not isinstance(contribution, bytes) or len(contribution) != RANDOMIZER_BYTES:
            raise BrisartStreamError("generator randomizer must be exactly 32 bytes")
        randomizer = xor_into(randomizer, contribution)
    prefix = MAGIC + bytes((FORMAT_VERSION, SUITE_ID, 0, 0)) + chunk_size.to_bytes(4, "big") + randomizer
    enc_key, mac_key, commitment = _derive(key, prefix)
    header_tag = _header_tag(mac_key, prefix, commitment, context_bytes, ad)
    destination.write(prefix + commitment + header_tag)
    total = 0
    index = 0
    current = _read_exact(source, chunk_size)
    while True:
        following = _read_exact(source, chunk_size) if len(current) == chunk_size else b""
        final = not following
        if index >= MAX_CHUNKS:
            raise BrisartStreamError("stream exceeds the chunk limit")
        tag = _chunk_tag(mac_key, index, final, header_tag, current)
        destination.write(tag + xor_into(current, _chunk_stream(enc_key, tag, index, final, len(current))))
        total += len(current)
        index += 1
        if final:
            return total
        current = following


def read_header(source, *, max_chunk_size: int = MAX_CHUNK_SIZE) -> tuple[bytes, int]:
    """Read and structurally validate a stream header. Returns (header, chunk_size)."""
    header = _read_exact(source, HEADER_BYTES)
    if len(header) != HEADER_BYTES or header[:4] != MAGIC:
        raise BrisartStreamError("not a BSR stream")
    if header[4] != FORMAT_VERSION or header[5] != SUITE_ID:
        raise BrisartStreamError("unsupported stream format")
    if header[6] or header[7]:
        raise BrisartStreamError("reserved stream header bits are set")
    chunk_size = int.from_bytes(header[8:12], "big")
    if not MIN_CHUNK_SIZE <= chunk_size <= min(max_chunk_size, MAX_CHUNK_SIZE):
        raise BrisartStreamError("stream chunk size is outside the permitted range")
    return header, chunk_size


def decrypt_stream(
    key: bytes,
    source,
    destination,
    *,
    context: str,
    associated_data: bytes = b"",
    max_chunk_size: int = MAX_CHUNK_SIZE,
    max_plaintext_bytes: int | None = None,
) -> int:
    """Verify and decrypt a BSR-STREAM-1 stream. Returns plaintext byte count."""
    _require_key(key)
    context_bytes = _context(context)
    ad = _ad(associated_data)
    header, chunk_size = read_header(source, max_chunk_size=max_chunk_size)
    prefix = header[:44]
    commitment = header[44:76]
    provided_header_tag = header[76:HEADER_BYTES]
    enc_key, mac_key, expected_commitment = _derive(key, prefix)
    if not constant_time_equal(expected_commitment, commitment):
        raise BrisartStreamError("authentication failed")
    header_tag = _header_tag(mac_key, prefix, expected_commitment, context_bytes, ad)
    if not constant_time_equal(header_tag, provided_header_tag):
        raise BrisartStreamError("authentication failed")
    record_size = TAG_BYTES + chunk_size
    total = 0
    index = 0
    current = _read_exact(source, record_size)
    while True:
        if len(current) < TAG_BYTES:
            raise BrisartStreamError("stream is truncated")
        following = _read_exact(source, record_size) if len(current) == record_size else b""
        final = not following
        tag = current[:TAG_BYTES]
        ciphertext = current[TAG_BYTES:]
        plaintext = xor_into(ciphertext, _chunk_stream(enc_key, tag, index, final, len(ciphertext)))
        expected = _chunk_tag(mac_key, index, final, header_tag, plaintext)
        if not constant_time_equal(expected, tag):
            raise BrisartStreamError("authentication failed")
        total += len(plaintext)
        if max_plaintext_bytes is not None and total > max_plaintext_bytes:
            raise BrisartStreamError("stream exceeds the permitted plaintext size")
        destination.write(plaintext)
        index += 1
        if index > MAX_CHUNKS:
            raise BrisartStreamError("stream exceeds the chunk limit")
        if final:
            if source.read(1):
                raise BrisartStreamError("trailing data after final chunk")
            return total
        current = following


def encrypt_bytes(key: bytes, data: bytes, *, context: str, associated_data: bytes = b"", chunk_size: int = DEFAULT_CHUNK_SIZE, rng=None) -> bytes:
    if not isinstance(data, bytes):
        raise BrisartStreamError("data must be bytes")
    output = io.BytesIO()
    encrypt_stream(key, io.BytesIO(data), output, context=context, associated_data=associated_data, chunk_size=chunk_size, rng=rng)
    return output.getvalue()


def decrypt_bytes(key: bytes, blob: bytes, *, context: str, associated_data: bytes = b"", max_plaintext_bytes: int | None = None) -> bytes:
    if not isinstance(blob, bytes):
        raise BrisartStreamError("blob must be bytes")
    source = io.BytesIO(blob)
    output = io.BytesIO()
    decrypt_stream(key, source, output, context=context, associated_data=associated_data, max_plaintext_bytes=max_plaintext_bytes)
    return output.getvalue()
