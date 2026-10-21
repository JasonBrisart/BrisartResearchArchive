"""
File: brisart_native/brisart_hash.py

Purpose
-------
BrisartHash256 -- a from-spec, pure-Python SHA-256 (FIPS 180-4) with a
hashlib-compatible streaming interface, replacing hashlib.sha256() in
Brisart Research Archive tooling.

Public interface:
- BrisartHash256(data=b"") -- Streaming hash object with update(),
  digest(), hexdigest() and copy().
- brisart_sha256(data=b"") -- Convenience constructor.
- brisart_stable_hash(value) -- Hex digest of a str, injective over all
  Python strings (lone surrogates included).

Design notes:

SHA-256 is a published, fully specified algorithm; this file is a
re-implementation of it, not a new cryptographic design. Correctness is
established by the NIST test vectors, the one-million-'a' vector and
byte-for-byte comparison with hashlib across every padding boundary and
random chunking (see brisart_native/tests/test_hash.py). It is a
reference-quality implementation, not a hardened one: see Known
limitations before using it for secrets.

Input is processed in place with offsets rather than by repeatedly
trimming a working buffer, and hashing time is linear in input size. The
round function is written with inlined rotations (the doubled-word
trick: a 32-bit word multiplied by 0x100000001 holds two copies, so a
right shift leaves the rotated word in the low 32 bits), eight rounds
per loop pass generated mechanically so the working variables rotate by
renaming, and one 32-bit mask per stored word.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other brisart_native
modules. Output is cross-checked against hashlib by
brisart_native/tests/test_hash.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- _INITIAL_HASH -- The eight 32-bit initial words fixed by FIPS 180-4
  (square roots of the first eight primes). Not tunable.
- _ROUND_CONSTANTS -- The 64 round constants fixed by FIPS 180-4 (cube
  roots of the first 64 primes). Not tunable.
- BrisartHash256.digest_size == 32, block_size == 64 and name ==
  "brisart_sha256", matching the attributes hashlib objects expose.

Edge cases
----------
- update() accepts bytes, bytearray and memoryview. A str raises
  TypeError exactly as hashlib does, because a str has no single byte
  encoding.
- The empty message is valid and hashes to e3b0c442...b855.
- digest() and hexdigest() do not change the object: more data can be
  added afterwards, and copy() returns an independent object.
- The running length is kept modulo 2**64 bits as FIPS 180-4 requires.
- brisart_stable_hash encodes with UTF-8 and "surrogatepass", so two
  different strings never share a digest. The earlier "replace" handler
  turned every lone surrogate into "?", making "\\ud800" and "?"
  collide.

Known limitations
-----------------
- Not constant-time and not side-channel resistant. Do not use it to
  hash secrets where a local timing or cache observer is in your threat
  model.
- About 300 KB/s on CPython 3.12 (measured). hashlib measured about
  1,400 MB/s on the same machine, roughly 4,000 times faster. Prefer
  hashlib for large files unless zero external dependencies is the
  requirement. A 100 MB file would take roughly six minutes.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.
- No HMAC, SHA-512 or other algorithms are provided.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_hash import brisart_sha256, brisart_stable_hash
    assert brisart_sha256(b"abc").hexdigest() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    h = brisart_sha256()
    h.update(b"a")
    h.update(b"bc")
    assert h.hexdigest() == brisart_sha256(b"abc").hexdigest()
    assert brisart_stable_hash("\\ud800") != brisart_stable_hash("?")
"""

_INITIAL_HASH = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)

_ROUND_CONSTANTS = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)

_MASK32 = 0xFFFFFFFF
_MASK64 = 0xFFFFFFFFFFFFFFFF
_DOUBLE = 0x100000001  # x * _DOUBLE == x placed twice, for 32-bit rotations


def _compress(state, data, start, stop):
    """Process every 64-byte block of data[start:stop] (a multiple of 64 bytes).

    Rotations use the doubled-word trick: for a 32-bit x, (x * 0x100000001)
    holds x twice, so a right shift of it leaves the rotated value in the low
    32 bits. Bits above 32 are garbage and are cleared by the single mask when
    a result is stored back into a state word. The eight rounds of each loop
    pass are written out so the working variables rotate by renaming rather
    than by assignment; the body is generated mechanically, not hand-edited.
    """
    mask = _MASK32
    constants = _ROUND_CONSTANTS
    h0, h1, h2, h3, h4, h5, h6, h7 = state
    for offset in range(start, stop, 64):
        block = int.from_bytes(data[offset:offset + 64], "big")
        w = [(block >> (480 - 32 * i)) & mask for i in range(16)]
        for i in range(16, 64):
            x = w[i - 15]
            y = w[i - 2]
            xx = x * _DOUBLE
            yy = y * _DOUBLE
            w.append((w[i - 16] + ((xx >> 7) ^ (xx >> 18) ^ (x >> 3))
                      + w[i - 7] + ((yy >> 17) ^ (yy >> 19) ^ (y >> 10))) & mask)
        a, b, c, d, e, f, g, h = h0, h1, h2, h3, h4, h5, h6, h7
        schedule = [constants[i] + w[i] for i in range(64)]
        iterator = iter(schedule)
        for k0, k1, k2, k3, k4, k5, k6, k7 in zip(iterator, iterator, iterator, iterator,
                                                  iterator, iterator, iterator, iterator):
            x = e * _DOUBLE
            t = h + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (g ^ (e & (f ^ g))) + k0
            d = (d + t) & mask
            x = a * _DOUBLE
            h = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((a & b) | (c & (a | b)))) & mask
            x = d * _DOUBLE
            t = g + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (f ^ (d & (e ^ f))) + k1
            c = (c + t) & mask
            x = h * _DOUBLE
            g = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((h & a) | (b & (h | a)))) & mask
            x = c * _DOUBLE
            t = f + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (e ^ (c & (d ^ e))) + k2
            b = (b + t) & mask
            x = g * _DOUBLE
            f = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((g & h) | (a & (g | h)))) & mask
            x = b * _DOUBLE
            t = e + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (d ^ (b & (c ^ d))) + k3
            a = (a + t) & mask
            x = f * _DOUBLE
            e = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((f & g) | (h & (f | g)))) & mask
            x = a * _DOUBLE
            t = d + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (c ^ (a & (b ^ c))) + k4
            h = (h + t) & mask
            x = e * _DOUBLE
            d = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((e & f) | (g & (e | f)))) & mask
            x = h * _DOUBLE
            t = c + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (b ^ (h & (a ^ b))) + k5
            g = (g + t) & mask
            x = d * _DOUBLE
            c = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((d & e) | (f & (d | e)))) & mask
            x = g * _DOUBLE
            t = b + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (a ^ (g & (h ^ a))) + k6
            f = (f + t) & mask
            x = c * _DOUBLE
            b = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((c & d) | (e & (c | d)))) & mask
            x = f * _DOUBLE
            t = a + ((x >> 6) ^ (x >> 11) ^ (x >> 25)) + (h ^ (f & (g ^ h))) + k7
            e = (e + t) & mask
            x = b * _DOUBLE
            a = (t + ((x >> 2) ^ (x >> 13) ^ (x >> 22)) + ((b & c) | (d & (b | c)))) & mask
        h0 = (h0 + a) & mask
        h1 = (h1 + b) & mask
        h2 = (h2 + c) & mask
        h3 = (h3 + d) & mask
        h4 = (h4 + e) & mask
        h5 = (h5 + f) & mask
        h6 = (h6 + g) & mask
        h7 = (h7 + h) & mask
    state[:] = (h0, h1, h2, h3, h4, h5, h6, h7)


def _as_bytes(data):
    if isinstance(data, (bytes, bytearray)):
        return data
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, str):
        raise TypeError("Strings must be encoded before hashing")
    raise TypeError("object supporting the buffer API required")


class BrisartHash256:
    """From-spec pure-Python SHA-256 with hashlib's streaming interface."""

    digest_size = 32
    block_size = 64
    name = "brisart_sha256"

    def __init__(self, data=b""):
        self._state = list(_INITIAL_HASH)
        self._buffer = bytearray()
        self._total_length = 0
        self.update(data)  # always validated: None, 0 and "" must raise TypeError like hashlib

    def update(self, data):
        raw = _as_bytes(data)
        self._total_length += len(raw)
        position = 0
        if self._buffer:
            take = min(64 - len(self._buffer), len(raw))
            self._buffer += raw[:take]
            position = take
            if len(self._buffer) == 64:
                _compress(self._state, bytes(self._buffer), 0, 64)
                self._buffer = bytearray()
        whole = (len(raw) - position) // 64 * 64
        if whole:
            _compress(self._state, raw, position, position + whole)
            position += whole
        if position < len(raw):
            self._buffer += raw[position:]
        return self

    def _final_state(self):
        state = list(self._state)
        tail = bytearray(self._buffer)
        tail.append(0x80)
        while len(tail) % 64 != 56:
            tail.append(0)
        tail += ((self._total_length * 8) & _MASK64).to_bytes(8, "big")
        _compress(state, bytes(tail), 0, len(tail))
        return state

    def digest(self):
        return b"".join(word.to_bytes(4, "big") for word in self._final_state())

    def hexdigest(self):
        return self.digest().hex()

    def copy(self):
        clone = BrisartHash256()
        clone._state = list(self._state)
        clone._buffer = bytearray(self._buffer)
        clone._total_length = self._total_length
        return clone


def brisart_sha256(data=b""):
    """Convenience constructor mirroring hashlib.sha256(data)."""
    return BrisartHash256(data)


def brisart_stable_hash(value):
    """Hex SHA-256 of a str; distinct strings always give distinct input bytes."""
    if not isinstance(value, str):
        raise TypeError("brisart_stable_hash() requires str, not %s" % type(value).__name__)
    return BrisartHash256(value.encode("utf-8", "surrogatepass")).hexdigest()


__all__ = ["BrisartHash256", "brisart_sha256", "brisart_stable_hash"]
