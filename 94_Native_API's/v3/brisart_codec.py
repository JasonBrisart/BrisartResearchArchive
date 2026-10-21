"""
File: v3/brisart_codec.py

Purpose
-------
BrisartBase64 -- from-spec, pure-Python Base64, Base32, Base32hex and
Base16 encoders with strict decoders (RFC 4648), replacing
base64.b64encode / b64decode / urlsafe_b64decode / b32encode /
b32decode / b32hexencode / b32hexdecode / b16encode / b16decode in
Brisart Research Archive tooling.

Public interface:
- brisart_b64encode(data, urlsafe=False, padding=True) -- Encode a
  bytes-like object; returns ASCII bytes.
- brisart_b64decode(data, urlsafe=False, padding="optional",
  canonical=True, allow_whitespace=False, max_output=None) -- Strictly
  decode bytes or ASCII text; returns bytes.
- brisart_urlsafe_b64encode(data, padding=True) -- URL-safe encode.
- brisart_urlsafe_b64decode(data, **options) -- URL-safe decode.
- BrisartBase64Error -- A ValueError subclass raised for every rejected
  input, so one `except ValueError` covers every failure.
- brisart_b32encode(data, hex=False, padding=True) -- Base32 or (hex=True)
  Base32hex encode; returns ASCII bytes.
- brisart_b32decode(data, hex=False, padding="required", casefold=False,
  canonical=True, max_output=None) -- Strict Base32/Base32hex decode.
- brisart_b16encode(data, lowercase=False) -- Base16 (hex) encode.
- brisart_b16decode(data, casefold=False, max_output=None) -- Strict
  Base16 decode.
- BrisartBase32Error -- Raised for rejected Base32 and Base16 input; a
  subclass of BrisartBase64Error and therefore of ValueError.

Design notes:

The decoder is deliberately stricter than base64.b64decode, which by
default silently discards characters outside the alphabet and accepts
non-canonical encodings. Those leniencies let two parsers see different
bytes in the same text (parser differentials), so this module accepts
exactly one encoding for each byte string: only alphabet characters,
correct '=' padding in the correct place, zero trailing bits, and no
whitespace unless the caller opts in. Validation is done with C-speed
bytes.translate calls rather than per-character Python loops.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other v3
modules. Behaviour is cross-checked against the standard base64 module
by v3/tests/test_codec.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- urlsafe -- Selects the URL-safe alphabet ('-' and '_' instead of '+'
  and '/'). The alphabets are never mixed.
- padding -- Decode only. "optional" (default) accepts unpadded input
  such as URL-safe tokens; "required" demands '=' padding; "forbidden"
  rejects any '='. Encode only: True (default) emits '='.
- canonical -- Decode only. True (default) rejects non-zero trailing
  bits, so each byte string has exactly one accepted encoding.
- allow_whitespace -- Decode only. False (default) rejects every
  whitespace character; True ignores space, tab, CR and LF anywhere.
- max_output -- Decode only. Optional upper bound on decoded size in
  bytes; larger inputs are rejected before any decoding work.
- Base32 padding defaults to "required" (as base64.b32decode requires
  it); Base64 padding defaults to "optional". Base32 and Base16 decoding
  are case-sensitive (uppercase) unless casefold=True, matching the
  standard library default.

Edge cases
----------
- A length remainder of 1 (for example "Z") can never be valid Base64
  and is rejected, with or without padding.
- '=' padding must be the final one or two characters, the total length
  must then be a multiple of 4, and the count must match the length.
- "Zh==" (non-zero trailing bits) is rejected while canonical is True;
  base64.b64decode would accept it as b"f".
- str input must be pure ASCII; bytes input with any byte outside the
  selected alphabet is rejected.
- Empty input encodes to b"" and decodes to b"".
- Base32 accepts only the RFC 4648 group remainders of 2, 4, 5 and 7
  characters (1-4 bytes) and exactly the matching padding (6, 4, 3 or 1
  '='). Trailing bits must be zero while canonical is True; with optional
  padding a value still has a padded and an unpadded spelling.
- Base16 rejects an odd digit count and any non-hex character, and it
  decodes with bytes.fromhex only after validation, so whitespace that
  fromhex would skip is never accepted.

Known limitations
-----------------
- Not constant-time: table lookups and early exits can leak timing.
  Do not use it to decode secret key material where a local timing
  observer is in your threat model.
- No streaming interface; the whole input is held in memory.
- Roughly 5-7 MB/s to encode and 4-6 MB/s to decode Base64 on CPython
  3.12 (measured). The C base64 module measured about 950 MB/s to encode
  and 670 MB/s to decode, roughly 100-150 times faster. Base32 measured
  about 3 MB/s to encode and 10 MB/s to decode.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run with the v3 folder on sys.path (for example, from inside v3/).

::

    from brisart_codec import (
        brisart_b64encode, brisart_b64decode, BrisartBase64Error)
    assert brisart_b64encode(b"foobar") == b"Zm9vYmFy"
    assert brisart_b64decode("Zm9vYmFy") == b"foobar"
    assert brisart_b64decode("Zg") == b"f"          # unpadded is fine
    try:
        brisart_b64decode("Zg=")                     # wrong padding
    except BrisartBase64Error:
        pass
"""

_STANDARD_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_URLSAFE_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_WHITESPACE = b" \t\r\n"


class BrisartBase64Error(ValueError):
    """Raised for any input that is not exactly one valid Base64 encoding."""


_PAIR_TABLES = {}
_VALUE_TABLES = {}


def _pair_table(alphabet):
    # 4096 two-character strings: one lookup encodes 12 bits.
    table = _PAIR_TABLES.get(alphabet)
    if table is None:
        table = [bytes((alphabet[v >> 6], alphabet[v & 63])) for v in range(4096)]
        _PAIR_TABLES[alphabet] = table
    return table


def _value_table(alphabet):
    # 256-byte translation table: alphabet character -> 6-bit value.
    table = _VALUE_TABLES.get(alphabet)
    if table is None:
        raw = bytearray(256)
        for value, char in enumerate(alphabet):
            raw[char] = value
        table = bytes(raw)
        _VALUE_TABLES[alphabet] = table
    return table


def _bytes_like(data, what):
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    raise TypeError("%s requires a bytes-like object, not %s" % (what, type(data).__name__))


def brisart_b64encode(data, urlsafe=False, padding=True):
    """Encode a bytes-like object to Base64 (RFC 4648)."""
    raw = _bytes_like(data, "b64encode()")
    alphabet = _URLSAFE_ALPHABET if urlsafe else _STANDARD_ALPHABET
    pairs = _pair_table(alphabet)
    out = bytearray()
    length = len(raw)
    full = length - length % 3
    for i in range(0, full, 3):
        value = (raw[i] << 16) | (raw[i + 1] << 8) | raw[i + 2]
        out += pairs[value >> 12]
        out += pairs[value & 4095]
    rest = length - full
    if rest == 1:
        value = raw[full] << 4
        out += pairs[value]
        if padding:
            out += b"=="
    elif rest == 2:
        value = (raw[full] << 10) | (raw[full + 1] << 2)
        out += pairs[value >> 6]
        out.append(alphabet[value & 63])
        if padding:
            out += b"="
    return bytes(out)


def brisart_urlsafe_b64encode(data, padding=True):
    """URL-safe Base64 encode ('-' and '_'); padding is optional."""
    return brisart_b64encode(data, urlsafe=True, padding=padding)


def brisart_b64decode(data, urlsafe=False, padding="optional", canonical=True,
                      allow_whitespace=False, max_output=None):
    """Strictly decode Base64 (RFC 4648) text or bytes to bytes."""
    if padding not in ("optional", "required", "forbidden"):
        raise ValueError("padding must be 'optional', 'required' or 'forbidden'")
    if isinstance(data, str):
        try:
            raw = data.encode("ascii")
        except UnicodeEncodeError:
            raise BrisartBase64Error("non-ASCII character in Base64 text") from None
    else:
        raw = _bytes_like(data, "b64decode()")
    if allow_whitespace:
        raw = raw.translate(None, _WHITESPACE)

    stripped = raw.rstrip(b"=")
    pad_count = len(raw) - len(stripped)
    if pad_count > 2:
        raise BrisartBase64Error("too much '=' padding")
    if pad_count:
        if padding == "forbidden":
            raise BrisartBase64Error("'=' padding is not allowed here")
        if len(raw) % 4:
            raise BrisartBase64Error("incorrect '=' padding")
    elif padding == "required" and len(raw) % 4:
        raise BrisartBase64Error("missing '=' padding")

    alphabet = _URLSAFE_ALPHABET if urlsafe else _STANDARD_ALPHABET
    bad = stripped.translate(None, alphabet)
    if bad:
        if b"=" in bad:
            raise BrisartBase64Error("'=' padding in the middle of the data")
        raise BrisartBase64Error("invalid Base64 character: %r" % chr(bad[0]))

    count = len(stripped)
    remainder = count % 4
    if remainder == 1:
        raise BrisartBase64Error("invalid Base64 length")
    if max_output is not None and (count * 3) // 4 > max_output:
        raise BrisartBase64Error("decoded size exceeds max_output")

    values = stripped.translate(_value_table(alphabet))
    out = bytearray()
    full = count - remainder
    for i in range(0, full, 4):
        value = (values[i] << 18) | (values[i + 1] << 12) | (values[i + 2] << 6) | values[i + 3]
        out += value.to_bytes(3, "big")
    if remainder == 2:
        value = (values[full] << 6) | values[full + 1]
        if canonical and value & 15:
            raise BrisartBase64Error("non-canonical Base64: trailing bits are not zero")
        out.append(value >> 4)
    elif remainder == 3:
        value = (values[full] << 12) | (values[full + 1] << 6) | values[full + 2]
        if canonical and value & 3:
            raise BrisartBase64Error("non-canonical Base64: trailing bits are not zero")
        out += (value >> 2).to_bytes(2, "big")
    return bytes(out)


def brisart_urlsafe_b64decode(data, **options):
    """Strict URL-safe Base64 decode; accepts the brisart_b64decode options."""
    return brisart_b64decode(data, urlsafe=True, **options)


# --------------------------------------------------------------------------- Base32 and Base16
_B32_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
_B32HEX_ALPHABET = b"0123456789ABCDEFGHIJKLMNOPQRSTUV"
_B16_ALPHABET = b"0123456789ABCDEF"
_B32_PAD_FOR_REMAINDER = {0: 0, 2: 6, 4: 4, 5: 3, 7: 1}     # characters in the last group -> '=' count
_B32_BYTES_FOR_REMAINDER = {0: 0, 2: 1, 4: 2, 5: 3, 7: 4}
_ASCII_UPPER = bytes(range(97)) + bytes(range(65, 91)) + bytes(range(123, 256))


class BrisartBase32Error(BrisartBase64Error):
    """Raised for any input that is not exactly one valid Base32 or Base16 encoding."""


def _ascii_input(data, what, error):
    if isinstance(data, str):
        try:
            return data.encode("ascii")
        except UnicodeEncodeError:
            raise error("non-ASCII character in %s text" % what) from None
    return _bytes_like(data, what + " decode")


def brisart_b32encode(data, hex=False, padding=True):
    """Encode a bytes-like object to Base32 (RFC 4648 section 6) or Base32hex (section 7)."""
    raw = _bytes_like(data, "b32encode()")
    alphabet = _B32HEX_ALPHABET if hex else _B32_ALPHABET
    out = bytearray()
    length = len(raw)
    full = length - length % 5
    for i in range(0, full, 5):
        value = int.from_bytes(raw[i:i + 5], "big")
        for shift in (35, 30, 25, 20, 15, 10, 5, 0):
            out.append(alphabet[(value >> shift) & 31])
    rest = length - full
    if rest:
        chars = {1: 2, 2: 4, 3: 5, 4: 7}[rest]
        value = int.from_bytes(raw[full:], "big") << (chars * 5 - rest * 8)
        for shift in range((chars - 1) * 5, -1, -5):
            out.append(alphabet[(value >> shift) & 31])
        if padding:
            out += b"=" * (8 - chars)
    return bytes(out)


def brisart_b32decode(data, hex=False, padding="required", casefold=False, canonical=True,
                      max_output=None):
    """Strictly decode Base32 or Base32hex (RFC 4648) to bytes."""
    if padding not in ("optional", "required", "forbidden"):
        raise ValueError("padding must be 'optional', 'required' or 'forbidden'")
    raw = _ascii_input(data, "Base32", BrisartBase32Error)
    if casefold:
        raw = raw.translate(_ASCII_UPPER)
    stripped = raw.rstrip(b"=")
    pad_count = len(raw) - len(stripped)
    count = len(stripped)
    remainder = count % 8
    if remainder not in _B32_PAD_FOR_REMAINDER:
        raise BrisartBase32Error("invalid Base32 length")
    if pad_count:
        if padding == "forbidden":
            raise BrisartBase32Error("'=' padding is not allowed here")
        if pad_count != _B32_PAD_FOR_REMAINDER[remainder]:
            raise BrisartBase32Error("incorrect '=' padding")
    elif padding == "required" and remainder:
        raise BrisartBase32Error("missing '=' padding")
    alphabet = _B32HEX_ALPHABET if hex else _B32_ALPHABET
    bad = stripped.translate(None, alphabet)
    if bad:
        if b"=" in bad:
            raise BrisartBase32Error("'=' padding in the middle of the data")
        raise BrisartBase32Error("invalid Base32 character: %r" % chr(bad[0]))
    produced = (count // 8) * 5 + _B32_BYTES_FOR_REMAINDER[remainder]
    if max_output is not None and produced > max_output:
        raise BrisartBase32Error("decoded size exceeds max_output")
    table = bytearray(256)
    for value, char in enumerate(alphabet):
        table[char] = value
    values = stripped.translate(bytes(table))
    out = bytearray()
    full = count - remainder
    for i in range(0, full, 8):
        value = 0
        for v in values[i:i + 8]:
            value = (value << 5) | v
        out += value.to_bytes(5, "big")
    if remainder:
        value = 0
        for v in values[full:]:
            value = (value << 5) | v
        size = _B32_BYTES_FOR_REMAINDER[remainder]
        spare = remainder * 5 - size * 8
        if canonical and value & ((1 << spare) - 1):
            raise BrisartBase32Error("non-canonical Base32: trailing bits are not zero")
        out += (value >> spare).to_bytes(size, "big")
    return bytes(out)


def brisart_b16encode(data, lowercase=False):
    """Encode a bytes-like object to Base16 (RFC 4648 section 8): uppercase hex by default."""
    text = _bytes_like(data, "b16encode()").hex()
    return (text if lowercase else text.upper()).encode("ascii")


def brisart_b16decode(data, casefold=False, max_output=None):
    """Strictly decode Base16 (RFC 4648 section 8). Lowercase digits need casefold=True."""
    raw = _ascii_input(data, "Base16", BrisartBase32Error)
    if casefold:
        raw = raw.translate(_ASCII_UPPER)
    if len(raw) % 2:
        raise BrisartBase32Error("Base16 input has an odd number of digits")
    bad = raw.translate(None, _B16_ALPHABET)
    if bad:
        raise BrisartBase32Error("invalid Base16 character: %r" % chr(bad[0]))
    if max_output is not None and len(raw) // 2 > max_output:
        raise BrisartBase32Error("decoded size exceeds max_output")
    return bytes.fromhex(raw.decode("ascii"))


__all__ = [
    "BrisartBase32Error",
    "BrisartBase64Error",
    "brisart_b16decode",
    "brisart_b16encode",
    "brisart_b32decode",
    "brisart_b32encode",
    "brisart_b64decode",
    "brisart_b64encode",
    "brisart_urlsafe_b64decode",
    "brisart_urlsafe_b64encode",
]
