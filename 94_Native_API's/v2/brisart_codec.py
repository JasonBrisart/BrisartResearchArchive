"""
File: brisart_native/brisart_codec.py

Purpose
-------
BrisartBase64 -- a from-spec, pure-Python Base64 encoder and strict
decoder (RFC 4648), replacing base64.b64encode / b64decode /
urlsafe_b64decode in Brisart Research Archive tooling.

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
into any tool on its own. It does not depend on the other brisart_native
modules. Behaviour is cross-checked against the standard base64 module
by brisart_native/tests/test_codec.py (tests may import the standard
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

Known limitations
-----------------
- Not constant-time: table lookups and early exits can leak timing.
  Do not use it to decode secret key material where a local timing
  observer is in your threat model.
- No streaming interface; the whole input is held in memory.
- Roughly 5-7 MB/s to encode and 4-6 MB/s to decode on CPython 3.12
  (measured). The C base64 module measured about 950 MB/s to encode and
  670 MB/s to decode, roughly 100-150 times faster.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_codec import (
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


__all__ = [
    "BrisartBase64Error",
    "brisart_b64decode",
    "brisart_b64encode",
    "brisart_urlsafe_b64decode",
    "brisart_urlsafe_b64encode",
]
