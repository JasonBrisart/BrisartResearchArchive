"""
File: brisart_security_kdf.py

Purpose
-------
BSR2-MHF-1, the memory-hard password key-derivation function introduced in
release 0.4.0. It closes the "not memory-hard" limitation of the legacy
iterated KDF (``derive_password_key`` in brisart_security_primitives.py) with a
scrypt-ROMix-style fill-then-mix over 128-byte blocks, using the BSR2
permutation reduced to 8 rounds as the block function, plus a write-back so
each pass mutates the table it reads.

Algorithm::

    X      = S64("BSR2/v3/mhf/init", nfc(password), salt, params) -> 128 bytes
    for i in 0..m-1:      V[i] = X;  X = F(X, i)
    for k in 0..m*t-1:    j = X[0] mod m;  X = F(X xor V[j], m + k);  V[j] = X
    key    = S64("BSR2/v3/mhf/final", X, nfc(password), salt) -> output_bytes
    F(B,c) = P8(B with c folded into word 15) xor B      (feed-forward)

Communication / relationships
-----------------------------
Imports ``permute_unchecked`` from brisart_security_primitives.py and
``Sponge64`` from brisart_security_sponge.py. Used by
brisart_security_archive.py (password-protected archives), the CLI
(``--password`` paths and ``kdf-bench``), and tests/test_kdf_mhf.py.
``KdfParams`` is the serialisable parameter record stored in archive headers.

Settings / parameters
---------------------
MIX_ROUNDS              8 (scrypt uses Salsa20/8 by the same reasoning;
                        docs/CRYPTANALYSIS.md measured full diffusion by round 3)
DEFAULT_MEMORY_BLOCKS   8192 (1 MiB of 128-byte blocks)
DEFAULT_PASSES          1
MIN_MEMORY_BLOCKS       64       (test-sized floor; real use should not go low)
MAX_MEMORY_BLOCKS       2**20    (128 MiB; hard ceiling for parsed headers)
MIN_PASSES / MAX_PASSES 1 / 16
SALT_BYTES              32 (minimum 16 accepted)

Edge cases
----------
* ``memory_blocks`` must be a power of two so the index reduction is unbiased.
* Text passwords are Unicode NFC-normalised before UTF-8 encoding, so the same
  visible password typed on different systems derives the same key. Bytes
  passwords are used as-is.
* Parameters read from untrusted headers are bounded by ``max_memory_blocks``
  and ``max_passes`` before any work is done (decompression-bomb-style DoS).

Known limitations
-----------------
* Data-dependent indexing (like scrypt) leaks access patterns to a co-resident
  cache-timing attacker.
* CPython stores each 64-bit word as a Python int, so the defender spends far
  more RAM and time than an attacker's native implementation would; the
  attacker-side memory cost is m x 128 bytes.
* The 8-round block function and the whole construction are unanalysed.

Examples
--------
>>> from brisart_security_kdf import KdfParams, derive_key
>>> params = KdfParams(memory_blocks=64, passes=1, salt=bytes(32))
>>> len(derive_key("correct horse", params))
32
"""
import unicodedata
from dataclasses import dataclass

from brisart_security_primitives import MASK64, permute_unchecked
from brisart_security_sponge import Sponge64

KDF_NAME = "BSR2-MHF-1"
KDF_ID = 1
MIX_ROUNDS = 8
BLOCK_WORDS = 16
BLOCK_BYTES = 128
DEFAULT_MEMORY_BLOCKS = 8192
DEFAULT_PASSES = 1
MIN_MEMORY_BLOCKS = 64
MAX_MEMORY_BLOCKS = 1 << 20
MIN_PASSES = 1
MAX_PASSES = 16
SALT_BYTES = 32
MIN_SALT_BYTES = 16
MAX_SALT_BYTES = 64
MAX_PASSWORD_BYTES = 4096
ENCODED_PARAMS_BYTES = 1 + 1 + 2 + 4 + 1 + MAX_SALT_BYTES


class BrisartKdfError(ValueError):
    """Raised for invalid KDF parameters or passwords."""


@dataclass(frozen=True)
class KdfParams:
    memory_blocks: int = DEFAULT_MEMORY_BLOCKS
    passes: int = DEFAULT_PASSES
    salt: bytes = b""
    rounds: int = MIX_ROUNDS

    def validate(self, *, max_memory_blocks: int = MAX_MEMORY_BLOCKS, max_passes: int = MAX_PASSES) -> None:
        m, t = self.memory_blocks, self.passes
        if type(m) is not int or type(t) is not int or type(self.rounds) is not int:
            raise BrisartKdfError("KDF parameters must be integers")
        if self.rounds != MIX_ROUNDS:
            raise BrisartKdfError("unsupported KDF round count")
        if m < MIN_MEMORY_BLOCKS or m & (m - 1):
            raise BrisartKdfError("memory_blocks must be a power of two of at least 64")
        if m > min(max_memory_blocks, MAX_MEMORY_BLOCKS):
            raise BrisartKdfError("memory_blocks exceeds the permitted maximum")
        if t < MIN_PASSES or t > min(max_passes, MAX_PASSES):
            raise BrisartKdfError("passes is outside the permitted range")
        if not isinstance(self.salt, bytes) or not MIN_SALT_BYTES <= len(self.salt) <= MAX_SALT_BYTES:
            raise BrisartKdfError("salt must be 16 to 64 bytes")

    def encode(self) -> bytes:
        """Fixed 73-byte encoding: id, rounds, passes, memory, salt len, salt (zero filled)."""
        self.validate()
        return (
            bytes((KDF_ID, self.rounds))
            + self.passes.to_bytes(2, "big")
            + self.memory_blocks.to_bytes(4, "big")
            + bytes((len(self.salt),))
            + self.salt.ljust(MAX_SALT_BYTES, b"\x00")
        )

    @classmethod
    def decode(cls, data: bytes, *, max_memory_blocks: int = MAX_MEMORY_BLOCKS, max_passes: int = MAX_PASSES) -> "KdfParams":
        if not isinstance(data, bytes) or len(data) != ENCODED_PARAMS_BYTES:
            raise BrisartKdfError("encoded KDF parameters have the wrong size")
        if data[0] != KDF_ID:
            raise BrisartKdfError("unknown KDF identifier")
        salt_length = data[8]
        if not MIN_SALT_BYTES <= salt_length <= MAX_SALT_BYTES or any(data[9 + salt_length:]):
            raise BrisartKdfError("encoded KDF salt is malformed")
        params = cls(
            memory_blocks=int.from_bytes(data[4:8], "big"),
            passes=int.from_bytes(data[2:4], "big"),
            salt=data[9:9 + salt_length],
            rounds=data[1],
        )
        params.validate(max_memory_blocks=max_memory_blocks, max_passes=max_passes)
        return params

    def describe(self) -> str:
        return f"{KDF_NAME} m={self.memory_blocks} ({self.memory_blocks * BLOCK_BYTES // 1024} KiB) t={self.passes} r={self.rounds}"


def _password_bytes(password) -> bytes:
    if isinstance(password, str):
        if not password:
            raise BrisartKdfError("password must not be empty")
        try:
            data = unicodedata.normalize("NFC", password).encode("utf-8")
        except UnicodeEncodeError as exc:
            raise BrisartKdfError("password is not valid UTF-8 text") from exc
    elif isinstance(password, bytes):
        if not password:
            raise BrisartKdfError("password must not be empty")
        data = password
    else:
        raise BrisartKdfError("password must be str or bytes")
    if len(data) > MAX_PASSWORD_BYTES:
        raise BrisartKdfError("password exceeds the size limit")
    return data


def _block_function(block: list[int], counter: int) -> list[int]:
    work = block[:]
    work[15] ^= counter & MASK64
    permute_unchecked(work, MIX_ROUNDS)
    return [a ^ b for a, b in zip(work, block)]


def derive_key(
    password,
    params: KdfParams,
    output_bytes: int = 32,
    *,
    max_memory_blocks: int = MAX_MEMORY_BLOCKS,
    max_passes: int = MAX_PASSES,
) -> bytes:
    """Derive ``output_bytes`` of key material from a password with BSR2-MHF-1."""
    if not isinstance(params, KdfParams):
        raise BrisartKdfError("params must be a KdfParams instance")
    params.validate(max_memory_blocks=max_memory_blocks, max_passes=max_passes)
    if type(output_bytes) is not int or not 16 <= output_bytes <= 1024:
        raise BrisartKdfError("output length must be between 16 and 1024 bytes")
    secret = _password_bytes(password)
    m, t = params.memory_blocks, params.passes
    header = (
        KDF_ID.to_bytes(1, "big")
        + params.rounds.to_bytes(1, "big")
        + t.to_bytes(4, "big")
        + m.to_bytes(4, "big")
        + output_bytes.to_bytes(4, "big")
    )
    seed = Sponge64(b"BSR2/v3/mhf/init").absorb_framed(secret, params.salt, header).squeeze(BLOCK_BYTES)
    x = [int.from_bytes(seed[i * 8:i * 8 + 8], "big") for i in range(BLOCK_WORDS)]
    table: list[list[int]] = [None] * m  # type: ignore[list-item]
    for index in range(m):
        table[index] = x
        x = _block_function(x, index)
    mask = m - 1
    for step in range(m * t):
        j = x[0] & mask
        mixed = [a ^ b for a, b in zip(x, table[j])]
        x = _block_function(mixed, m + step)
        table[j] = x
    final = b"".join(word.to_bytes(8, "big") for word in x)
    table.clear()
    return Sponge64(b"BSR2/v3/mhf/final").absorb_framed(final, secret, params.salt).squeeze(output_bytes)


def new_params(memory_blocks: int = DEFAULT_MEMORY_BLOCKS, passes: int = DEFAULT_PASSES, salt: bytes | None = None) -> KdfParams:
    """Create parameters with a fresh 32-byte operating-system salt."""
    if salt is None:
        from brisart_security_entropy import system_entropy

        salt = system_entropy(SALT_BYTES)
    params = KdfParams(memory_blocks=memory_blocks, passes=passes, salt=salt)
    params.validate()
    return params
