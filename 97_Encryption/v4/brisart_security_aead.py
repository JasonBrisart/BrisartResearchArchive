"""
File: brisart_security_aead.py

Purpose
-------
Sealed-message format version 3 (suite ``BSR2-S64-SIV``): binary, key-committing,
nonce-misuse-resistant authenticated encryption with associated data and
optional length-hiding padding. This is the recommended single-message format
from release 0.4.0 onward; the legacy JSON envelope stays in
brisart_security_envelope.py.

Construction (all keyed calls are BSR2-S64, see brisart_security_sponge.py)::

    prefix      = MAGIC | version | suite | flags | padding | randomizer(32)
    enc, mac, c = derive_keys64(key, "BSR2/v3/seal/keys", prefix[:8], randomizer)
    payload     = u64(len(plaintext)) | plaintext | zero padding
    siv         = mac64(mac, "BSR2/v3/seal/siv", prefix | c, context, ad, payload)
    ciphertext  = payload XOR keystream64(enc, siv)
    sealed      = prefix | c | siv | ciphertext

Because the keystream nonce is a MAC of the whole message, a repeated
randomizer (entropy failure plus a replayed DRBG) no longer repeats the
keystream for different messages. Only identical messages under identical
inputs produce identical output.

Communication / relationships
-----------------------------
Imports brisart_security_sponge.py (keyed modes), brisart_security_primitives.py
(``constant_time_equal``, hex helpers), and brisart_security_entropy.py.
Used by brisart_security_archive.py (encrypted directory), the CLI
``seal``/``unseal`` commands, and tests/test_aead_v3.py.

Settings / parameters
---------------------
MAGIC b"BSRE", FORMAT_VERSION 3, SUITE_ID 1 ("BSR2-S64-SIV")
HEADER_BYTES 104 (40-byte prefix + 32 commitment + 32 SIV)
PADDING_NONE 0, PADDING_PADME 1, PADDING_BLOCK 2 (256-byte blocks)
MAX_CONTEXT_BYTES 4096, MAX_ASSOCIATED_DATA_BYTES 1 MiB,
MAX_PLAINTEXT_BYTES 16 MiB, MIN_KEY_BYTES 32, MAX_KEY_BYTES 1024

Edge cases
----------
* Every failure after parsing (wrong key, wrong context, wrong associated data,
  any modified byte, truncation, non-canonical padding) raises the same
  "authentication failed" message.
* Reserved flag bits and unknown padding ids are rejected before key use.
* Padding bytes must be zero and the padded size must be the canonical size
  for the declared length, so there is exactly one valid encoding per message.
* Plaintext is never returned before the SIV verifies.

Known limitations
-----------------
* SIV needs two passes over the payload; throughput is roughly half the raw
  keystream rate.
* Identical (key, randomizer, context, ad, plaintext) tuples produce identical
  output by design (deterministic-AE leakage only under total entropy failure).
* The construction is new in 0.4.0 and has not been independently analysed.

Examples
--------
>>> from brisart_security_aead import seal, unseal
>>> key = bytes(range(32))
>>> blob = seal(key, b"secret", "notes:1", associated_data=b"hdr")
>>> unseal(key, blob, "notes:1", associated_data=b"hdr")
b'secret'
"""
from brisart_security_entropy import BrisartEntropyError, system_entropy
from brisart_security_primitives import BrisartPrimitiveError, constant_time_equal, hex_decode, hex_encode
from brisart_security_sponge import derive_keys64, hash64, keystream64, mac64, xor_into

MAGIC = b"BSRE"
FORMAT_VERSION = 3
SUITE_ID = 1
SUITE_NAME = "BSR2-S64-SIV"
RANDOMIZER_BYTES = 32
COMMITMENT_BYTES = 32
SIV_BYTES = 32
PREFIX_BYTES = 8 + RANDOMIZER_BYTES
HEADER_BYTES = PREFIX_BYTES + COMMITMENT_BYTES + SIV_BYTES
LENGTH_FIELD_BYTES = 8

PADDING_NONE = 0
PADDING_PADME = 1
PADDING_BLOCK = 2
PADDING_BLOCK_SIZE = 256
PADDING_NAMES = {"none": PADDING_NONE, "padme": PADDING_PADME, "block": PADDING_BLOCK}

MIN_KEY_BYTES = 32
MAX_KEY_BYTES = 1024
MAX_CONTEXT_BYTES = 4096
MAX_ASSOCIATED_DATA_BYTES = 1024 * 1024
MAX_PLAINTEXT_BYTES = 16 * 1024 * 1024

ARMOR_BEGIN = "-----BEGIN BSR2 SEALED MESSAGE-----"
ARMOR_END = "-----END BSR2 SEALED MESSAGE-----"
ARMOR_LINE = 64


class BrisartSealError(Exception):
    """Raised when sealing or unsealing fails validation or authentication."""


def _require_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
        raise BrisartSealError(f"key must be bytes of at least {MIN_KEY_BYTES} bytes")
    if len(key) > MAX_KEY_BYTES:
        raise BrisartSealError("key exceeds the size limit")


def _context_bytes(context: str) -> bytes:
    if not isinstance(context, str) or not context:
        raise BrisartSealError("context must be a non-empty string")
    try:
        encoded = context.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BrisartSealError("context is not valid UTF-8 text") from exc
    if len(encoded) > MAX_CONTEXT_BYTES:
        raise BrisartSealError("context exceeds the size limit")
    return encoded


def _require_associated_data(value: bytes) -> bytes:
    if not isinstance(value, bytes):
        raise BrisartSealError("associated data must be bytes")
    if len(value) > MAX_ASSOCIATED_DATA_BYTES:
        raise BrisartSealError("associated data exceeds the size limit")
    return value


def padme_length(length: int) -> int:
    """Padmé padded length (leaks O(log log L) bits of L)."""
    if length < 2:
        return length
    exponent = length.bit_length() - 1
    size_bits = exponent.bit_length()
    last_bits = exponent - size_bits
    mask = (1 << last_bits) - 1
    return (length + mask) & ~mask


def padded_payload_length(payload_length: int, padding: int) -> int:
    if padding == PADDING_NONE:
        return payload_length
    if padding == PADDING_PADME:
        return padme_length(payload_length)
    if padding == PADDING_BLOCK:
        return -(-payload_length // PADDING_BLOCK_SIZE) * PADDING_BLOCK_SIZE
    raise BrisartSealError("unknown padding policy")


def _randomizer(rng, context: bytes) -> bytes:
    try:
        fresh = system_entropy(RANDOMIZER_BYTES)
    except BrisartEntropyError as exc:
        raise BrisartSealError("fresh entropy failed while producing randomizer") from exc
    if rng is None:
        return fresh
    if not callable(getattr(rng, "generate", None)):
        raise BrisartSealError("rng must provide generate(length, additional_input)")
    try:
        contribution = rng.generate(RANDOMIZER_BYTES, b"BSR2/v3/seal/randomizer/" + context[:256])
    except Exception as exc:
        raise BrisartSealError("generator failed while producing randomizer") from exc
    if not isinstance(contribution, bytes) or len(contribution) != RANDOMIZER_BYTES:
        raise BrisartSealError("generator randomizer must be exactly 32 bytes")
    return xor_into(fresh, contribution)


def _keys(key: bytes, prefix: bytes) -> list[bytes]:
    return derive_keys64(key, b"BSR2/v3/seal/keys", prefix[:8], prefix[8:PREFIX_BYTES], count=3)


def _siv(mac_key: bytes, prefix: bytes, commitment: bytes, context: bytes, ad: bytes, payload: bytes) -> bytes:
    return mac64(mac_key, b"BSR2/v3/seal/siv", prefix + commitment, context, ad, payload, output_bytes=SIV_BYTES)


def seal(
    key: bytes,
    plaintext: bytes,
    context: str,
    *,
    associated_data: bytes = b"",
    rng=None,
    padding: str = "none",
) -> bytes:
    """Encrypt and authenticate ``plaintext`` into a version 3 sealed message."""
    _require_key(key)
    if not isinstance(plaintext, bytes):
        raise BrisartSealError("plaintext must be bytes")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise BrisartSealError("plaintext exceeds the size limit")
    if padding not in PADDING_NAMES:
        raise BrisartSealError("padding must be 'none', 'padme', or 'block'")
    padding_id = PADDING_NAMES[padding]
    context_bytes = _context_bytes(context)
    ad = _require_associated_data(associated_data)
    randomizer = _randomizer(rng, context_bytes)
    prefix = MAGIC + bytes((FORMAT_VERSION, SUITE_ID, 0, padding_id)) + randomizer
    enc_key, mac_key, commitment = _keys(key, prefix)
    body_length = LENGTH_FIELD_BYTES + len(plaintext)
    total = padded_payload_length(body_length, padding_id)
    payload = len(plaintext).to_bytes(8, "big") + plaintext + bytes(total - body_length)
    siv = _siv(mac_key, prefix, commitment, context_bytes, ad, payload)
    ciphertext = xor_into(payload, keystream64(enc_key, siv, len(payload), b"BSR2/v3/seal/stream"))
    return prefix + commitment + siv + ciphertext


def inspect_sealed(sealed: bytes) -> dict:
    """Parse the public header of a sealed message without using any key."""
    if not isinstance(sealed, bytes):
        raise BrisartSealError("sealed message must be bytes")
    if len(sealed) < HEADER_BYTES + LENGTH_FIELD_BYTES:
        raise BrisartSealError("sealed message is truncated")
    if sealed[:4] != MAGIC:
        raise BrisartSealError("not a BSR2 sealed message")
    version, suite, flags, padding_id = sealed[4], sealed[5], sealed[6], sealed[7]
    if version != FORMAT_VERSION or suite != SUITE_ID:
        raise BrisartSealError("unsupported sealed-message format")
    if flags != 0:
        raise BrisartSealError("reserved flag bits are set")
    if padding_id not in PADDING_NAMES.values():
        raise BrisartSealError("unknown padding policy")
    padding_name = next(name for name, value in PADDING_NAMES.items() if value == padding_id)
    return {
        "format_version": version,
        "suite": SUITE_NAME,
        "padding": padding_name,
        "randomizer_hex": hex_encode(sealed[8:PREFIX_BYTES]),
        "payload_bytes": len(sealed) - HEADER_BYTES,
        "total_bytes": len(sealed),
    }


def unseal(
    key: bytes,
    sealed: bytes,
    context: str,
    *,
    associated_data: bytes = b"",
    max_plaintext_bytes: int = MAX_PLAINTEXT_BYTES,
) -> bytes:
    """Verify and decrypt a version 3 sealed message."""
    _require_key(key)
    info = inspect_sealed(sealed)
    if type(max_plaintext_bytes) is not int or max_plaintext_bytes < 0:
        raise BrisartSealError("max_plaintext_bytes must be a non-negative integer")
    limit = min(max_plaintext_bytes, MAX_PLAINTEXT_BYTES)
    if info["payload_bytes"] > padded_payload_length(LENGTH_FIELD_BYTES + limit, PADDING_NAMES[info["padding"]]):
        raise BrisartSealError("sealed message exceeds the size limit")
    context_bytes = _context_bytes(context)
    ad = _require_associated_data(associated_data)
    prefix = sealed[:PREFIX_BYTES]
    commitment = sealed[PREFIX_BYTES:PREFIX_BYTES + COMMITMENT_BYTES]
    provided_siv = sealed[PREFIX_BYTES + COMMITMENT_BYTES:HEADER_BYTES]
    ciphertext = sealed[HEADER_BYTES:]
    enc_key, mac_key, expected_commitment = _keys(key, prefix)
    if not constant_time_equal(expected_commitment, commitment):
        raise BrisartSealError("authentication failed")
    payload = xor_into(ciphertext, keystream64(enc_key, provided_siv, len(ciphertext), b"BSR2/v3/seal/stream"))
    expected_siv = _siv(mac_key, prefix, commitment, context_bytes, ad, payload)
    if not constant_time_equal(expected_siv, provided_siv):
        raise BrisartSealError("authentication failed")
    length = int.from_bytes(payload[:LENGTH_FIELD_BYTES], "big")
    body_length = LENGTH_FIELD_BYTES + length
    if (
        body_length > len(payload)
        or length > limit
        or padded_payload_length(body_length, PADDING_NAMES[info["padding"]]) != len(payload)
        or any(payload[body_length:])
    ):
        raise BrisartSealError("authentication failed")
    return payload[LENGTH_FIELD_BYTES:body_length]


def armor(sealed: bytes) -> str:
    """Wrap a sealed message as line-broken lowercase hex with a checksum line."""
    inspect_sealed(sealed)
    text = hex_encode(sealed)
    lines = [ARMOR_BEGIN]
    lines.extend(text[i:i + ARMOR_LINE] for i in range(0, len(text), ARMOR_LINE))
    lines.append("=" + hex_encode(hash64(sealed, b"BSR2/v3/armor/checksum", 4)))
    lines.append(ARMOR_END)
    return "\n".join(lines) + "\n"


def dearmor(text: str) -> bytes:
    """Reverse ``armor``; the checksum catches transport damage, not attacks."""
    if not isinstance(text, str):
        raise BrisartSealError("armored text must be a string")
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 4 or lines[0] != ARMOR_BEGIN or lines[-1] != ARMOR_END:
        raise BrisartSealError("armor markers are missing")
    checksum_line = lines[-2]
    if not checksum_line.startswith("="):
        raise BrisartSealError("armor checksum line is missing")
    try:
        sealed = hex_decode("".join(lines[1:-2]))
        checksum = hex_decode(checksum_line[1:])
    except BrisartPrimitiveError as exc:
        raise BrisartSealError("armor body is not canonical hex") from exc
    if not constant_time_equal(hash64(sealed, b"BSR2/v3/armor/checksum", 4), checksum):
        raise BrisartSealError("armor checksum mismatch")
    inspect_sealed(sealed)
    return sealed
