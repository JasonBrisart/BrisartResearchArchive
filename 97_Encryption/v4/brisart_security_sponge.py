"""
File: brisart_security_sponge.py

Purpose
-------
BSR2-S64: the incremental, rate-64 sponge that every 0.4.0 construction is built
on. It reuses the frozen 32-round BSR2 permutation and provides one hashing
object (``Sponge64``) plus four fixed modes: unkeyed hash (``hash64``), keyed
MAC (``mac64``), keystream (``keystream64``), and multi-key derivation
(``derive_keys64``).

Communication / relationships
-----------------------------
Imports ``permute_unchecked``, ``frame``, ``MASK64`` and the parameter tables from
brisart_security_primitives.py. Consumed by brisart_security_aead.py,
brisart_security_stream.py, brisart_security_kdf.py, brisart_security_keys.py,
and brisart_security_archive.py.

Settings / parameters
---------------------
S64_RATE_BYTES     64 bytes absorbed/squeezed per permutation (words 0-7).
S64_CAPACITY_BYTES 64 bytes never output (words 8-15); 512-bit capacity.
S64_IV_TWEAK       XORed into word 15 of the initial value so no BSR2-S64
                   state can coincide with a legacy rate-32 initial state.
MAX_S64_OUTPUT     16 MiB ceiling per squeeze request.

Edge cases
----------
* Absorbing after squeezing raises; a Sponge64 is absorb-then-squeeze only.
* Padding is pad10*1 inside the rate (0x80 ... 0x01, or 0x81 when they share
  one byte), so absorbing b"" and absorbing b"\\x80" produce different states.
* Every mode frames its variable-length inputs with ``frame`` so concatenation
  ambiguity is impossible.

Known limitations
-----------------
* Rate 64 / capacity 512 is a design choice that has not been analysed. The
  docs/CRYPTANALYSIS.md results cover the permutation and the legacy rate-32
  modes only.
* Throughput is about 70 KiB/s of keystream on a typical desktop CPython; this
  is research software, not a bulk cipher.

Examples
--------
>>> from brisart_security_sponge import hash64, mac64, keystream64
>>> len(hash64(b"data", b"BSR2/v3/example", 32))
32
>>> len(keystream64(bytes(32), bytes(32), 100))
100
"""

from brisart_security_primitives import (
    BrisartPrimitiveError,
    INITIAL_STATE_CONSTANT,
    MASK64,
    ROUND_CONSTANTS,
    STATE_WORDS,
    frame,
    permute_unchecked,
)

S64_RATE_BYTES = 64
S64_RATE_WORDS = 8
S64_CAPACITY_BYTES = 64
S64_IV_TWEAK = 0x4253523253363401  # "BSR2S64\x01"
MAX_S64_OUTPUT = 16 * 1024 * 1024
MIN_KEY_BYTES = 16

_IV = tuple(
    (
        (ROUND_CONSTANTS[(index + 7) % len(ROUND_CONSTANTS)] ^ ((index + 1) * INITIAL_STATE_CONSTANT))
        ^ (S64_IV_TWEAK if index == 15 else 0)
    )
    & MASK64
    for index in range(STATE_WORDS)
)
_DOMAIN_CACHE: dict[bytes, tuple[int, ...]] = {}


def _domain_state(domain: bytes) -> list[int]:
    if not isinstance(domain, bytes) or not domain:
        raise BrisartPrimitiveError("sponge domain must be non-empty bytes")
    cached = _DOMAIN_CACHE.get(domain)
    if cached is not None:
        return list(cached)
    sponge = Sponge64.__new__(Sponge64)
    sponge._state = list(_IV)
    sponge._buffer = bytearray()
    sponge._squeezing = False
    sponge._out = b""
    sponge._absorb_raw(frame(domain))
    sponge._finish_absorb()
    if len(_DOMAIN_CACHE) < 512:
        _DOMAIN_CACHE[domain] = tuple(sponge._state)
    return sponge._state


class Sponge64:
    """Incremental BSR2-S64 sponge bound to one domain string."""

    __slots__ = ("_state", "_buffer", "_squeezing", "_out")

    def __init__(self, domain: bytes):
        self._state = _domain_state(domain)
        self._buffer = bytearray()
        self._squeezing = False
        self._out = b""

    def __reduce__(self):
        raise TypeError("Sponge64 state cannot be serialized")

    def _absorb_block(self, block) -> None:
        s = self._state
        for index in range(S64_RATE_WORDS):
            s[index] ^= int.from_bytes(block[index * 8:index * 8 + 8], "big")
        permute_unchecked(s)

    def _absorb_raw(self, data) -> None:
        buffer = self._buffer
        buffer.extend(data)
        if len(buffer) < S64_RATE_BYTES:
            return
        view = memoryview(buffer)
        full = len(buffer) - (len(buffer) % S64_RATE_BYTES)
        for offset in range(0, full, S64_RATE_BYTES):
            self._absorb_block(view[offset:offset + S64_RATE_BYTES])
        view.release()
        del buffer[:full]

    def _finish_absorb(self) -> None:
        block = bytearray(self._buffer)
        block.append(0x80)
        block.extend(b"\x00" * (S64_RATE_BYTES - len(block)))
        block[-1] |= 0x01
        self._absorb_block(block)
        self._buffer = bytearray()

    def absorb(self, data: bytes) -> "Sponge64":
        if self._squeezing:
            raise BrisartPrimitiveError("cannot absorb after squeezing")
        if not isinstance(data, (bytes, bytearray)):
            raise BrisartPrimitiveError("absorbed data must be bytes")
        self._absorb_raw(data)
        return self

    def absorb_framed(self, *values: bytes) -> "Sponge64":
        for value in values:
            if not isinstance(value, bytes):
                raise BrisartPrimitiveError("framed value must be bytes")
            self.absorb(len(value).to_bytes(8, "big"))
            self.absorb(value)
        return self

    def squeeze(self, length: int) -> bytes:
        if type(length) is not int or length <= 0:
            raise BrisartPrimitiveError("squeeze length must be a positive integer")
        if length > MAX_S64_OUTPUT:
            raise BrisartPrimitiveError("squeeze length exceeds the size limit")
        if not self._squeezing:
            self._finish_absorb()
            self._squeezing = True
            self._out = self._rate_bytes()
        output = bytearray()
        while len(output) < length:
            if not self._out:
                permute_unchecked(self._state)
                self._out = self._rate_bytes()
            take = min(length - len(output), len(self._out))
            output.extend(self._out[:take])
            self._out = self._out[take:]
        return bytes(output)

    def _rate_bytes(self) -> bytes:
        s = self._state
        return b"".join(s[index].to_bytes(8, "big") for index in range(S64_RATE_WORDS))


def _require_key(key: bytes, name: str = "key") -> None:
    if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
        raise BrisartPrimitiveError(f"{name} must be bytes of at least {MIN_KEY_BYTES} bytes")


def hash64(message: bytes, domain: bytes, output_bytes: int = 32) -> bytes:
    """Unkeyed BSR2-S64 hash of ``message`` under ``domain``."""
    if not isinstance(message, (bytes, bytearray)):
        raise BrisartPrimitiveError("message must be bytes")
    return Sponge64(domain).absorb(message).squeeze(output_bytes)


def mac64(key: bytes, domain: bytes, *parts: bytes, output_bytes: int = 32) -> bytes:
    """Keyed BSR2-S64 MAC: absorb frame(key) then each part framed."""
    _require_key(key)
    sponge = Sponge64(domain)
    sponge.absorb_framed(key, *parts)
    return sponge.squeeze(output_bytes)


def keystream64(key: bytes, nonce: bytes, length: int, domain: bytes = b"BSR2/v3/keystream") -> bytes:
    """Return ``length`` keystream bytes for (key, nonce). Length 0 returns b""."""
    _require_key(key)
    if not isinstance(nonce, bytes):
        raise BrisartPrimitiveError("nonce must be bytes")
    if type(length) is not int or length < 0:
        raise BrisartPrimitiveError("keystream length must be a non-negative integer")
    if length == 0:
        return b""
    return Sponge64(domain).absorb_framed(key, nonce).squeeze(length)


def derive_keys64(master: bytes, domain: bytes, *parts: bytes, count: int = 3, size: int = 32) -> list[bytes]:
    """Derive ``count`` independent ``size``-byte keys from one keyed sponge call."""
    _require_key(master, "master key")
    if type(count) is not int or not 1 <= count <= 16:
        raise BrisartPrimitiveError("key count must be between 1 and 16")
    if type(size) is not int or not 16 <= size <= 64:
        raise BrisartPrimitiveError("key size must be between 16 and 64 bytes")
    material = mac64(master, domain, *parts, output_bytes=count * size)
    return [material[index * size:(index + 1) * size] for index in range(count)]


def xor_into(data: bytes, stream: bytes) -> bytes:
    """XOR two equal-length byte strings using big-integer arithmetic."""
    if len(data) != len(stream):
        raise BrisartPrimitiveError("XOR inputs must have equal length")
    if not data:
        return b""
    return (int.from_bytes(data, "big") ^ int.from_bytes(stream, "big")).to_bytes(len(data), "big")
