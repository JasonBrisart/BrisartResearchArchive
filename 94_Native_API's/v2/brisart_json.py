"""
File: brisart_native/brisart_json.py

Purpose
-------
BrisartJSON -- a from-spec, pure-Python JSON parser and serializer
(RFC 8259) with safe defaults, replacing json.loads / json.dumps in
Brisart Research Archive tooling.

Public interface:
- brisart_loads(text, *, allow_nan=False, max_depth=DEFAULT_MAX_DEPTH,
  max_length=DEFAULT_MAX_LENGTH, duplicate_keys="error",
  allow_lone_surrogates=False) -- Parse a JSON document from str or
  UTF-8 bytes.
- brisart_dumps(value, indent=None, sort_keys=False, *,
  ensure_ascii=False, allow_nan=False, separators=None,
  max_depth=DEFAULT_MAX_DEPTH, allow_lone_surrogates=False) --
  Serialize plain Python data to a JSON str.
- BrisartJSONDecodeError -- A ValueError subclass carrying msg, pos,
  lineno and colno; the only exception brisart_loads raises for bad
  input.
- DEFAULT_MAX_DEPTH (100) and DEFAULT_MAX_LENGTH (64 Mi characters).

Design notes:

Where the standard json module is lenient, this module is strict by
default, because leniency is what lets two parsers disagree about the
same text. The deliberate differences are:

1. Numbers follow the RFC 8259 grammar exactly: no leading zeros, no
   "1.", no ".5", no "+1", ASCII digits only. (The previous version
   accepted 01, 1. and non-ASCII digits.) Integer and float literals are
   limited to 4300 characters and a float that overflows to infinity is
   an error, not inf.
2. NaN, Infinity and -Infinity are errors unless allow_nan=True. json
   accepts them by default and json.dumps emits them, producing text
   that is not JSON.
3. Duplicate object keys are an error unless duplicate_keys="first" or
   "last". Parsers that disagree about which duplicate wins are a known
   source of security bugs.
4. Unpaired UTF-16 surrogates (a raw lone surrogate, or an escape such
   as \\ud800 not followed by a low surrogate) are errors unless
   allow_lone_surrogates=True, because they cannot be encoded as UTF-8
   and crash later consumers (RFC 7493 requires rejecting them).
5. Nesting deeper than max_depth is a BrisartJSONDecodeError. Both the
   parser and the serializer are iterative, so no input can trigger
   RecursionError or exhaust the interpreter stack.
6. \\u escapes must be exactly four ASCII hex digits. int(text, 16)
   would also accept "+123", " 123" and "1_23"; this module does not.
7. brisart_dumps refuses NaN/Infinity, circular references, non-str
   object keys (json silently turns 1 and "1" into the same key) and
   indent or separator strings that would produce invalid JSON, and it
   always escapes U+2028 and U+2029.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other brisart_native
modules. Output is cross-checked against the json module (with the
leniencies above switched to match) by brisart_native/tests/test_json.py
(tests may import the standard library; this module may not).

Settings / parameters
---------------------
- allow_nan -- False (default) rejects NaN/Infinity on both parse and
  dump; True accepts and emits the non-standard tokens.
- max_depth -- Most containers that may be open at once (default 100).
  Applied by both brisart_loads and brisart_dumps.
- max_length -- Parse only. Largest accepted document in characters
  (default 67108864); None disables the limit.
- duplicate_keys -- "error" (default), "first" or "last".
- allow_lone_surrogates -- False (default) rejects unpaired surrogates.
- indent -- Dump only. None for one line, a non-negative int number of
  spaces, or a str made only of space, tab, CR and LF.
- separators -- Dump only. (item_separator, key_separator); each may
  contain only its comma or colon plus JSON whitespace.
- ensure_ascii -- Dump only. True escapes every non-ASCII character as
  \\uXXXX (surrogate pairs above U+FFFF); default False.

Edge cases
----------
- A leading UTF-8 byte order mark is rejected, matching json.loads on
  str. bytes input must be valid UTF-8.
- "-0" parses to the int 0 and "-0.0" to the float -0.0.
- The empty string, whitespace only, and a trailing comma are errors.
- All JSON whitespace is exactly space, tab, LF and CR.
- Round trips are exact for int, str, bool, None, list and dict values
  and for every finite float (repr is the shortest exact form).
- tuple dumps as an array; it loads back as a list.

Known limitations
-----------------
- Pure Python. Measured on CPython 3.12: parsing runs at about 2.7-3.2
  MB/s for documents of many small values and about 40 MB/s for long
  strings; serializing runs at about 3-10 MB/s, and about 200 MB/s for
  long strings. The C json module parses roughly 15-25 times faster. A
  64 Mi-character document of small values takes about 20 seconds, so
  lower max_length for untrusted input. Deeply nested small containers
  serialize more slowly than flat data.
- Floats are converted with float(), which rounds correctly; integers
  of any size up to 4300 digits are exact.
- No streaming, no object hooks and no custom encoders: only None, bool,
  int, float, str, list, tuple and dict with str keys are serializable.
- Dumping a str subclass or int subclass uses its plain value.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_json import (
        brisart_loads, brisart_dumps, BrisartJSONDecodeError)
    assert brisart_loads('{"a": [1, 2.5, null]}') == {"a": [1, 2.5, None]}
    assert brisart_dumps({"b": 1, "a": 2}, sort_keys=True,
                         separators=(",", ":")) == '{"a":2,"b":1}'
    for bad in ("01", "[1,]", '{"a":1,"a":2}', "NaN", '"\\\\ud800"'):
        try:
            brisart_loads(bad)
        except BrisartJSONDecodeError:
            pass
"""

DEFAULT_MAX_DEPTH = 100
DEFAULT_MAX_LENGTH = 64 * 1024 * 1024
_MAX_NUMBER_CHARS = 4300

_WHITESPACE = " \t\n\r"
_HEX = frozenset("0123456789abcdefABCDEF")
_SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}

_ESCAPE_TABLE = {i: "\\u%04x" % i for i in range(32)}
_ESCAPE_TABLE.update({
    ord('"'): '\\"', ord("\\"): "\\\\", 8: "\\b", 9: "\\t", 10: "\\n", 12: "\\f", 13: "\\r",
    0x2028: "\\u2028", 0x2029: "\\u2029",
})

_NAN = float("nan")
_INF = float("inf")


class BrisartJSONDecodeError(ValueError):
    """Raised for malformed or unsafe JSON input."""

    def __init__(self, message, text, position):
        position = max(0, min(position, len(text)))
        self.msg = message
        self.pos = position
        self.position = position
        self.lineno = text.count("\n", 0, position) + 1
        self.colno = position - text.rfind("\n", 0, position)
        ValueError.__init__(self, "%s: line %d column %d (char %d)" % (message, self.lineno, self.colno, position))


def _skip(text, pos, length):
    while pos < length and text[pos] in _WHITESPACE:
        pos += 1
    return pos


def _scan_string(text, pos, length, allow_lone):
    """Parse a string whose opening quote is at pos - 1; return (value, next_pos)."""
    chunks = None
    open_at = pos - 1
    quote = text.find('"', pos)
    while True:
        if quote == -1:
            raise BrisartJSONDecodeError("Unterminated string", text, open_at)
        slash = text.find("\\", pos, quote)
        end = quote if slash == -1 else slash
        if end > pos:
            segment = text[pos:end]
            if min(segment) < " ":
                for offset, char in enumerate(segment):
                    if char < " ":
                        raise BrisartJSONDecodeError("Invalid control character in string", text, pos + offset)
            if chunks is not None:
                chunks.append(segment)
            elif slash == -1:
                return segment, quote + 1
            else:
                chunks = [segment]
        if slash == -1:
            return ("" if chunks is None else "".join(chunks)), quote + 1
        if chunks is None:
            chunks = []
        if slash + 1 >= length:
            raise BrisartJSONDecodeError("Unterminated string", text, open_at)
        code = text[slash + 1]
        if code in _SIMPLE_ESCAPES:
            chunks.append(_SIMPLE_ESCAPES[code])
            pos = slash + 2
        elif code != "u":
            raise BrisartJSONDecodeError("Invalid escape character %r" % code, text, slash)
        else:
            digits = text[slash + 2:slash + 6]
            if len(digits) != 4 or not _HEX.issuperset(digits):
                raise BrisartJSONDecodeError("Invalid \\u escape", text, slash)
            value = int(digits, 16)
            pos = slash + 6
            if 0xD800 <= value <= 0xDBFF:
                low_digits = text[pos + 2:pos + 6] if text.startswith("\\u", pos) else ""
                if len(low_digits) == 4 and _HEX.issuperset(low_digits) and 0xDC00 <= int(low_digits, 16) <= 0xDFFF:
                    value = 0x10000 + ((value - 0xD800) << 10) + (int(low_digits, 16) - 0xDC00)
                    pos += 6
                elif not allow_lone:
                    raise BrisartJSONDecodeError("Unpaired high surrogate escape", text, slash)
            elif 0xDC00 <= value <= 0xDFFF and not allow_lone:
                raise BrisartJSONDecodeError("Unpaired low surrogate escape", text, slash)
            chunks.append(chr(value))
        if quote < pos:
            quote = text.find('"', pos)      # only search again once the known quote has been passed


def _scan_number(text, pos, length):
    """Parse a number at pos using the RFC 8259 grammar; return (value, next_pos)."""
    start = pos
    if text[pos] == "-":
        pos += 1
    if pos >= length:
        raise BrisartJSONDecodeError("Invalid number", text, start)
    first = text[pos]
    if first == "0":
        pos += 1
    elif "1" <= first <= "9":
        pos += 1
        while pos < length and "0" <= text[pos] <= "9":
            pos += 1
    else:
        raise BrisartJSONDecodeError("Invalid number", text, start)
    is_float = False
    if pos < length and text[pos] == ".":
        pos += 1
        digits_from = pos
        while pos < length and "0" <= text[pos] <= "9":
            pos += 1
        if pos == digits_from:
            raise BrisartJSONDecodeError("Invalid number: digits required after '.'", text, start)
        is_float = True
    if pos < length and text[pos] in "eE":
        pos += 1
        if pos < length and text[pos] in "+-":
            pos += 1
        digits_from = pos
        while pos < length and "0" <= text[pos] <= "9":
            pos += 1
        if pos == digits_from:
            raise BrisartJSONDecodeError("Invalid number: digits required in exponent", text, start)
        is_float = True
    if pos - start > _MAX_NUMBER_CHARS:
        raise BrisartJSONDecodeError("Number literal too long", text, start)
    raw = text[start:pos]
    if is_float:
        value = float(raw)
        if value in (_INF, -_INF):
            raise BrisartJSONDecodeError("Number out of range", text, start)
        return value, pos
    return int(raw), pos


def _decode(text, allow_nan, max_depth, duplicate_keys, allow_lone):
    length = len(text)
    stack = []          # open containers, outermost first
    keys = []           # pending key of each open dict; None for open lists
    key_at = []         # source position of that pending key
    pos = _skip(text, 0, length)
    try:
        while True:
            if pos >= length:
                raise BrisartJSONDecodeError("Expecting value", text, pos)
            char = text[pos]
            if char == "{":
                if len(stack) >= max_depth:
                    raise BrisartJSONDecodeError("Maximum nesting depth (%d) exceeded" % max_depth, text, pos)
                pos = _skip(text, pos + 1, length)
                if text[pos] == "}":
                    value = {}
                    pos += 1
                else:
                    if text[pos] != '"':
                        raise BrisartJSONDecodeError("Expecting property name enclosed in double quotes", text, pos)
                    at = pos
                    key, pos = _scan_string(text, pos + 1, length, allow_lone)
                    pos = _skip(text, pos, length)
                    if text[pos] != ":":
                        raise BrisartJSONDecodeError("Expecting ':' delimiter", text, pos)
                    pos = _skip(text, pos + 1, length)
                    stack.append({})
                    keys.append(key)
                    key_at.append(at)
                    continue
            elif char == "[":
                if len(stack) >= max_depth:
                    raise BrisartJSONDecodeError("Maximum nesting depth (%d) exceeded" % max_depth, text, pos)
                pos = _skip(text, pos + 1, length)
                if text[pos] == "]":
                    value = []
                    pos += 1
                else:
                    stack.append([])
                    keys.append(None)
                    key_at.append(pos)
                    continue
            elif char == '"':
                value, pos = _scan_string(text, pos + 1, length, allow_lone)
            elif char == "t" and text.startswith("true", pos):
                value, pos = True, pos + 4
            elif char == "f" and text.startswith("false", pos):
                value, pos = False, pos + 5
            elif char == "n" and text.startswith("null", pos):
                value, pos = None, pos + 4
            elif char == "-" or "0" <= char <= "9":
                if text.startswith("-Infinity", pos):
                    if not allow_nan:
                        raise BrisartJSONDecodeError("-Infinity is not valid JSON (allow_nan=False)", text, pos)
                    value, pos = -_INF, pos + 9
                else:
                    value, pos = _scan_number(text, pos, length)
            elif char == "N" and text.startswith("NaN", pos):
                if not allow_nan:
                    raise BrisartJSONDecodeError("NaN is not valid JSON (allow_nan=False)", text, pos)
                value, pos = _NAN, pos + 3
            elif char == "I" and text.startswith("Infinity", pos):
                if not allow_nan:
                    raise BrisartJSONDecodeError("Infinity is not valid JSON (allow_nan=False)", text, pos)
                value, pos = _INF, pos + 8
            else:
                raise BrisartJSONDecodeError("Expecting value", text, pos)
            while True:                                  # a value is complete: attach it to its parent
                if not stack:
                    pos = _skip(text, pos, length)
                    if pos != length:
                        raise BrisartJSONDecodeError("Extra data after the JSON value", text, pos)
                    return value
                parent = stack[-1]
                if keys[-1] is None:
                    parent.append(value)
                    pos = _skip(text, pos, length)
                    char = text[pos]
                    if char == ",":
                        pos = _skip(text, pos + 1, length)
                        break
                    if char == "]":
                        pos += 1
                        value = stack.pop()
                        keys.pop()
                        key_at.pop()
                        continue
                    raise BrisartJSONDecodeError("Expecting ',' or ']'", text, pos)
                key = keys[-1]
                if key in parent:
                    if duplicate_keys == "error":
                        raise BrisartJSONDecodeError("Duplicate object key %s" % ascii(key[:60]), text, key_at[-1])
                    if duplicate_keys == "last":
                        parent[key] = value
                else:
                    parent[key] = value
                pos = _skip(text, pos, length)
                char = text[pos]
                if char == ",":
                    pos = _skip(text, pos + 1, length)
                    if text[pos] != '"':
                        raise BrisartJSONDecodeError("Expecting property name enclosed in double quotes", text, pos)
                    key_at[-1] = pos
                    keys[-1], pos = _scan_string(text, pos + 1, length, allow_lone)
                    pos = _skip(text, pos, length)
                    if text[pos] != ":":
                        raise BrisartJSONDecodeError("Expecting ':' delimiter", text, pos)
                    pos = _skip(text, pos + 1, length)
                    break
                if char == "}":
                    pos += 1
                    value = stack.pop()
                    keys.pop()
                    key_at.pop()
                    continue
                raise BrisartJSONDecodeError("Expecting ',' or '}'", text, pos)
    except IndexError:
        raise BrisartJSONDecodeError("Unexpected end of data", text, length) from None


def brisart_loads(text, *, allow_nan=False, max_depth=DEFAULT_MAX_DEPTH, max_length=DEFAULT_MAX_LENGTH,
                  duplicate_keys="error", allow_lone_surrogates=False):
    """Parse a JSON document (str, or UTF-8 bytes) into Python values."""
    if duplicate_keys not in ("error", "first", "last"):
        raise ValueError("duplicate_keys must be 'error', 'first' or 'last'")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")
    if isinstance(text, (bytes, bytearray, memoryview)):
        raw = bytes(text)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BrisartJSONDecodeError("Invalid UTF-8 at byte %d" % error.start, "", 0) from None
    elif not isinstance(text, str):
        raise TypeError("the JSON document must be str or bytes, not %s" % type(text).__name__)
    if max_length is not None and len(text) > max_length:
        raise BrisartJSONDecodeError("Document of %d characters exceeds max_length=%d" % (len(text), max_length), "", 0)
    if text.startswith("\ufeff"):
        raise BrisartJSONDecodeError("Unexpected byte order mark; decode with utf-8-sig first", text, 0)
    if not allow_lone_surrogates and not text.isascii():
        try:
            text.encode("utf-8")
        except UnicodeEncodeError as error:
            raise BrisartJSONDecodeError("Unpaired surrogate in the document", text, error.start) from None
    return _decode(text, allow_nan, max_depth, duplicate_keys, allow_lone_surrogates)


# --------------------------------------------------------------------------- serializer
def _ascii_escape(text):
    pieces = []
    for char in text:
        code = ord(char)
        if code < 128:
            pieces.append(char)
        elif code < 0x10000:
            pieces.append("\\u%04x" % code)
        else:
            code -= 0x10000
            pieces.append("\\u%04x\\u%04x" % (0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
    return "".join(pieces)


def _encode_string(text, ensure_ascii, allow_lone):
    if not allow_lone and not text.isascii():
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("cannot serialize a string containing an unpaired surrogate") from None
    escaped = text.translate(_ESCAPE_TABLE)
    if ensure_ascii and not escaped.isascii():
        escaped = _ascii_escape(escaped)
    return '"' + escaped + '"'


def _non_finite(value, allow_nan):
    if not allow_nan:
        raise ValueError("Out of range float values are not JSON compliant: %r" % value)
    return "NaN" if value != value else ("Infinity" if value > 0 else "-Infinity")


def _scalar(value, ensure_ascii, allow_nan, allow_lone):
    """Return the JSON text of a scalar, or None if value is a container."""
    kind = type(value)
    if kind is str:
        return _encode_string(value, ensure_ascii, allow_lone)
    if kind is float:
        if value - value == 0.0:                  # False for nan and for both infinities
            return float.__repr__(value)
        return _non_finite(value, allow_nan)
    if kind is int:
        return int.__repr__(value)
    if kind is list or kind is dict or kind is tuple:
        return None
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):                    # subclasses: serialize the plain value
        return _encode_string(str.__str__(value), ensure_ascii, allow_lone)
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float):
        if value - value == 0.0:
            return float.__repr__(value)
        return _non_finite(value, allow_nan)
    if isinstance(value, (list, tuple, dict)):
        return None
    raise TypeError("Object of type %s is not JSON serializable" % type(value).__name__)


def _structural(text, mark):
    if not isinstance(text, str) or text.strip(_WHITESPACE) != mark:
        raise ValueError("separators must be (item_separator, key_separator) made of ',' / ':' and JSON whitespace")
    return text


def _leaf_text(item, level, indent_text, item_sep, key_sep, sort_keys, ensure_ascii, allow_nan, allow_lone, max_depth):
    """Encode a list/tuple/dict whose children are all scalars, or return None if any child is a container.

    A container with only scalar children cannot contain a cycle and needs no
    explicit work stack, so it is written in one pass. It aborts at the first
    container child, so mixed containers cost at most one wasted pass over
    their leading scalars.
    """
    is_dict = isinstance(item, dict)
    if is_dict:
        entries = list(dict.items(item))
        for key, _ in entries:
            if type(key) is not str and not isinstance(key, str):
                raise TypeError("keys must be str, not %s" % type(key).__name__)
        if sort_keys:
            entries.sort(key=lambda pair: pair[0])
    else:
        entries = item
    if not entries:
        return "{}" if is_dict else "[]"
    if level >= max_depth:
        return None                      # the general path raises the depth error
    if indent_text is None:
        inner = outer = ""
    else:
        inner = "\n" + indent_text * (level + 1)
        outer = "\n" + indent_text * level
    between = item_sep + inner
    parts = []
    if is_dict:
        for key, child in entries:
            text = _scalar(child, ensure_ascii, allow_nan, allow_lone)
            if text is None:
                return None
            parts.append(_encode_string(key if type(key) is str else str.__str__(key), ensure_ascii, allow_lone)
                         + key_sep + text)
        return "{" + inner + between.join(parts) + outer + "}"
    for child in entries:
        text = _scalar(child, ensure_ascii, allow_nan, allow_lone)
        if text is None:
            return None
        parts.append(text)
    return "[" + inner + between.join(parts) + outer + "]"


def brisart_dumps(value, indent=None, sort_keys=False, *, ensure_ascii=False, allow_nan=False,
                  separators=None, max_depth=DEFAULT_MAX_DEPTH, allow_lone_surrogates=False):
    """Serialize plain Python data to a JSON string."""
    if isinstance(indent, bool):
        raise ValueError("indent must be None, a non-negative int or a whitespace str")
    if indent is None:
        indent_text = None
    elif isinstance(indent, int):
        if indent < 0:
            raise ValueError("indent must not be negative")
        indent_text = " " * indent
    elif isinstance(indent, str) and not indent.strip(_WHITESPACE):
        indent_text = indent
    else:
        raise ValueError("indent must be None, a non-negative int or a whitespace str")
    if separators is None:
        item_sep, key_sep = (", " if indent_text is None else ","), ": "
    else:
        if not isinstance(separators, (tuple, list)) or len(separators) != 2:
            raise ValueError("separators must be a pair of strings")
        item_sep, key_sep = _structural(separators[0], ","), _structural(separators[1], ":")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("max_depth must be a non-negative integer")

    def line(level):
        return "" if indent_text is None else "\n" + indent_text * level

    pieces = []
    active = set()
    tasks = [(0, value, 0)]                     # (kind, payload, level): 0 value, 1 text, 2 leave container
    while tasks:
        kind, item, level = tasks.pop()
        if kind == 1:
            pieces.append(item)
            continue
        if kind == 2:
            active.discard(item)
            continue
        text = _scalar(item, ensure_ascii, allow_nan, allow_lone_surrogates)
        if text is not None:
            pieces.append(text)
            continue
        leaf = _leaf_text(item, level, indent_text, item_sep, key_sep, sort_keys, ensure_ascii, allow_nan,
                          allow_lone_surrogates, max_depth)
        if leaf is not None:
            pieces.append(leaf)
            continue
        if level >= max_depth:
            raise ValueError("Maximum nesting depth (%d) exceeded" % max_depth)
        if id(item) in active:
            raise ValueError("Circular reference detected")
        is_dict = isinstance(item, dict)
        if is_dict:
            entries = list(dict.items(item))
            for key, _ in entries:
                if not isinstance(key, str):
                    raise TypeError("keys must be str, not %s" % type(key).__name__)
            if sort_keys:
                entries.sort(key=lambda pair: pair[0])
        else:
            entries = list(item)
        if not entries:
            pieces.append("{}" if is_dict else "[]")
            continue
        active.add(id(item))
        between = item_sep + line(level + 1)
        close = line(level) + ("}" if is_dict else "]")
        forward = []                    # this container's work in output order
        text_run = [("{" if is_dict else "[") + line(level + 1)]
        for index, entry in enumerate(entries):
            if index:
                text_run.append(between)
            if is_dict:
                key, child = entry
                text_run.append(_encode_string(str.__str__(key), ensure_ascii, allow_lone_surrogates) + key_sep)
            else:
                child = entry
            text = _scalar(child, ensure_ascii, allow_nan, allow_lone_surrogates)
            if text is None:                # a container child: a leaf container is written inline too
                text = _leaf_text(child, level + 1, indent_text, item_sep, key_sep, sort_keys, ensure_ascii,
                                  allow_nan, allow_lone_surrogates, max_depth)
            if text is not None:
                text_run.append(text)       # scalars and leaf containers go straight into the running text
            else:
                forward.append((1, "".join(text_run), 0))
                text_run = []
                forward.append((0, child, level + 1))
        text_run.append(close)
        forward.append((1, "".join(text_run), 0))
        forward.append((2, id(item), 0))
        forward.reverse()
        tasks.extend(forward)
    return "".join(pieces)


__all__ = [
    "BrisartJSONDecodeError",
    "DEFAULT_MAX_DEPTH",
    "DEFAULT_MAX_LENGTH",
    "brisart_dumps",
    "brisart_loads",
]
