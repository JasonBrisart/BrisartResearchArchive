"""
File: v1/brisart_deflate.py

Purpose
-------
BrisartDeflate -- a from-spec, pure-Python DEFLATE compressor (RFC 1951)
with zlib (RFC 1950) and gzip (RFC 1952) framing, replacing
zlib.compress() and gzip.compress() in Brisart Research Archive tooling
(for example writing PNG IDAT data, compressed archives and snapshot
files).

Public interface:
- brisart_deflate(data, level=DEFAULT_LEVEL) -- Compress to a raw DEFLATE
  stream.
- brisart_zlib_compress(data, level=DEFAULT_LEVEL) -- Compress to a zlib
  stream (2-byte header, DEFLATE data, Adler-32).
- brisart_gzip_compress(data, level=DEFAULT_LEVEL, mtime=0) -- Compress to
  a single-member gzip stream (10-byte header, DEFLATE data, CRC-32,
  ISIZE).
- DEFAULT_LEVEL -- 6, as in zlib.

Design notes:

Every stream this module writes is a valid stream for any conforming
decoder; it does not have to match zlib's output byte for byte, and it
does not. Level 0 writes stored blocks only. Levels 1-9 find
back-references with a hash chain over 3-byte prefixes in a 32 KiB
window (the same structure zlib uses), with lazy matching from level 4
upward, and longer chain searches as the level rises.

Each block is written in whichever of the three RFC 1951 block types is
smallest for that block: stored, fixed Huffman or dynamic Huffman.
Dynamic Huffman code lengths are computed with the package-merge
algorithm, which gives optimal codes under the format's limits (15 bits
for literal/length and distance codes, 7 bits for the code-length code),
and the code-length sequence is run-length encoded with symbols 16, 17
and 18. A block never needs more than five more bytes than its input
plus the stream overhead, because a stored block is always a candidate.

Output is deterministic: the same input and level always produce the
same bytes, on any platform. The gzip header records modification time 0
unless mtime is given, no file name, and operating system 255
("unknown"), so archives do not leak the host system or the time of
compression.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It carries its own Adler-32 and CRC-32 rather
than importing them from brisart_inflate.py. Every stream it writes is
checked by v1/tests/test_deflate.py against zlib.decompress and
gzip.decompress (tests may import the standard library; this module may
not) and against v3/brisart_inflate.py.

Settings / parameters
---------------------
- level -- 0 (stored only) to 9 (slowest, smallest). The table _LEVELS
  holds zlib's per-level configuration: the "good" length above which a
  lazy search uses a quarter of the chain, the "lazy" length at or above
  which a match is taken without looking one byte ahead, the "nice"
  length at which the chain search stops, the maximum chain length, and
  whether lazy matching is used at all.
- mtime -- gzip only. Unsigned 32-bit modification time written to the
  header; 0 (the default) means "not available" in RFC 1952.
- _BLOCK_TOKENS -- 16384 literals or matches per Huffman block; a new
  block lets the code adapt to changing data.
- _WINDOW -- 32768, the largest distance DEFLATE allows.

Edge cases
----------
- Empty input produces a valid stream that decodes to b"": one final,
  empty stored block.
- Input longer than 65,535 bytes at level 0 is split into several stored
  blocks.
- Overlapping matches (distance smaller than length) are produced for
  runs, as in zlib; decoders handle them by definition.
- A block whose dynamic code would use only one literal/length or
  distance symbol gets a second symbol so that every code written is
  complete, which every decoder accepts.
- bytes, bytearray and memoryview are accepted; str and other types raise
  TypeError. level must be an int from 0 to 9 (bool is rejected).

Known limitations
-----------------
- Pure Python and single-threaded. Measured on CPython 3.12, input
  throughput is about 0.4-2 MB/s at level 1, 0.07-1.1 MB/s at level 6
  and 0.02-0.95 MB/s at level 9; the slowest case is text built from
  many short, similar words, where the hash chains are long. zlib is
  hundreds to thousands of times faster. Use level 1-3 for anything
  large; the module suits snapshots, PNG frames and moderate archives,
  not bulk data.
- Whole-buffer interface: no streaming, no flush modes, no preset
  dictionary.
- Compression ratio is close to zlib's at the same level but not
  identical; the tests require the output to be no more than 5% (plus 16
  bytes) larger than zlib's on their data sets, and on those sets it is
  usually within 1%.
- The window and hash tables use memory proportional to the window, but
  the output and the per-block token list are held in memory.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run with the v1 folder on sys.path (for example, from inside v1/).

::

    from brisart_deflate import brisart_zlib_compress, brisart_gzip_compress
    from brisart_inflate import brisart_zlib_decompress, brisart_gzip_decompress
    text = b"the quick brown fox " * 50
    packed = brisart_zlib_compress(text, level=9)
    assert len(packed) < len(text) // 10
    assert brisart_zlib_decompress(packed) == text
    assert brisart_gzip_decompress(brisart_gzip_compress(text)) == text
"""

DEFAULT_LEVEL = 6

_WINDOW = 32768
_MIN_MATCH = 3
_MAX_MATCH = 258
_BLOCK_TOKENS = 16384
_STORED_MAX = 65535
_TOO_FAR = 4096

# level: (good length, lazy limit, nice length, max chain, lazy matching) -- zlib's configuration table
_LEVELS = {
    1: (4, 4, 8, 4, False), 2: (4, 5, 16, 8, False), 3: (4, 6, 32, 32, False),
    4: (4, 4, 16, 16, True), 5: (8, 16, 32, 32, True), 6: (8, 16, 128, 128, True),
    7: (8, 32, 128, 256, True), 8: (32, 128, 258, 1024, True), 9: (32, 258, 258, 4096, True),
}

_LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)
_LENGTH_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
_DISTANCE_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
                  257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
                  8193, 12289, 16385, 24577)
_DISTANCE_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
                   7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)
_CODE_LENGTH_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


def _length_tables():
    symbol, extra_bits, extra_value = [0] * 259, [0] * 259, [0] * 259
    for code in range(28):                         # codes 257-284 cover lengths 3-257
        base = _LENGTH_BASE[code]
        for length in range(base, _LENGTH_BASE[code + 1]):
            symbol[length] = 257 + code
            extra_bits[length] = _LENGTH_EXTRA[code]
            extra_value[length] = length - base
    symbol[258], extra_bits[258], extra_value[258] = 285, 0, 0     # 258 has its own code
    return tuple(symbol), tuple(extra_bits), tuple(extra_value)


def _distance_tables():
    symbol, extra_bits, extra_value = [0] * 32769, [0] * 32769, [0] * 32769
    for code in range(30):
        base = _DISTANCE_BASE[code]
        top = _DISTANCE_BASE[code + 1] if code < 29 else 32769
        for distance in range(base, top):
            symbol[distance] = code
            extra_bits[distance] = _DISTANCE_EXTRA[code]
            extra_value[distance] = distance - base
    return tuple(symbol), tuple(extra_bits), tuple(extra_value)


_LEN_SYM, _LEN_XB, _LEN_XV = _length_tables()
_DIST_SYM, _DIST_XB, _DIST_XV = _distance_tables()


def _bytes_like(data):
    if isinstance(data, bytes):
        return data
    if isinstance(data, (bytearray, memoryview)):
        return bytes(data)
    raise TypeError("a bytes-like object is required, not %s" % type(data).__name__)


def _check_level(level):
    if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 9:
        raise ValueError("level must be an integer from 0 to 9")
    return level


# --------------------------------------------------------------------------- Huffman codes
def _limited_lengths(freqs, limit):
    """Optimal code lengths no longer than `limit` bits (package-merge)."""
    lengths = [0] * len(freqs)
    leaves = sorted((f, s) for s, f in enumerate(freqs) if f)
    n = len(leaves)
    if n == 0:
        return lengths
    if n == 1:
        lengths[leaves[0][1]] = 1
        return lengths
    weight, left, right = [], [], []          # node arrays; left == -1 marks a leaf (right = leaf index)
    leaf_nodes = []
    for index, (f, _) in enumerate(leaves):
        weight.append(f)
        left.append(-1)
        right.append(index)
        leaf_nodes.append(len(weight) - 1)
    current = list(leaf_nodes)
    for _ in range(limit - 1):
        packages = []
        for j in range(0, len(current) - 1, 2):
            a, b = current[j], current[j + 1]
            weight.append(weight[a] + weight[b])
            left.append(a)
            right.append(b)
            packages.append(len(weight) - 1)
        merged = []
        i = k = 0
        while i < n or k < len(packages):
            if k >= len(packages) or (i < n and weight[leaf_nodes[i]] <= weight[packages[k]]):
                merged.append(leaf_nodes[i])
                i += 1
            else:
                merged.append(packages[k])
                k += 1
        current = merged
    counts = [0] * n
    stack = current[:2 * n - 2]
    while stack:
        node = stack.pop()
        if left[node] == -1:
            counts[right[node]] += 1
        else:
            stack.append(left[node])
            stack.append(right[node])
    for index, (_, symbol) in enumerate(leaves):
        lengths[symbol] = counts[index]
    return lengths


def _canonical_reversed(lengths):
    """Bit-reversed canonical codes (ready for LSB-first output) for the given lengths."""
    counts = [0] * 16
    for length in lengths:
        counts[length] += 1
    counts[0] = 0
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + counts[bits - 1]) << 1
        next_code[bits] = code
    codes = [0] * len(lengths)
    for symbol, length in enumerate(lengths):
        if length:
            value = next_code[length]
            next_code[length] += 1
            reversed_value = 0
            for _ in range(length):
                reversed_value = (reversed_value << 1) | (value & 1)
                value >>= 1
            codes[symbol] = reversed_value
    return codes


_FIXED_LIT_LENGTHS = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
_FIXED_DIST_LENGTHS = [5] * 30
_FIXED_LIT_CODES = _canonical_reversed(_FIXED_LIT_LENGTHS)
_FIXED_DIST_CODES = _canonical_reversed(_FIXED_DIST_LENGTHS)


def _run_length_encode(lengths):
    """Code-length sequence as (symbol, extra_bits, extra_value) using RLE symbols 16, 17 and 18."""
    out = []
    i = 0
    n = len(lengths)
    while i < n:
        value = lengths[i]
        run = 1
        while i + run < n and lengths[i + run] == value:
            run += 1
        if value == 0:
            remaining = run
            while remaining >= 11:
                take = min(remaining, 138)
                out.append((18, 7, take - 11))
                remaining -= take
            if remaining >= 3:
                out.append((17, 3, remaining - 3))
                remaining = 0
            out.extend([(0, 0, 0)] * remaining)
        else:
            out.append((value, 0, 0))
            remaining = run - 1
            while remaining >= 3:
                take = min(remaining, 6)
                out.append((16, 2, take - 3))
                remaining -= take
            out.extend([(value, 0, 0)] * remaining)
        i += run
    return out


# --------------------------------------------------------------------------- bit output
class _BitWriter:
    __slots__ = ("out", "acc", "count")

    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.count = 0

    def put(self, value, bits):
        self.acc |= value << self.count
        self.count += bits
        if self.count >= 4096:
            self.flush_whole()

    def flush_whole(self):
        whole = self.count >> 3
        if whole:
            self.out += (self.acc & ((1 << (whole << 3)) - 1)).to_bytes(whole, "little")
            self.acc >>= whole << 3
            self.count -= whole << 3

    def align(self):
        self.count = (self.count + 7) & ~7
        self.flush_whole()

    def raw(self, data):
        self.align()
        self.out += data

    def finish(self):
        self.align()
        return bytes(self.out)


# --------------------------------------------------------------------------- LZ77 match finding
def _tokens(data, level):
    """Yield blocks of tokens: lists of literals (0-255) and matches (256 + ((length-3) << 15 | distance-1)),
    with the input span each block covers."""
    good, max_lazy, nice, max_chain, lazy = _LEVELS[level]
    n = len(data)
    head = {}
    prev = [-1] * _WINDOW
    mask = _WINDOW - 1
    tokens = []
    block_start = 0
    i = 0

    def longest(pos, chain, best_len):
        """Longest match at pos that is longer than best_len, as (length, distance), or (0, 0)."""
        if pos + _MIN_MATCH > n:
            return 0, 0
        limit = min(_MAX_MATCH, n - pos)
        if best_len >= limit:
            return 0, 0
        floor = best_len
        best_dist = 0
        cand = head.get((data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2], -1)
        last = pos
        while cand >= 0 and chain and pos - cand <= _WINDOW and cand < last:
            if data[cand + best_len] == data[pos + best_len] and \
                    data[cand:cand + best_len + 1] == data[pos:pos + best_len + 1]:
                # Equal for best_len + 1 bytes: gallop forward, then binary-search the exact length.
                low = best_len + 1
                step = 8
                high = limit
                while low < limit:
                    probe = min(low + step, limit)
                    if data[cand + low:cand + probe] == data[pos + low:pos + probe]:
                        low = probe
                        step <<= 1
                    else:
                        high = probe - 1
                        break
                while low < high:                         # largest L <= high with equal prefixes
                    middle = (low + high + 1) >> 1
                    if data[cand + low:cand + middle] == data[pos + low:pos + middle]:
                        low = middle
                    else:
                        high = middle - 1
                length = low
                if length > best_len:
                    best_len, best_dist = length, pos - cand
                    if length >= nice or length == limit:
                        break
            last = cand
            cand = prev[cand & mask]
            chain -= 1
        if best_len > floor and best_len >= _MIN_MATCH:
            return best_len, best_dist
        return 0, 0

    def insert(pos):
        if pos + _MIN_MATCH <= n:
            key = (data[pos] << 16) | (data[pos + 1] << 8) | data[pos + 2]
            prev[pos & mask] = head.get(key, -1)
            head[key] = pos

    pending = None                                 # lazy matching: (length, distance) found at i - 1
    while i < n:
        if pending is not None:
            p_len, p_dist = pending
            length, distance = longest(i, max_chain >> 2 if p_len >= good else max_chain, p_len)
            if length:
                tokens.append(data[i - 1])         # the previous match loses: emit its first byte as a literal
                pending = (length, distance)
                insert(i)
                i += 1
                if length >= max_lazy:             # long enough: take it now
                    p_len, p_dist = pending
                    tokens.append(256 + ((p_len - 3) << 15 | (p_dist - 1)))
                    end = i - 1 + p_len
                    for q in range(i, end):
                        insert(q)
                    i = end
                    pending = None
            else:
                tokens.append(256 + ((p_len - 3) << 15 | (p_dist - 1)))
                end = i - 1 + p_len
                for q in range(i, end):
                    insert(q)
                i = end
                pending = None
        else:
            length, distance = longest(i, max_chain, _MIN_MATCH - 1)
            if lazy and length == _MIN_MATCH and distance > _TOO_FAR:
                length = 0                         # zlib's TOO_FAR rule: a far 3-byte match costs more than literals
            if length and lazy and length < max_lazy:
                pending = (length, distance)
                insert(i)
                i += 1
            elif length:
                tokens.append(256 + ((length - 3) << 15 | (distance - 1)))
                end = i + length
                insert(i)
                if lazy or length <= max_lazy:         # zlib: lazy levels insert every position; fast levels
                                                       # skip the interior of matches longer than max_lazy
                    for q in range(i + 1, end):
                        insert(q)
                i = end
            else:
                tokens.append(data[i])
                insert(i)
                i += 1
        if len(tokens) >= _BLOCK_TOKENS and pending is None:
            yield tokens, block_start, i
            tokens = []
            block_start = i
    if pending is not None:
        p_len, p_dist = pending
        tokens.append(256 + ((p_len - 3) << 15 | (p_dist - 1)))
    yield tokens, block_start, n


# --------------------------------------------------------------------------- block writing
def _encode_tokens(writer, tokens, lit_codes, lit_lengths, dist_codes, dist_lengths):
    put = writer.put
    for t in tokens:
        if t < 256:
            put(lit_codes[t], lit_lengths[t])
            continue
        m = t - 256
        length = (m >> 15) + 3
        distance = (m & 32767) + 1
        ls = _LEN_SYM[length]
        ds = _DIST_SYM[distance]
        value = lit_codes[ls] | (_LEN_XV[length] << lit_lengths[ls])
        bits = lit_lengths[ls] + _LEN_XB[length]
        value |= (dist_codes[ds] | (_DIST_XV[distance] << dist_lengths[ds])) << bits
        put(value, bits + dist_lengths[ds] + _DIST_XB[distance])
    put(lit_codes[256], lit_lengths[256])


def _write_block(writer, tokens, raw, final):
    lit_freq = [0] * 286
    dist_freq = [0] * 30
    extra = 0
    for t in tokens:
        if t < 256:
            lit_freq[t] += 1
        else:
            m = t - 256
            length = (m >> 15) + 3
            distance = (m & 32767) + 1
            lit_freq[_LEN_SYM[length]] += 1
            dist_freq[_DIST_SYM[distance]] += 1
            extra += _LEN_XB[length] + _DIST_XB[distance]
    lit_freq[256] = 1
    # Keep every code complete: at least two symbols in each alphabet.
    if sum(1 for f in lit_freq if f) < 2:
        lit_freq[0 if lit_freq[0] == 0 else 1] = 1
    used_dist = sum(1 for f in dist_freq if f)
    if used_dist < 2:
        dist_freq[0] = dist_freq[0] or 1
        dist_freq[1] = dist_freq[1] or 1
    lit_lengths = _limited_lengths(lit_freq, 15)
    dist_lengths = _limited_lengths(dist_freq, 15)
    hlit = 286
    while hlit > 257 and lit_lengths[hlit - 1] == 0:
        hlit -= 1
    hdist = 30
    while hdist > 1 and dist_lengths[hdist - 1] == 0:
        hdist -= 1
    rle = _run_length_encode(lit_lengths[:hlit] + dist_lengths[:hdist])
    cl_freq = [0] * 19
    for symbol, _, _ in rle:
        cl_freq[symbol] += 1
    cl_lengths = _limited_lengths(cl_freq, 7)
    if sum(1 for x in cl_lengths if x) < 2:
        cl_freq[0 if cl_freq[0] == 0 else 1] += 1
        cl_lengths = _limited_lengths(cl_freq, 7)
    hclen = 19
    while hclen > 4 and cl_lengths[_CODE_LENGTH_ORDER[hclen - 1]] == 0:
        hclen -= 1

    true_lit = [0] * 286
    true_dist = [0] * 30
    for t in tokens:
        if t < 256:
            true_lit[t] += 1
        else:
            m = t - 256
            true_lit[_LEN_SYM[(m >> 15) + 3]] += 1
            true_dist[_DIST_SYM[(m & 32767) + 1]] += 1
    true_lit[256] = 1
    dynamic_bits = 3 + 14 + 3 * hclen + extra + sum(cl_lengths[s] + xb for s, xb, _ in rle) \
        + sum(f * l for f, l in zip(true_lit, lit_lengths)) + sum(f * l for f, l in zip(true_dist, dist_lengths))
    fixed_bits = 3 + extra + sum(f * l for f, l in zip(true_lit, _FIXED_LIT_LENGTHS)) \
        + sum(f * 5 for f in true_dist)
    stored_bits = 3 + 7 + (4 + len(raw)) * 8 if len(raw) <= _STORED_MAX else None

    if stored_bits is not None and stored_bits <= min(fixed_bits, dynamic_bits):
        writer.put(final, 1)
        writer.put(0, 2)
        writer.align()
        writer.raw(len(raw).to_bytes(2, "little") + (len(raw) ^ 0xFFFF).to_bytes(2, "little") + raw)
    elif fixed_bits <= dynamic_bits:
        writer.put(final, 1)
        writer.put(1, 2)
        _encode_tokens(writer, tokens, _FIXED_LIT_CODES, _FIXED_LIT_LENGTHS, _FIXED_DIST_CODES, _FIXED_DIST_LENGTHS)
    else:
        writer.put(final, 1)
        writer.put(2, 2)
        writer.put(hlit - 257, 5)
        writer.put(hdist - 1, 5)
        writer.put(hclen - 4, 4)
        for index in range(hclen):
            writer.put(cl_lengths[_CODE_LENGTH_ORDER[index]], 3)
        cl_codes = _canonical_reversed(cl_lengths)
        for symbol, extra_bits, extra_value in rle:
            writer.put(cl_codes[symbol], cl_lengths[symbol])
            if extra_bits:
                writer.put(extra_value, extra_bits)
        _encode_tokens(writer, tokens, _canonical_reversed(lit_lengths), lit_lengths,
                       _canonical_reversed(dist_lengths), dist_lengths)


def _deflate(data, level):
    writer = _BitWriter()
    if level == 0 or not data:
        if not data:
            writer.put(1, 1)
            writer.put(0, 2)
            writer.raw(b"\x00\x00\xff\xff")
            return writer.finish()
        for start in range(0, len(data), _STORED_MAX):
            chunk = data[start:start + _STORED_MAX]
            writer.put(1 if start + _STORED_MAX >= len(data) else 0, 1)
            writer.put(0, 2)
            writer.raw(len(chunk).to_bytes(2, "little") + (len(chunk) ^ 0xFFFF).to_bytes(2, "little") + chunk)
        return writer.finish()
    blocks = _tokens(data, level)
    previous = next(blocks)
    for current in blocks:
        tokens, start, end = previous
        _write_block(writer, tokens, data[start:end], 0)
        previous = current
    tokens, start, end = previous
    _write_block(writer, tokens, data[start:end], 1)
    return writer.finish()


# --------------------------------------------------------------------------- checksums and framing
def _adler32(data):
    a, b = 1, 0
    for offset in range(0, len(data), 5552):
        for byte in data[offset:offset + 5552]:
            a += byte
            b += a
        a %= 65521
        b %= 65521
    return (b << 16) | a


def _crc_table():
    table = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if c & 1 else c >> 1
        table.append(c)
    return tuple(table)


_CRC_TABLE = _crc_table()


def _crc32(data):
    crc = 0xFFFFFFFF
    table = _CRC_TABLE
    for byte in data:
        crc = table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFF


def brisart_deflate(data, level=DEFAULT_LEVEL):
    """Compress a bytes-like object to a raw DEFLATE stream (RFC 1951)."""
    return _deflate(_bytes_like(data), _check_level(level))


def brisart_zlib_compress(data, level=DEFAULT_LEVEL):
    """Compress a bytes-like object to a zlib stream (RFC 1950)."""
    raw = _bytes_like(data)
    level = _check_level(level)
    flevel = 0 if level < 2 else 1 if level < 6 else 2 if level == 6 else 3
    cmf = 0x78
    flg = flevel << 6
    flg |= 31 - ((cmf * 256 + flg) % 31)
    return bytes((cmf, flg)) + _deflate(raw, level) + _adler32(raw).to_bytes(4, "big")


def brisart_gzip_compress(data, level=DEFAULT_LEVEL, mtime=0):
    """Compress a bytes-like object to a single-member gzip stream (RFC 1952)."""
    raw = _bytes_like(data)
    level = _check_level(level)
    if isinstance(mtime, bool) or not isinstance(mtime, int) or not 0 <= mtime <= 0xFFFFFFFF:
        raise ValueError("mtime must be an unsigned 32-bit integer")
    xfl = 2 if level == 9 else 4 if level == 1 else 0
    header = b"\x1f\x8b\x08\x00" + mtime.to_bytes(4, "little") + bytes((xfl, 255))
    trailer = _crc32(raw).to_bytes(4, "little") + (len(raw) & 0xFFFFFFFF).to_bytes(4, "little")
    return header + _deflate(raw, level) + trailer


__all__ = [
    "DEFAULT_LEVEL",
    "brisart_deflate",
    "brisart_gzip_compress",
    "brisart_zlib_compress",
]
