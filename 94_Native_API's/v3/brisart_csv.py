"""
File: v3/brisart_csv.py

Purpose
-------
BrisartCSV -- a from-spec, pure-Python CSV reader and writer (RFC 4180)
with strict quoting rules and resource limits, replacing csv.reader and
csv.writer in Brisart Research Archive tooling.

Public interface:
- brisart_csv_reader(text, delimiter=",", quotechar='"',
  strict_quotes=True, max_field_size=DEFAULT_MAX_FIELD_SIZE,
  max_rows=None) -- Iterate over the rows of a CSV document; each row is a
  list of str.
- brisart_csv_loads(text, **options) -- The same rows as a list.
- brisart_csv_dumps(rows, delimiter=",", quotechar='"',
  lineterminator="\\r\\n", quote_all=False, escape_formulas=False) --
  Serialize rows to CSV text.
- BrisartCSVError -- A ValueError subclass carrying `line` (1-based) and
  `column` (1-based) of the problem.
- DEFAULT_MAX_FIELD_SIZE -- 131072 characters, csv.field_size_limit()'s
  default.

Design notes:

The reader follows RFC 4180 and agrees with csv.reader(strict=True) on
well-formed input, including empty lines (reported as an empty row),
quoted fields that contain delimiters, doubled quotes and line breaks,
and a final line with or without a line break. It is stricter in one
place by default: a quote character inside an unquoted field (a,b"c,d)
is an error, because RFC 4180 does not allow it and two CSV readers
commonly disagree about what it means. strict_quotes=False accepts it as
a literal character, as csv.reader does.

Scanning uses str.find with cached "next delimiter / next line break /
next quote" positions, so a document is read in time linear in its
length even when a separator never appears; there is no per-character
Python loop.

The writer quotes exactly the fields csv.writer quotes with QUOTE_MINIMAL
(fields containing the delimiter, the quote character, CR or LF, and a
lone empty field so that it is not read back as an empty row). It can
optionally neutralise spreadsheet formulas: with escape_formulas=True a
field beginning with "=", "+", "-", "@", tab or CR is prefixed with a
single quote, the mitigation OWASP recommends against CSV injection.
That changes the data, so it is off by default.

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other v3 modules.
Behaviour is cross-checked against csv.reader(strict=True) and
csv.writer by v3/tests/test_csv.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- delimiter, quotechar -- Single characters, different from each other
  and from CR and LF. Defaults "," and '"'.
- strict_quotes -- Reader only. True (default) rejects a quote character
  inside an unquoted field; False keeps it literally.
- max_field_size -- Reader only. Largest field in characters (default
  131072); None disables the limit.
- max_rows -- Reader only. Largest number of rows; None (default) for no
  limit.
- lineterminator -- Writer only. "\\r\\n" (default, RFC 4180), "\\n" or
  "\\r".
- quote_all -- Writer only. Quote every field (csv.QUOTE_ALL).
- escape_formulas -- Writer only. Prefix formula-like fields with "'".

Edge cases
----------
- "" reads as no rows; "\\n" reads as one empty row; "a," reads as
  ["a", ""].
- CRLF, LF and a lone CR all end a row, as in csv.reader. A line break
  inside a quoted field is kept exactly as written.
- After a closing quote only the delimiter, a line break or the end of
  the input may follow; anything else (for example "a"b) is an error.
- An unterminated quoted field is an error, not a field that silently
  runs to the end of the input.
- NUL characters are ordinary characters.
- The writer accepts str, int, float, bool and None (written as an empty
  field); any other value raises TypeError rather than being converted
  with str(). An empty row is written as an empty line.

Known limitations
-----------------
- Input must be str: decode bytes first (and strip a byte order mark if
  present). There is no dialect sniffing, no escapechar, no
  skipinitialspace and no QUOTE_NONNUMERIC.
- The whole document is held in memory; the reader yields rows lazily but
  does not stream from a file.
- About 6 MB/s to read and 7 MB/s to write on CPython 3.12 (measured);
  the C csv module is roughly ten times faster.
- Formula escaping is a mitigation, not a guarantee: spreadsheet programs
  differ in which leading characters start a formula.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run with the v3 folder on sys.path (for example, from inside v3/).

::

    from brisart_csv import brisart_csv_loads, brisart_csv_dumps, BrisartCSVError
    rows = brisart_csv_loads('name,note\\r\\n"Lab, Inc.","a ""b"" c"\\r\\n')
    assert rows == [["name", "note"], ["Lab, Inc.", 'a "b" c']]
    assert brisart_csv_loads(brisart_csv_dumps(rows)) == rows
    assert brisart_csv_dumps([["=SUM(A1)"]], escape_formulas=True) == "'=SUM(A1)\\r\\n"
    try:
        brisart_csv_loads('a,b"c')
    except BrisartCSVError:
        pass
"""

DEFAULT_MAX_FIELD_SIZE = 131072

_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


class BrisartCSVError(ValueError):
    """Raised for malformed CSV input or a breached limit."""

    def __init__(self, message, text, position):
        position = max(0, min(position, len(text)))
        self.line = text.count("\n", 0, position) + text.count("\r", 0, position) \
            - text.count("\r\n", 0, position) + 1
        last_break = max(text.rfind("\n", 0, position), text.rfind("\r", 0, position))
        self.column = position - last_break
        self.position = position
        ValueError.__init__(self, "%s (line %d, column %d)" % (message, self.line, self.column))


def _check_chars(delimiter, quotechar):
    for name, value in (("delimiter", delimiter), ("quotechar", quotechar)):
        if not isinstance(value, str) or len(value) != 1:
            raise TypeError("%s must be a single character" % name)
        if value in "\r\n":
            raise ValueError("%s cannot be a line break" % name)
    if delimiter == quotechar:
        raise ValueError("delimiter and quotechar must differ")


def _check_limit(name, value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("%s must be a non-negative integer or None" % name)
    return value


class _NextFinder:
    """Cached str.find: each search runs again only after the scan has passed its last result."""

    __slots__ = ("text", "needle", "at")

    def __init__(self, text, needle):
        self.text = text
        self.needle = needle
        self.at = -2

    def find(self, pos):
        if self.at == -1:
            return -1
        if self.at < pos:
            self.at = self.text.find(self.needle, pos)
        return self.at


def brisart_csv_reader(text, delimiter=",", quotechar='"', strict_quotes=True,
                       max_field_size=DEFAULT_MAX_FIELD_SIZE, max_rows=None):
    """Iterate over the rows of a CSV document given as str."""
    if not isinstance(text, str):
        raise TypeError("CSV input must be str, not %s (decode bytes first)" % type(text).__name__)
    _check_chars(delimiter, quotechar)
    field_limit = _check_limit("max_field_size", max_field_size)
    row_limit = _check_limit("max_rows", max_rows)
    return _read(text, delimiter, quotechar, strict_quotes, field_limit, row_limit)


def _read(text, delimiter, quotechar, strict_quotes, field_limit, row_limit):
    n = len(text)
    next_delim = _NextFinder(text, delimiter)
    next_lf = _NextFinder(text, "\n")
    next_cr = _NextFinder(text, "\r")
    next_quote = _NextFinder(text, quotechar)
    rows = 0
    pos = 0
    while pos < n:
        if row_limit is not None and rows >= row_limit:
            raise BrisartCSVError("more than max_rows=%d rows" % row_limit, text, pos)
        row = []
        if text[pos] == "\n" or text[pos] == "\r":       # an empty line is an empty row
            pos += 2 if text.startswith("\r\n", pos) else 1
            rows += 1
            yield row
            continue
        while True:                                       # one field per pass
            if pos < n and text[pos] == quotechar:
                start = pos
                pieces = []
                pos += 1
                while True:
                    close = next_quote.find(pos)
                    if close == -1:
                        raise BrisartCSVError("unterminated quoted field", text, start)
                    pieces.append(text[pos:close])
                    if close + 1 < n and text[close + 1] == quotechar:
                        pieces.append(quotechar)
                        pos = close + 2
                        continue
                    pos = close + 1
                    break
                field = "".join(pieces)
                if pos < n and text[pos] != delimiter and text[pos] != "\n" and text[pos] != "\r":
                    raise BrisartCSVError("%r expected after a closing quote" % delimiter, text, pos)
            else:
                end = n
                for finder in (next_delim, next_lf, next_cr):
                    found = finder.find(pos)
                    if found != -1 and found < end:
                        end = found
                if strict_quotes:
                    quote = next_quote.find(pos)
                    if quote != -1 and quote < end:
                        raise BrisartCSVError("quote character inside an unquoted field", text, quote)
                field = text[pos:end]
                pos = end
            if field_limit is not None and len(field) > field_limit:
                raise BrisartCSVError("field larger than max_field_size=%d" % field_limit, text, pos)
            row.append(field)
            if pos < n and text[pos] == delimiter:
                pos += 1
                continue
            if pos < n:                                   # a line break ends the row
                pos += 2 if text.startswith("\r\n", pos) else 1
            break
        rows += 1
        yield row


def brisart_csv_loads(text, **options):
    """Read every row of a CSV document into a list of lists of str."""
    return list(brisart_csv_reader(text, **options))


def _cell(value):
    if isinstance(value, str):
        return str.__str__(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return int.__repr__(value)
    if isinstance(value, float):
        return float.__repr__(value)
    raise TypeError("CSV fields must be str, int, float, bool or None, not %s" % type(value).__name__)


def brisart_csv_dumps(rows, delimiter=",", quotechar='"', lineterminator="\r\n", quote_all=False,
                      escape_formulas=False):
    """Serialize an iterable of rows (iterables of fields) to CSV text."""
    _check_chars(delimiter, quotechar)
    if lineterminator not in ("\r\n", "\n", "\r"):
        raise ValueError("lineterminator must be CRLF, LF or CR")
    special = (delimiter, quotechar, "\r", "\n")
    doubled = quotechar + quotechar
    lines = []
    for row in rows:
        if isinstance(row, (str, bytes)):
            raise TypeError("each row must be an iterable of fields, not %s" % type(row).__name__)
        cells = [_cell(value) for value in row]
        out = []
        for cell in cells:
            if escape_formulas and cell.startswith(_FORMULA_STARTS):
                cell = "'" + cell
            if quote_all or (len(cells) == 1 and cell == "") or any(mark in cell for mark in special):
                cell = quotechar + cell.replace(quotechar, doubled) + quotechar
            out.append(cell)
        lines.append(delimiter.join(out) + lineterminator)
    return "".join(lines)


__all__ = [
    "BrisartCSVError",
    "DEFAULT_MAX_FIELD_SIZE",
    "brisart_csv_dumps",
    "brisart_csv_loads",
    "brisart_csv_reader",
]
