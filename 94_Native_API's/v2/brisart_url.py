"""
File: brisart_native/brisart_url.py

Purpose
-------
BrisartURL -- a from-spec, pure-Python URL toolkit (RFC 3986), replacing
urllib.parse's urlsplit / urlunsplit / quote / unquote / urlencode /
parse_qsl / urljoin in Brisart Research Archive tooling.

Public interface:
- brisart_urlsplit(url) -- Split into a BrisartSplitResult (scheme,
  netloc, path, query, fragment) with strict hostname and port helpers.
- brisart_urlunsplit(parts) -- Recompose; exact inverse of urlsplit.
- brisart_urljoin(base, url) -- RFC 3986 section 5 reference resolution.
- brisart_quote(text, safe="/", errors="strict") -- Percent-encode.
- brisart_unquote(text, errors="replace") -- Percent-decode.
- brisart_urlencode(query, doseq=False) -- Form-encode pairs or a dict.
- brisart_parse_qsl(query, keep_blank_values=False,
  max_num_fields=DEFAULT_MAX_QUERY_FIELDS) -- Parse a query string.
- BrisartSplitResult -- Result type with hostname, port, geturl().

Design notes:

A URL has to mean the same thing to every component that handles it: the
filter that decides whether it is allowed, the code that extracts its
host, and the client that finally fetches it. Disagreements between
those components are the root of server-side request forgery and open
redirect bugs, so this module refuses to guess where the standard
library or browsers would:

1. Leading and trailing C0 control characters and spaces are stripped
   and every tab, CR and LF is removed before parsing, as the WHATWG URL
   standard (browsers) does. "java\\nscript:alert(1)" therefore has the
   scheme "javascript", so a scheme filter sees what a browser will run.
2. A scheme is ASCII letters, digits, "+", "-" and "." starting with a
   letter, and is lower-cased with ASCII rules only. Unicode case
   folding is never used: the Kelvin sign U+212A lower-cases to "k" and
   the long s U+017F folds to "s", which would let a look-alike host
   match an allow-list.
3. hostname returns None, and port raises ValueError, whenever the
   authority is not a clean RFC 3986 authority: backslashes, spaces,
   control characters, "<", ">", quotes, percent escapes, repeated
   colons, unbalanced brackets. Browsers read "http://a.com\\\\@b.com/"
   as host a.com while a plain RFC parser reads host b.com; returning
   None forces the caller to reject the URL instead of picking one.
4. Dot-segment removal follows RFC 3986 section 5.2.4 exactly, including
   the trailing "/" that "." and ".." leave, and runs in linear time.
5. urljoin is the strict RFC 3986 algorithm: "http:g" stays "http:g"
   and the base fragment is dropped.
6. The split result remembers whether an authority, query and fragment
   were present, so urlunsplit(urlsplit(url)) reproduces the cleaned URL
   exactly (including "http:///x", "?" and "#").

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other brisart_native
modules (brisart_robots.py carries its own small path normaliser rather
than importing this one). Behaviour is cross-checked against
urllib.parse and the RFC 3986 section 5.4 reference table by
brisart_native/tests/test_url.py (tests may import the standard library;
this module may not).

Settings / parameters
---------------------
- DEFAULT_MAX_QUERY_FIELDS -- 1000. parse_qsl raises ValueError when a
  query has this many "&"-separated fields or more; pass
  max_num_fields=None to disable.
- safe -- quote only. ASCII characters left unescaped in addition to the
  RFC 3986 unreserved set; "/" by default.
- errors -- quote: "strict" (default) or "replace" for characters that
  cannot be encoded as UTF-8; unquote: "replace" (default) or "strict"
  for percent-escaped bytes that are not valid UTF-8.
- doseq -- urlencode only. True expands list/tuple values into repeated
  keys.

Edge cases
----------
- None is treated as the empty URL; any other non-str raises TypeError.
- "%00" decodes to a real NUL character. Reject it before passing a
  decoded value to any C API, file system or logger.
- urlsplit never raises for a malformed authority; check
  `parts.netloc and parts.hostname is None` to detect one.
- A bracketed IPv6 literal returns the text inside the brackets,
  lower-cased; it is not validated beyond allowed characters.
- Non-ASCII hostnames are returned lower-cased for ASCII letters only.
  No IDNA or punycode processing is done; do not treat a non-ASCII host
  as equal to, or safe in place of, an ASCII one.
- An empty query or fragment ("?" or "#") is preserved by urlsplit and
  urlunsplit; urljoin treats "?" as a query that replaces the base's.
- urljoin with an empty base returns a purely relative reference
  unchanged, but still resolves dot segments in a reference that has a
  scheme or authority, so an absolute URL is normalised identically
  whatever base it is joined with.
- urlunsplit keeps its output re-parseable: a scheme-less, authority-less
  path whose first segment looks like a scheme gets a "./" prefix
  (RFC 3986 section 4.2), a path beginning "//" gets "/.", and leading or
  trailing control characters and spaces are percent-encoded because
  parsing would strip them.

Known limitations
-----------------
- Not a full WHATWG parser: backslashes are not converted to slashes,
  special-scheme default ports are not elided and hosts are not
  normalised. The aim is a strict, predictable RFC 3986 parser that
  refuses ambiguous input.
- No IDNA/punycode, no percent-encoding normalisation of URLs (only
  quote/unquote), no IPv6 or IPv4 address validation.
- unquote of a very long string builds the result in memory; callers
  should limit input length.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_url import (
        brisart_urlsplit, brisart_urljoin, brisart_quote)
    parts = brisart_urlsplit("HTTPS://Example.COM:8080/a/b?x=1#frag")
    assert (parts.scheme, parts.hostname, parts.port) == ("https", "example.com", 8080)
    assert parts.geturl() == "https://Example.COM:8080/a/b?x=1#frag"
    assert brisart_urlsplit("java\\tscript:alert(1)").scheme == "javascript"
    assert brisart_urlsplit("http://good.com\\\\@evil.com/").hostname is None
    assert brisart_urljoin("http://a/b/c/d;p?q", "../g") == "http://a/b/g"
    assert brisart_quote("a b/c") == "a%20b/c"
"""

DEFAULT_MAX_QUERY_FIELDS = 1000

_ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"
_UNRESERVED = _ALPHA + _DIGITS + "-._~"
_SUB_DELIMS = "!$&'()*+,;="
_SCHEME_FIRST = frozenset(_ALPHA)
_SCHEME_REST = frozenset(_ALPHA + _DIGITS + "+-.")
_HEX = frozenset("0123456789ABCDEFabcdef")
_HOST_ASCII_OK = frozenset(_UNRESERVED + _SUB_DELIMS)
_IPV6_OK = frozenset("0123456789abcdefABCDEF:.")
_USERINFO_ASCII_OK = frozenset(_UNRESERVED + _SUB_DELIMS + ":%")
_C0_AND_SPACE = "".join(chr(i) for i in range(33))
_DROP_TAB_CR_LF = {9: None, 10: None, 13: None}
_ASCII_LOWER = {c: c + 32 for c in range(65, 91)}

_QUOTE_TABLES = {}


def _ascii_lower(text):
    return text.translate(_ASCII_LOWER)


def _text(url):
    if url is None:
        return ""
    if not isinstance(url, str):
        raise TypeError("URL must be str, not %s" % type(url).__name__)
    return url


def _clean(url):
    return _text(url).strip(_C0_AND_SPACE).translate(_DROP_TAB_CR_LF)


class BrisartSplitResult:
    """The five URL components plus markers for which delimiters were present."""

    __slots__ = ("scheme", "netloc", "path", "query", "fragment", "has_authority", "has_query", "has_fragment")

    def __init__(self, scheme, netloc, path, query, fragment, has_authority=None, has_query=None, has_fragment=None):
        self.scheme = scheme
        self.netloc = netloc
        self.path = path
        self.query = query
        self.fragment = fragment
        self.has_authority = bool(netloc) if has_authority is None else bool(has_authority) or bool(netloc)
        self.has_query = bool(query) if has_query is None else bool(has_query) or bool(query)
        self.has_fragment = bool(fragment) if has_fragment is None else bool(has_fragment) or bool(fragment)

    def _key(self):
        return (self.scheme, self.netloc, self.path, self.query, self.fragment,
                self.has_authority, self.has_query, self.has_fragment)

    def __iter__(self):
        return iter((self.scheme, self.netloc, self.path, self.query, self.fragment))

    def __eq__(self, other):
        if isinstance(other, BrisartSplitResult):
            return self._key() == other._key()
        return NotImplemented

    def __hash__(self):
        return hash(self._key())

    def __repr__(self):
        return ("BrisartSplitResult(scheme=%r, netloc=%r, path=%r, query=%r, fragment=%r)"
                % (self.scheme, self.netloc, self.path, self.query, self.fragment))

    def _authority_parts(self):
        """Return (host, port_text) for a clean authority, or None when it is not clean."""
        netloc = self.netloc
        if not netloc:
            return None
        userinfo, at_sign, hostport = netloc.rpartition("@")
        if at_sign:
            if "@" in userinfo:
                return None                      # "a@b@c": browsers and RFC parsers split this differently
            for char in userinfo:
                if char < "\x80" and char not in _USERINFO_ASCII_OK:
                    return None                  # a backslash here is what "http://a.com\\@evil.com" hides behind
        if hostport.startswith("["):
            end = hostport.find("]")
            if end == -1:
                return None
            host, rest = hostport[1:end], hostport[end + 1:]
            if not host or not _IPV6_OK.issuperset(host) or (rest and not rest.startswith(":")):
                return None
            return _ascii_lower(host), rest[1:]
        host, colon, port = hostport.partition(":")
        if ":" in port or not host:
            return None
        for char in host:
            if char < "\x80" and char not in _HOST_ASCII_OK:
                return None                  # controls, spaces, backslash, quotes, "<", ">", "%", "[", "]", "@", ...
        return _ascii_lower(host), port

    @property
    def hostname(self):
        """Lower-cased host, or None when absent or when the authority is ambiguous."""
        parts = self._authority_parts()
        return None if parts is None else parts[0]

    @property
    def port(self):
        """Port as an int, None when absent; ValueError when invalid or the authority is ambiguous."""
        if not self.netloc:
            return None
        parts = self._authority_parts()
        if parts is None:
            raise ValueError("authority is not a clean RFC 3986 authority")
        text = parts[1]
        if not text:
            return None
        if not (text.isascii() and text.isdigit()):
            raise ValueError("port is not a decimal number")
        number = int(text)
        if number > 65535:
            raise ValueError("port out of range 0-65535")
        return number

    def geturl(self):
        return brisart_urlunsplit(self)


def brisart_urlsplit(url):
    """Split a URL into scheme, netloc, path, query and fragment (RFC 3986 appendix B)."""
    rest = _clean(url)
    fragment = ""
    has_fragment = False
    hash_at = rest.find("#")
    if hash_at != -1:
        rest, fragment, has_fragment = rest[:hash_at], rest[hash_at + 1:], True
    scheme = ""
    colon = rest.find(":")
    if colon > 0 and rest[0] in _SCHEME_FIRST and _SCHEME_REST.issuperset(rest[:colon]):
        scheme = _ascii_lower(rest[:colon])
        rest = rest[colon + 1:]
    netloc = ""
    has_authority = False
    if rest.startswith("//"):
        has_authority = True
        end = len(rest)
        for mark in ("/", "?"):
            found = rest.find(mark, 2)
            if found != -1 and found < end:
                end = found
        netloc, rest = rest[2:end], rest[end:]
    query = ""
    has_query = False
    question = rest.find("?")
    if question != -1:
        rest, query, has_query = rest[:question], rest[question + 1:], True
    return BrisartSplitResult(scheme, netloc, rest, query, fragment, has_authority, has_query, has_fragment)


def brisart_urlunsplit(parts):
    """Recompose the five components (a BrisartSplitResult or a 5-sequence) into a URL string."""
    if isinstance(parts, BrisartSplitResult):
        scheme, netloc, path, query, fragment = parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment
        has_authority, has_query, has_fragment = parts.has_authority, parts.has_query, parts.has_fragment
    elif hasattr(parts, "scheme") and hasattr(parts, "fragment"):
        scheme, netloc, path, query, fragment = parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment
        has_authority, has_query, has_fragment = bool(netloc), bool(query), bool(fragment)
    else:
        scheme, netloc, path, query, fragment = parts
        has_authority, has_query, has_fragment = bool(netloc), bool(query), bool(fragment)
    out = []
    if scheme:
        out.append(scheme + ":")
    if has_authority:
        out.append("//" + netloc)
        if path and not path.startswith("/"):
            out.append("/")
    elif path.startswith("//"):
        out.append("/.")                        # keep "//x" from being re-read as an authority
    elif not scheme and _first_segment_reads_as_scheme(path):
        out.append("./")                        # RFC 3986 section 4.2: "b:c" would be re-read as a scheme
    out.append(path)
    if has_query:
        out.append("?" + query)
    if has_fragment:
        out.append("#" + fragment)
    return _protect_edges("".join(out))


def _first_segment_reads_as_scheme(path):
    colon = path.find(":")
    if colon < 1:
        return False
    slash = path.find("/")
    if slash != -1 and slash < colon:
        return False
    return path[0] in _SCHEME_FIRST and _SCHEME_REST.issuperset(path[:colon])


def _protect_edges(url):
    """Percent-encode leading/trailing control characters and spaces, which parsing would strip."""
    if url and (url[0] <= " " or url[-1] <= " "):
        start = 0
        while start < len(url) and url[start] <= " ":
            start += 1
        end = len(url)
        while end > start and url[end - 1] <= " ":
            end -= 1
        url = "".join("%%%02X" % ord(c) for c in url[:start]) + url[start:end] + \
            "".join("%%%02X" % ord(c) for c in url[end:])
    return url


def _quote_table(safe):
    table = _QUOTE_TABLES.get(safe)
    if table is None:
        keep = set(_UNRESERVED) | set(safe)
        table = ["%%%02X" % b if (b > 127 or chr(b) not in keep) else chr(b) for b in range(256)]
        if len(_QUOTE_TABLES) >= 32:
            _QUOTE_TABLES.clear()
        _QUOTE_TABLES[safe] = table
    return table


def brisart_quote(text, safe="/", errors="strict"):
    """Percent-encode str or bytes (RFC 3986), leaving unreserved characters and `safe` as they are."""
    if isinstance(safe, bytes):
        safe = safe.decode("ascii")
    if not isinstance(safe, str) or not safe.isascii():
        raise ValueError("safe must be ASCII")
    if errors not in ("strict", "replace"):
        raise ValueError("errors must be 'strict' or 'replace'")
    if isinstance(text, str):
        if not text:
            return text
        if not text.strip(_UNRESERVED + safe):
            return text                          # nothing to escape
        raw = text.encode("utf-8", errors)
    elif isinstance(text, (bytes, bytearray)):
        raw = bytes(text)
    else:
        raise TypeError("quote() requires str or bytes, not %s" % type(text).__name__)
    table = _quote_table(safe)
    return "".join([table[b] for b in raw])


def brisart_unquote(text, errors="replace"):
    """Reverse percent-encoding. A '%' not followed by two hex digits is kept literally."""
    if not isinstance(text, str):
        raise TypeError("unquote() requires str, not %s" % type(text).__name__)
    if errors not in ("strict", "replace"):
        raise ValueError("errors must be 'strict' or 'replace'")
    if "%" not in text:
        return text
    segments = text.split("%")
    out = [segments[0]]
    pending = bytearray()
    for segment in segments[1:]:
        if len(segment) >= 2 and segment[0] in _HEX and segment[1] in _HEX:
            pending.append(int(segment[:2], 16))
            tail = segment[2:]
            if tail:
                out.append(pending.decode("utf-8", errors))
                pending = bytearray()
                out.append(tail)
        else:
            if pending:
                out.append(pending.decode("utf-8", errors))
                pending = bytearray()
            out.append("%" + segment)
    if pending:
        out.append(pending.decode("utf-8", errors))
    return "".join(out)


def _quote_plus(value):
    if isinstance(value, (bytes, bytearray)):
        encoded = brisart_quote(bytes(value), safe="")
    else:
        encoded = brisart_quote(value if isinstance(value, str) else str(value), safe="")
    return encoded.replace("%20", "+")


def brisart_urlencode(query, doseq=False):
    """Encode a mapping or an iterable of (key, value) pairs as application/x-www-form-urlencoded."""
    pairs = query.items() if hasattr(query, "items") else query
    segments = []
    for key, value in pairs:
        name = _quote_plus(key)
        if doseq and isinstance(value, (list, tuple)):
            for item in value:
                segments.append(name + "=" + _quote_plus(item))
        else:
            segments.append(name + "=" + _quote_plus(value))
    return "&".join(segments)


def brisart_parse_qsl(query, keep_blank_values=False, max_num_fields=DEFAULT_MAX_QUERY_FIELDS):
    """Parse a query string into a list of (key, value) pairs; '&' is the only separator."""
    if not isinstance(query, str):
        raise TypeError("query must be str, not %s" % type(query).__name__)
    if max_num_fields is not None and query.count("&") >= max_num_fields:
        raise ValueError("Max number of fields exceeded")
    pairs = []
    if not query:
        return pairs
    for segment in query.split("&"):
        if not segment:
            continue
        name, equals, value = segment.partition("=")
        if not value and not keep_blank_values:
            continue
        pairs.append((brisart_unquote(name.replace("+", " ")), brisart_unquote(value.replace("+", " "))))
    return pairs


def _remove_dot_segments(path):
    """RFC 3986 section 5.2.4, in linear time (no repeated slicing of the remaining input)."""
    output = []
    i = 0
    n = len(path)
    while i < n:
        if path.startswith("../", i):
            i += 3
        elif path.startswith("./", i):
            i += 2
        elif path.startswith("/./", i):
            i += 2
        elif path.startswith("/.", i) and i + 2 == n:
            output.append("/")
            i = n
        elif path.startswith("/../", i):
            i += 3
            if output:
                output.pop()
        elif path.startswith("/..", i) and i + 3 == n:
            if output:
                output.pop()
            output.append("/")
            i = n
        elif path.startswith(".", i) and (i + 1 == n or (i + 2 == n and path[i + 1] == ".")):
            i = n
        else:
            end = path.find("/", i + 1 if path[i] == "/" else i)
            if end == -1:
                end = n
            output.append(path[i:end])
            i = end
    return "".join(output)


def brisart_urljoin(base, url):
    """Resolve `url` against `base` with the strict RFC 3986 section 5.2 algorithm."""
    base, url = _clean(base), _clean(url)
    ref = brisart_urlsplit(url)
    if not base and not ref.scheme and not ref.has_authority:
        return url                              # a relative reference cannot be resolved against nothing
    origin = brisart_urlsplit(base)
    if ref.scheme:
        scheme, has_authority, netloc = ref.scheme, ref.has_authority, ref.netloc
        path, has_query, query = _remove_dot_segments(ref.path), ref.has_query, ref.query
    else:
        scheme = origin.scheme
        if ref.has_authority:
            has_authority, netloc = True, ref.netloc
            path, has_query, query = _remove_dot_segments(ref.path), ref.has_query, ref.query
        else:
            has_authority, netloc = origin.has_authority, origin.netloc
            if not ref.path:
                path = _remove_dot_segments(origin.path)
                if ref.has_query:
                    has_query, query = True, ref.query
                else:
                    has_query, query = origin.has_query, origin.query
            else:
                if ref.path.startswith("/"):
                    path = _remove_dot_segments(ref.path)
                else:
                    if origin.has_authority and not origin.path:
                        merged = "/" + ref.path
                    else:
                        merged = origin.path[:origin.path.rfind("/") + 1] + ref.path
                    path = _remove_dot_segments(merged)
                has_query, query = ref.has_query, ref.query
    return brisart_urlunsplit(BrisartSplitResult(scheme, netloc, path, query, ref.fragment,
                                                 has_authority, has_query, ref.has_fragment))


__all__ = [
    "BrisartSplitResult",
    "DEFAULT_MAX_QUERY_FIELDS",
    "brisart_parse_qsl",
    "brisart_quote",
    "brisart_unquote",
    "brisart_urlencode",
    "brisart_urljoin",
    "brisart_urlsplit",
    "brisart_urlunsplit",
]
