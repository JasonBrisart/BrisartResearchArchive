from brisart_security_primitives import (
    constant_time_equal,
    derive_subkey,
    frame,
    hex_decode,
    hex_encode,
    keyed_mac,
    stream_bytes,
    xor_bytes,
)


ALGORITHM = "BSR1-ARX-SPONGE-ETM"
VERSION = 1
SALT_BYTES = 32
NONCE_BYTES = 32
TAG_BYTES = 32
MAX_PLAINTEXT_BYTES = 16 * 1024 * 1024


class BrisartEnvelopeError(Exception):
    pass


def _context_bytes(context: str) -> bytes:
    if not isinstance(context, str) or not context:
        raise BrisartEnvelopeError("context must be a non-empty string")
    return context.encode("utf-8")


def _tag_input(context: bytes, salt: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    return b"".join(
        (
            frame(ALGORITHM.encode("ascii")),
            VERSION.to_bytes(4, "big"),
            frame(context),
            frame(salt),
            frame(nonce),
            frame(ciphertext),
        )
    )


def encrypt(master_key: bytes, plaintext: bytes, context: str, rng) -> dict:
    if not isinstance(master_key, bytes) or len(master_key) < 32:
        raise BrisartEnvelopeError("master key must contain at least 32 bytes")
    if not isinstance(plaintext, bytes):
        raise BrisartEnvelopeError("plaintext must be bytes")
    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise BrisartEnvelopeError("plaintext exceeds the size limit")

    if not hasattr(rng, "generate"):
        raise BrisartEnvelopeError(
            "a caller-supplied research generator is required"
        )

    context_bytes = _context_bytes(context)
    message_salt = rng.generate(
        SALT_BYTES,
        b"BSR1/envelope-v2/salt/" + context_bytes,
    )
    nonce = rng.generate(
        NONCE_BYTES,
        b"BSR1/envelope-v2/nonce/" + context_bytes,
    )
    if message_salt == nonce:
        raise BrisartEnvelopeError(
            "generator produced equal salt and nonce values"
        )
    encryption_key = derive_subkey(master_key, message_salt, b"BSR1/encryption")
    authentication_key = derive_subkey(master_key, message_salt, b"BSR1/authentication")
    ciphertext = xor_bytes(plaintext, stream_bytes(encryption_key, nonce, len(plaintext)))
    tag = keyed_mac(
        authentication_key,
        _tag_input(context_bytes, message_salt, nonce, ciphertext),
        TAG_BYTES,
    )
    return {
        "algorithm": ALGORITHM,
        "version": VERSION,
        "salt": hex_encode(message_salt),
        "nonce": hex_encode(nonce),
        "ciphertext": hex_encode(ciphertext),
        "tag": hex_encode(tag),
    }


def decrypt(master_key: bytes, envelope: dict, context: str) -> bytes:
    if not isinstance(master_key, bytes) or len(master_key) < 32:
        raise BrisartEnvelopeError("master key must contain at least 32 bytes")
    if not isinstance(envelope, dict):
        raise BrisartEnvelopeError("envelope must be an object")

    expected_fields = {"algorithm", "version", "salt", "nonce", "ciphertext", "tag"}
    if set(envelope) != expected_fields:
        raise BrisartEnvelopeError("envelope fields are invalid")
    if envelope["algorithm"] != ALGORITHM or envelope["version"] != VERSION:
        raise BrisartEnvelopeError("unsupported envelope format")

    try:
        message_salt = hex_decode(envelope["salt"])
        nonce = hex_decode(envelope["nonce"])
        ciphertext = hex_decode(envelope["ciphertext"])
        provided_tag = hex_decode(envelope["tag"])
    except Exception as exc:
        raise BrisartEnvelopeError("envelope encoding is invalid") from exc

    if len(message_salt) != SALT_BYTES or len(nonce) != NONCE_BYTES or len(provided_tag) != TAG_BYTES:
        raise BrisartEnvelopeError("envelope field length is invalid")
    if len(ciphertext) > MAX_PLAINTEXT_BYTES:
        raise BrisartEnvelopeError("ciphertext exceeds the size limit")

    context_bytes = _context_bytes(context)
    encryption_key = derive_subkey(master_key, message_salt, b"BSR1/encryption")
    authentication_key = derive_subkey(master_key, message_salt, b"BSR1/authentication")
    expected_tag = keyed_mac(
        authentication_key,
        _tag_input(context_bytes, message_salt, nonce, ciphertext),
        TAG_BYTES,
    )
    if not constant_time_equal(expected_tag, provided_tag):
        raise BrisartEnvelopeError("authentication failed")
    return xor_bytes(ciphertext, stream_bytes(encryption_key, nonce, len(ciphertext)))
