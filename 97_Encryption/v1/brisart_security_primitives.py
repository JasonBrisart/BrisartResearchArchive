MASK64 = (1 << 64) - 1
STATE_WORDS = 16
RATE_BYTES = 32
DEFAULT_ROUNDS = 32

ROUND_CONSTANTS = (
    0x243F6A8885A308D3,
    0x13198A2E03707344,
    0xA4093822299F31D0,
    0x082EFA98EC4E6C89,
    0x452821E638D01377,
    0xBE5466CF34E90C6C,
    0xC0AC29B7C97C50DD,
    0x3F84D5B5B5470917,
    0x9216D5D98979FB1B,
    0xD1310BA698DFB5AC,
    0x2FFD72DBD01ADFB7,
    0xB8E1AFED6A267E96,
    0xBA7C9045F12C7F99,
    0x24A19947B3916CF7,
    0x0801F2E2858EFC16,
    0x636920D871574E69,
    0xA458FEA3F4933D7E,
    0x0D95748F728EB658,
    0x718BCD5882154AEE,
    0x7B54A41DC25A59B5,
)

ROTATIONS = (7, 13, 19, 29, 31, 37, 43, 53)
WORD_PERMUTATION = (0, 5, 10, 15, 12, 1, 6, 11, 8, 13, 2, 7, 4, 9, 14, 3)


class BrisartPrimitiveError(ValueError):
    pass


def rotate_left(value: int, amount: int) -> int:
    amount %= 64
    value &= MASK64
    return ((value << amount) | (value >> (64 - amount))) & MASK64


def _mix_pair(state: list[int], left: int, right: int, rotation: int) -> None:
    state[left] = (state[left] + state[right]) & MASK64
    state[right] = rotate_left(state[right] ^ state[left], rotation)


def permute(state: list[int], rounds: int = DEFAULT_ROUNDS) -> None:
    if len(state) != STATE_WORDS:
        raise BrisartPrimitiveError("state must contain sixteen words")
    if rounds <= 0:
        raise BrisartPrimitiveError("round count must be positive")

    for round_index in range(rounds):
        constant = ROUND_CONSTANTS[round_index % len(ROUND_CONSTANTS)]
        state[0] ^= constant
        state[15] ^= ((round_index + 1) * 0x9E3779B97F4A7C15) & MASK64

        for index in range(0, 16, 2):
            _mix_pair(state, index, index + 1, ROTATIONS[(index // 2) % 8])
        for index in range(8):
            _mix_pair(state, index, index + 8, ROTATIONS[(index + round_index) % 8])
        for index in range(0, 16, 2):
            _mix_pair(state, index, index + 1, ROTATIONS[(index // 2 + 3) % 8])

        state[:] = [state[index] for index in WORD_PERMUTATION]

        snapshot = state[:]
        for index in range(16):
            neighbor_mix = (
                snapshot[(index + 1) % 16]
                & snapshot[(index + 2) % 16]
            ) ^ (
                (~snapshot[(index + 3) % 16])
                & snapshot[(index + 5) % 16]
            )
            state[index] ^= rotate_left(
                neighbor_mix,
                ROTATIONS[(index + round_index) % 8],
            )
            state[index] = (
                state[index]
                + rotate_left(
                    constant ^ (index * 0xD6E8FEB86659FD93),
                    (index * 7 + round_index) % 64,
                )
            ) & MASK64


def frame(value: bytes) -> bytes:
    if not isinstance(value, bytes):
        raise BrisartPrimitiveError("framed value must be bytes")
    return len(value).to_bytes(8, "big") + value


def _pad(message: bytes) -> bytes:
    if not isinstance(message, bytes):
        raise BrisartPrimitiveError("message must be bytes")
    length_bits = len(message) * 8
    padded = bytearray(message)
    padded.append(0x80)
    while (len(padded) + 8) % RATE_BYTES:
        padded.append(0)
    padded.extend(length_bits.to_bytes(8, "big"))
    return bytes(padded)


def _initial_state(domain: bytes) -> list[int]:
    state = [
        (ROUND_CONSTANTS[index % len(ROUND_CONSTANTS)] ^ (index * 0x9E3779B97F4A7C15)) & MASK64
        for index in range(STATE_WORDS)
    ]
    domain_block = frame(domain)
    for offset in range(0, len(domain_block), RATE_BYTES):
        block = domain_block[offset:offset + RATE_BYTES].ljust(RATE_BYTES, b"\x00")
        for index in range(4):
            state[index] ^= int.from_bytes(block[index * 8:(index + 1) * 8], "big")
        permute(state)
    return state


def sponge_hash(message: bytes, output_bytes: int = 32, domain: bytes = b"BSR1/hash") -> bytes:
    if output_bytes <= 0 or output_bytes > 1024:
        raise BrisartPrimitiveError("output length must be between 1 and 1024 bytes")
    state = _initial_state(domain)
    padded = _pad(message)

    for offset in range(0, len(padded), RATE_BYTES):
        block = padded[offset:offset + RATE_BYTES]
        for index in range(4):
            state[index] ^= int.from_bytes(block[index * 8:(index + 1) * 8], "big")
        permute(state)

    output = bytearray()
    while len(output) < output_bytes:
        for index in range(4):
            output.extend(state[index].to_bytes(8, "big"))
        if len(output) < output_bytes:
            permute(state)
    return bytes(output[:output_bytes])


def keyed_mac(key: bytes, message: bytes, output_bytes: int = 32) -> bytes:
    if not isinstance(key, bytes) or len(key) < 16:
        raise BrisartPrimitiveError("MAC key must contain at least sixteen bytes")
    inner = sponge_hash(frame(key) + frame(message), 64, b"BSR1/mac/inner")
    return sponge_hash(frame(key) + frame(inner) + frame(message), output_bytes, b"BSR1/mac/outer")


def derive_password_key(password: str, salt: bytes, iterations: int = 120_000, output_bytes: int = 32) -> bytes:
    if not isinstance(password, str) or not password:
        raise BrisartPrimitiveError("password must be a non-empty string")
    if not isinstance(salt, bytes) or len(salt) < 16:
        raise BrisartPrimitiveError("salt must contain at least sixteen bytes")
    if iterations < 10_000:
        raise BrisartPrimitiveError("iteration count is below the research minimum")

    password_bytes = password.encode("utf-8")
    state = sponge_hash(frame(password_bytes) + frame(salt), 64, b"BSR1/kdf/start")
    for index in range(iterations):
        state = sponge_hash(
            frame(password_bytes)
            + frame(salt)
            + index.to_bytes(8, "big")
            + frame(state),
            64,
            b"BSR1/kdf/round",
        )
    return sponge_hash(frame(state) + frame(salt), output_bytes, b"BSR1/kdf/final")


def derive_subkey(master_key: bytes, salt: bytes, purpose: bytes, output_bytes: int = 32) -> bytes:
    return keyed_mac(master_key, frame(salt) + frame(purpose), output_bytes)


def stream_bytes(key: bytes, nonce: bytes, length: int) -> bytes:
    if length < 0:
        raise BrisartPrimitiveError("stream length cannot be negative")
    output = bytearray()
    counter = 0
    while len(output) < length:
        output.extend(
            keyed_mac(
                key,
                frame(nonce) + counter.to_bytes(8, "big"),
                64,
            )
        )
        counter += 1
    return bytes(output[:length])


def xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise BrisartPrimitiveError("XOR inputs must have equal length")
    return bytes(a ^ b for a, b in zip(left, right))


def constant_time_equal(left: bytes, right: bytes) -> bool:
    if not isinstance(left, bytes) or not isinstance(right, bytes):
        return False
    difference = len(left) ^ len(right)
    maximum = max(len(left), len(right))
    for index in range(maximum):
        a = left[index] if index < len(left) else 0
        b = right[index] if index < len(right) else 0
        difference |= a ^ b
    return difference == 0



_HEX_ALPHABET = "0123456789abcdef"


def hex_encode(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise BrisartPrimitiveError("hex input must be bytes")
    characters = []
    for value in data:
        characters.append(_HEX_ALPHABET[value >> 4])
        characters.append(_HEX_ALPHABET[value & 15])
    return "".join(characters)


def hex_decode(text: str) -> bytes:
    if not isinstance(text, str) or len(text) % 2:
        raise BrisartPrimitiveError("hex input must have even length")
    if text != text.lower():
        raise BrisartPrimitiveError("hex input must be canonical lowercase")
    values = bytearray()
    for index in range(0, len(text), 2):
        pair = text[index:index + 2]
        if pair[0] not in _HEX_ALPHABET or pair[1] not in _HEX_ALPHABET:
            raise BrisartPrimitiveError("hex input contains invalid characters")
        values.append((_HEX_ALPHABET.index(pair[0]) << 4) | _HEX_ALPHABET.index(pair[1]))
    return bytes(values)
