"""
File: v2/brisart_inflate.py

Purpose
-------
BrisartInflate -- a from-spec, pure-Python DEFLATE decompressor
(RFC 1951) with a zlib-stream wrapper (RFC 1950), replacing
zlib.decompress() in Brisart Research Archive tooling (for example PDF
stream decoding and PNG IDAT decoding).

Public interface:
- brisart_zlib_decompress(data, verify_checksum=True,
  max_output=DEFAULT_MAX_OUTPUT, allow_trailing=False) -- Decode a full
  zlib stream.
- brisart_inflate(data, max_output=DEFAULT_MAX_OUTPUT,
  allow_trailing=False) -- Decode a raw DEFLATE stream.
- brisart_inflate_prefix(data, start=0, max_output=DEFAULT_MAX_OUTPUT)
  -- Decode one DEFLATE stream that begins at `start` and return
  (output, end_offset), leaving anything after it untouched.
- brisart_adler32(data, seed=1) -- Adler-32 checksum.
- BrisartBitReader -- The LSB-first bit reader the decoder is built on.
- BrisartInflateError -- A ValueError subclass raised for every rejected
  stream; BrisartInflateUnsupported additionally derives from
  NotImplementedError and is raised for a preset dictionary (FDICT).
- DEFAULT_MAX_OUTPUT -- Default decompressed-size cap, 32 MiB.

Design notes:

Decompressing untrusted data is a classic resource-exhaustion and
parser-differential surface, so this decoder differs deliberately from a
minimal implementation:

1. Output is capped. A 3 KB stream can legitimately expand to gigabytes
   (a "decompression bomb"); every write is checked against max_output
   before it happens, and exceeding it raises. Pass max_output=None to
   remove the cap.
2. Structure is validated exactly as RFC 1951 and zlib require:
   over-subscribed Huffman codes, incomplete codes (other than the one
   permitted single-code case), a stored block whose NLEN is not the
   complement of LEN, a missing end-of-block code, HLIT above 286 or
   HDIST above 30, length symbols 286/287, distance symbols 30/31,
   repeat-code overruns, and back-references that reach before the start
   of the output are all rejected rather than tolerated.
3. Trailing bytes after the stream end are rejected by default (zlib
   silently ignores them), because accepting hidden trailing data is a
   way to smuggle content past a validator that stops at the stream end.
4. Decoding uses a flat lookup table per Huffman code (one list index
   per symbol) and a multi-byte bit buffer instead of one Python call per
   bit, and copies back-references with slices instead of byte-by-byte.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other brisart_native
modules. Behaviour is cross-checked against zlib, including its accept
and reject decisions on randomly corrupted streams, by
brisart_native/tests/test_inflate.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- DEFAULT_MAX_OUTPUT -- 33554432 bytes (32 MiB). The cap applies to
  every public decompression function unless max_output is given.
- max_output -- Integer byte limit, or None for no limit. Must not be
  negative.
- verify_checksum -- zlib wrapper only. True (default) requires the
  Adler-32 to match; False still requires the four checksum bytes to be
  present but does not compare them.
- allow_trailing -- False (default) rejects bytes after the stream end.
  True accepts and ignores them (zlib.decompress behaviour).
- The length/distance tables and the code-length order are fixed by
  RFC 1951 sections 3.2.5-3.2.7 and are not tunable.

Edge cases
----------
- Overlapping back-references (distance smaller than length) repeat the
  last `distance` bytes, exactly as byte-by-byte copying would.
- A distance code with a single code of length 1 is accepted, and an
  all-zero distance table is accepted for blocks that use no matches.
  Any other incomplete code is rejected, matching zlib.
- A stream whose data ends inside a symbol, the stored-block header, the
  zlib checksum or before the final block raises, so every strict prefix
  of a valid stream is an error.
- A zlib header is validated in full: method 8, window size field at
  most 7, header check bits, and FDICT.

Known limitations
-----------------
- Whole-buffer interface; no streaming or incremental output.
- No gzip, raw-with-dictionary or preset-dictionary support.
- Measured on CPython 3.12: about 2.4 MB/s of output for low-ratio
  text, 7-8 MB/s for repetitive text and 18 MB/s for incompressible
  data. zlib measured 360-1,800 MB/s on the same data, roughly 100-150
  times faster. Time is linear in input and output size, but a
  maximum-size (32 MiB) stream still takes seconds.
- The cap bounds memory and work per call; it does not rate-limit a
  caller that decompresses many streams.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_inflate import (
        brisart_zlib_decompress, BrisartInflateError)
    # zlib.compress(b"hello hello hello hello")
    packed = bytes.fromhex("789ccb48cdc9c957c8402701680308b1")
    assert brisart_zlib_decompress(packed) == b"hello hello hello hello"
    try:
        brisart_zlib_decompress(packed, max_output=5)   # bomb guard
    except BrisartInflateError:
        pass
"""

DEFAULT_MAX_OUTPUT = 32 * 1024 * 1024

_LENGTH_BASE = (
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
    35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258,
)
_LENGTH_EXTRA = (
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
    3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
)
_DISTANCE_BASE = (
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
    257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
    8193, 12289, 16385, 24577,
)
_DISTANCE_EXTRA = (
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
    7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
)
_CODE_LENGTH_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)

_ADLER_MODULO = 65521


class BrisartInflateError(ValueError):
    """Raised for any malformed, truncated, unsupported or oversized stream."""


class BrisartInflateUnsupported(BrisartInflateError, NotImplementedError):
    """Raised for a valid-looking stream that needs an unsupported feature (FDICT)."""


def _bytes_like(data):
    if isinstance(data, bytes):
        return data
    if isinstance(data, (bytearray, memoryview)):
        return bytes(data)
    raise TypeError("a bytes-like object is required, not %s" % type(data).__name__)


def _check_limit(max_output):
    if max_output is None:
        return float("inf")
    if isinstance(max_output, bool) or not isinstance(max_output, int) or max_output < 0:
        raise ValueError("max_output must be a non-negative integer or None")
    return max_output


def _build_table(lengths, kind):
    """Build a flat decode table from per-symbol code lengths.

    Returns (table, bits) where table[next `bits` stream bits] is
    (symbol << 4) | code_length, or 0 for a bit pattern no code uses; or
    (None, 0) for a code with no symbols. `kind` is "codes" for the
    code-length alphabet (must be complete) or "lens" for literal/length and
    distance alphabets (a lone length-1 code may be incomplete).
    """
    counts = [0] * 16
    for length in lengths:
        counts[length] += 1
    counts[0] = 0
    used = sum(counts)
    if used == 0:
        return None, 0
    left = 1
    for length in range(1, 16):
        left = (left << 1) - counts[length]
        if left < 0:
            raise BrisartInflateError("over-subscribed Huffman code")
    if left > 0 and (kind == "codes" or not (used == 1 and counts[1] == 1)):
        raise BrisartInflateError("incomplete Huffman code")
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + counts[bits - 1]) << 1
        next_code[bits] = code
    max_bits = 15
    while counts[max_bits] == 0:
        max_bits -= 1
    size = 1 << max_bits
    table = [0] * size
    for symbol, length in enumerate(lengths):
        if length:
            value = next_code[length]
            next_code[length] += 1
            reversed_code = int(bin(value)[2:].zfill(length)[::-1], 2)
            table[reversed_code::1 << length] = [(symbol << 4) | length] * (size >> length)
    return table, max_bits


_FIXED_LITERAL = _build_table([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8, "lens")
_FIXED_DISTANCE = _build_table([5] * 32, "lens")


class BrisartBitReader:
    """LSB-first bit reader over a bytes object (RFC 1951 section 3.1.1).

    Ordinary fields are read least-significant bit first; Huffman codes are
    resolved through a flat table indexed by the next stream bits, which
    already accounts for codes being packed most-significant bit first.
    """

    def __init__(self, data, position=0):
        self._data = _bytes_like(data)
        self.position = position       # index of the next byte not yet loaded into the buffer
        self.bit_buffer = 0
        self.bit_count = 0

    def _need(self, count):
        data = self._data
        while self.bit_count < count:
            if self.position >= len(data):
                raise BrisartInflateError("unexpected end of DEFLATE stream")
            self.bit_buffer |= data[self.position] << self.bit_count
            self.position += 1
            self.bit_count += 8

    def read_bits(self, count):
        """Read an ordinary multi-bit field, least-significant bit first."""
        self._need(count)
        value = self.bit_buffer & ((1 << count) - 1)
        self.bit_buffer >>= count
        self.bit_count -= count
        return value

    def read_bit(self):
        return self.read_bits(1)

    def align_to_byte(self):
        """Discard the rest of the current byte and give back unused whole bytes."""
        self.bit_buffer >>= self.bit_count % 8
        self.bit_count -= self.bit_count % 8
        self.position -= self.bit_count // 8
        self.bit_buffer = 0
        self.bit_count = 0

    def read_raw_bytes(self, count):
        """Read whole bytes; only valid immediately after align_to_byte()."""
        if self.position + count > len(self._data):
            raise BrisartInflateError("unexpected end of DEFLATE stream")
        chunk = self._data[self.position:self.position + count]
        self.position += count
        return chunk

    def read_huffman_symbol(self, table):
        """Decode one symbol using a table built by _build_table."""
        flat, bits = table
        if flat is None:
            raise BrisartInflateError("invalid Huffman code: the code has no symbols")
        data = self._data
        while self.bit_count < bits and self.position < len(data):
            self.bit_buffer |= data[self.position] << self.bit_count
            self.position += 1
            self.bit_count += 8
        entry = flat[self.bit_buffer & ((1 << bits) - 1)]
        if not entry:
            raise BrisartInflateError("invalid Huffman code")
        used = entry & 15
        if used > self.bit_count:
            raise BrisartInflateError("unexpected end of DEFLATE stream")
        self.bit_buffer >>= used
        self.bit_count -= used
        return entry >> 4


def _read_dynamic_tables(reader):
    literal_count = reader.read_bits(5) + 257
    distance_count = reader.read_bits(5) + 1
    code_length_count = reader.read_bits(4) + 4
    if literal_count > 286 or distance_count > 30:
        raise BrisartInflateError("too many length or distance symbols")
    code_length_lengths = [0] * 19
    for index in range(code_length_count):
        code_length_lengths[_CODE_LENGTH_ORDER[index]] = reader.read_bits(3)
    code_length_table = _build_table(code_length_lengths, "codes")
    total = literal_count + distance_count
    lengths = []
    while len(lengths) < total:
        symbol = reader.read_huffman_symbol(code_length_table)
        if symbol < 16:
            lengths.append(symbol)
            continue
        if symbol == 16:
            if not lengths:
                raise BrisartInflateError("repeat code with no previous length")
            previous = lengths[-1]
            repeat = 3 + reader.read_bits(2)
        elif symbol == 17:
            previous = 0
            repeat = 3 + reader.read_bits(3)
        else:
            previous = 0
            repeat = 11 + reader.read_bits(7)
        if len(lengths) + repeat > total:
            raise BrisartInflateError("code length repeat overruns the table")
        lengths.extend([previous] * repeat)
    if lengths[256] == 0:
        raise BrisartInflateError("missing end-of-block code")
    return _build_table(lengths[:literal_count], "lens"), _build_table(lengths[literal_count:], "lens")


def _decode_block(reader, out, literal, distance, limit):
    """Decode Huffman-coded symbols into `out` until the end-of-block symbol."""
    literal_table, literal_bits = literal
    distance_table, distance_bits = distance
    if literal_table is None:
        raise BrisartInflateError("invalid Huffman code: the code has no symbols")
    literal_mask = (1 << literal_bits) - 1
    distance_mask = (1 << distance_bits) - 1
    data = reader._data
    total = len(data)
    buf = reader.bit_buffer
    count = reader.bit_count
    position = reader.position
    length_base, length_extra = _LENGTH_BASE, _LENGTH_EXTRA
    distance_base, distance_extra = _DISTANCE_BASE, _DISTANCE_EXTRA
    while True:
        if count < 48 and position < total:
            chunk = data[position:position + 8]
            buf |= int.from_bytes(chunk, "little") << count
            count += 8 * len(chunk)
            position += len(chunk)
        entry = literal_table[buf & literal_mask]
        if not entry:
            raise BrisartInflateError("invalid literal/length code")
        used = entry & 15
        buf >>= used
        count -= used
        if count < 0:
            raise BrisartInflateError("unexpected end of DEFLATE stream")
        symbol = entry >> 4
        if symbol < 256:
            out.append(symbol)
            if len(out) > limit:
                raise BrisartInflateError("decompressed size exceeds max_output")
            continue
        if symbol == 256:
            break
        symbol -= 257
        if symbol >= 29:
            raise BrisartInflateError("invalid length symbol")
        extra = length_extra[symbol]
        length = length_base[symbol]
        if extra:
            length += buf & ((1 << extra) - 1)
            buf >>= extra
            count -= extra
            if count < 0:
                raise BrisartInflateError("unexpected end of DEFLATE stream")
        if distance_table is None:
            raise BrisartInflateError("invalid distance code: the code has no symbols")
        entry = distance_table[buf & distance_mask]
        if not entry:
            raise BrisartInflateError("invalid distance code")
        used = entry & 15
        buf >>= used
        count -= used
        if count < 0:
            raise BrisartInflateError("unexpected end of DEFLATE stream")
        symbol = entry >> 4
        if symbol >= 30:
            raise BrisartInflateError("invalid distance symbol")
        extra = distance_extra[symbol]
        back = distance_base[symbol]
        if extra:
            back += buf & ((1 << extra) - 1)
            buf >>= extra
            count -= extra
            if count < 0:
                raise BrisartInflateError("unexpected end of DEFLATE stream")
        size = len(out)
        if back > size:
            raise BrisartInflateError("back-reference distance exceeds the output so far")
        if size + length > limit:
            raise BrisartInflateError("decompressed size exceeds max_output")
        start = size - back
        if back >= length:
            out += out[start:start + length]
        else:
            out += (out[start:] * (length // back + 1))[:length]
    reader.bit_buffer = buf
    reader.bit_count = count
    reader.position = position


def _inflate(data, start, limit):
    reader = BrisartBitReader(data, start)
    out = bytearray()
    while True:
        is_final = reader.read_bits(1)
        block_type = reader.read_bits(2)
        if block_type == 0:
            reader.align_to_byte()
            header = reader.read_raw_bytes(4)
            length = header[0] | (header[1] << 8)
            if length ^ (header[2] | (header[3] << 8)) != 0xFFFF:
                raise BrisartInflateError("stored block length does not match its complement")
            if len(out) + length > limit:
                raise BrisartInflateError("decompressed size exceeds max_output")
            out += reader.read_raw_bytes(length)
        elif block_type == 1:
            _decode_block(reader, out, _FIXED_LITERAL, _FIXED_DISTANCE, limit)
        elif block_type == 2:
            literal, distance = _read_dynamic_tables(reader)
            _decode_block(reader, out, literal, distance, limit)
        else:
            raise BrisartInflateError("invalid DEFLATE block type 3 (reserved)")
        if is_final:
            break
    reader.align_to_byte()
    return bytes(out), reader.position


def brisart_inflate_prefix(data, start=0, max_output=DEFAULT_MAX_OUTPUT):
    """Decode one raw DEFLATE stream starting at `start`; return (output, end_offset)."""
    raw = _bytes_like(data)
    if isinstance(start, bool) or not isinstance(start, int) or start < 0 or start > len(raw):
        raise ValueError("start is outside the data")
    return _inflate(raw, start, _check_limit(max_output))


def brisart_inflate(data, max_output=DEFAULT_MAX_OUTPUT, allow_trailing=False):
    """Decompress a raw DEFLATE stream (RFC 1951; no zlib or gzip framing)."""
    raw = _bytes_like(data)
    output, end = _inflate(raw, 0, _check_limit(max_output))
    if end != len(raw) and not allow_trailing:
        raise BrisartInflateError("trailing data after the DEFLATE stream")
    return output


def brisart_adler32(data, seed=1):
    """Adler-32 checksum (RFC 1950 section 8.2)."""
    raw = _bytes_like(data)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed must be an unsigned 32-bit integer")
    a = seed & 0xFFFF
    b = (seed >> 16) & 0xFFFF
    for offset in range(0, len(raw), 5552):
        for byte in raw[offset:offset + 5552]:
            a += byte
            b += a
        a %= _ADLER_MODULO
        b %= _ADLER_MODULO
    # Reduce once more outside the loop so empty input with a large seed is
    # normalised exactly as zlib does it.
    return ((b % _ADLER_MODULO) << 16) | (a % _ADLER_MODULO)


def brisart_zlib_decompress(data, verify_checksum=True, max_output=DEFAULT_MAX_OUTPUT,
                            allow_trailing=False):
    """Decompress a full zlib stream (RFC 1950: header + DEFLATE + Adler-32)."""
    raw = _bytes_like(data)
    limit = _check_limit(max_output)
    if len(raw) < 2:
        raise BrisartInflateError("input too short to be a zlib stream")
    cmf, flg = raw[0], raw[1]
    if cmf & 0x0F != 8:
        raise BrisartInflateError("unsupported zlib compression method %d" % (cmf & 0x0F))
    if cmf >> 4 > 7:
        raise BrisartInflateError("invalid zlib window size")
    if (cmf * 256 + flg) % 31:
        raise BrisartInflateError("invalid zlib header check")
    if flg & 0x20:
        raise BrisartInflateUnsupported("zlib stream needs a preset dictionary (FDICT), which is not supported")
    output, end = _inflate(raw, 2, limit)
    if end + 4 > len(raw):
        raise BrisartInflateError("unexpected end of zlib stream: missing Adler-32 checksum")
    if end + 4 != len(raw) and not allow_trailing:
        raise BrisartInflateError("trailing data after the zlib stream")
    if verify_checksum:
        expected = int.from_bytes(raw[end:end + 4], "big")
        actual = brisart_adler32(output)
        if actual != expected:
            raise BrisartInflateError("Adler-32 mismatch: stream says %#010x, data is %#010x"
                                      % (expected, actual))
    return output


__all__ = [
    "BrisartBitReader",
    "BrisartInflateError",
    "BrisartInflateUnsupported",
    "DEFAULT_MAX_OUTPUT",
    "brisart_adler32",
    "brisart_inflate",
    "brisart_inflate_prefix",
    "brisart_zlib_decompress",
]
