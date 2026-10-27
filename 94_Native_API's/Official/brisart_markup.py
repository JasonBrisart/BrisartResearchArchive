"""
File: v2/brisart_markup.py

Purpose
-------
BrisartMarkup -- a from-scratch, pure-Python HTML tokenizer and
character-reference decoder following the HTML Living Standard's
tokenization rules, replacing html.parser.HTMLParser and html.unescape
in Brisart Research Archive tooling (link extraction, text extraction,
scraping).

Public interface:
- BrisartMarkupParser(convert_charrefs=True) -- Subclass and override
  handle_starttag, handle_endtag, handle_startendtag, handle_data,
  handle_comment and handle_decl; call feed(text) any number of times,
  then close(). reset() makes the object reusable.
- brisart_unescape(text, *, attribute=False) -- Decode character
  references in text or (attribute=True) in an attribute value.

Design notes:

This is a tokenizer, not a tree builder: it reports what a browser's
tokenizer would see and does no implied-tag, nesting or foreign-content
repair. Where html.parser disagrees with browsers, this module follows
the browsers, because a link or text extractor that sees a different
document than the browser does can be tricked (the same class of bug as
parser-differential attacks on sanitizers and URL filters):

1. Tags are scanned with quote awareness: ">" inside a quoted attribute
   value does not end the tag, and an attribute value is never cut at the
   first ">" the way a naive find() would.
2. Tag and attribute names are lower-cased with ASCII rules only, and
   only space, tab, LF, FF and CR separate attributes (not NBSP or other
   Unicode whitespace). The old tokenizer used casefold(), under which
   the long s U+017F matched "s", so "</\\u017fcript>" closed a script
   element that no browser would close.
3. If an attribute name repeats, the first occurrence wins and later ones
   are dropped, as in browsers. (Keeping all of them lets
   dict(attrs) disagree with the browser about href.)
4. <script>, <style>, <xmp>, <iframe>, <noembed> and <noframes> content
   is opaque text, and <textarea> and <title> content is text with
   character references decoded but no tags; each ends only at a matching
   end tag followed by whitespace, "/" or ">". <plaintext> makes the rest
   of the input text. Character references are never decoded inside
   script or style, and are always decoded in text, <textarea> and
   <title>.
5. Attribute values follow the spec's attribute rule: a named reference
   with no semicolon is not decoded when the next character is "=" or
   alphanumeric, so href="?a=1&copy=2" keeps "&copy=2" instead of
   becoming "\\u00a9=2" as html.parser makes it. The full 2,231-name
   entity table is included, so "java&Tab;script:" decodes the same way
   everywhere.
6. Comments end at "-->" or "--!>"; "<!-->" and "<!--->" are empty
   comments; "<!", "<?" and "</" followed by a non-letter start bogus
   comments that end at the next ">". A tag, comment or declaration cut
   off by the end of input is handled as the standard says (a cut-off tag
   is dropped, a cut-off comment is reported).
7. Everything is designed to run in linear time, and the tests check
   linear growth on adversarial shapes. Input is indexed rather than repeatedly
   sliced, buffered text is joined once, incomplete constructs are
   re-scanned only after the buffer has doubled, and an end-of-comment
   search is cached, so no input (many tiny feed() calls, an endless
   attribute, thousands of unterminated comments) can cause quadratic
   work. Numeric references with thousands of digits are bounded (html
   .unescape raises ValueError on them).

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing (the regular
expression module included), so it can be copied into any tool on its
own. It does not depend on the other brisart_native modules. The entity
data at the bottom was generated from CPython's html.entities.html5
(2,125 names that end in a semicolon and 106 legacy names without one)
and the numeric-reference tables from html._invalid_charrefs and
html._invalid_codepoints. Behaviour is cross-checked against
html.unescape for every named entity and every code point, and against
html.parser on well-formed documents, by
brisart_native/tests/test_markup.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- convert_charrefs -- True (default) decodes character references in
  text and attribute values; False reports them raw. There are no
  handle_charref / handle_entityref callbacks.
- attribute -- brisart_unescape only. True applies the attribute-value
  rule for semicolon-less named references (see Design notes 5).
- _ENTITY_DATA, _LEGACY_NAMES, _INVALID_CHARREFS, _INVALID_CODEPOINTS --
  Generated data tables at the bottom of the file; not tunable.

Edge cases
----------
- Text between markup is delivered in as few handle_data calls as
  possible (normally one per text node), independent of how the input
  was split across feed() calls.
- A valueless attribute reports None; an empty one reports "". NUL
  characters in names and values become U+FFFD.
- "<br/>" and "<a/>" call handle_startendtag; "<br/ >" does not (the
  stray "/" is ignored), matching the standard. "<script/>" still starts
  script content, as in browsers.
- "</>" produces nothing; "</ x>" is a comment; "<" followed by anything
  but a letter, "!", "?" or "/" is literal text.
- Numeric references follow html.unescape: 0 becomes U+FFFD, 0x80-0x9F
  map through Windows-1252, surrogates and values above 0x10FFFF become
  U+FFFD, and noncharacters and most control characters are dropped.
- close() resolves anything left over; feed() after close() starts a new
  document only after reset().

Known limitations
-----------------
- Tokenizer only: no tree construction, no implied end tags, no foreign
  content (SVG/MathML), no CDATA sections (they are bogus comments, as in
  HTML), no script-data "escaped" states (a "<!--" inside script does not
  change where the script ends, which browsers treat specially), no
  <noscript> mode and no encoding sniffing (input is str).
- Do not use the token stream as a security sanitizer: a sanitizer must
  parse exactly as the target browser does, including tree building.
- Measured on CPython 3.12: about 2-3 MB/s, roughly 1.2-1.4 times the
  speed of html.parser on the same documents.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_markup import (
        BrisartMarkupParser, brisart_unescape)

    class Links(BrisartMarkupParser):
        def __init__(self):
            BrisartMarkupParser.__init__(self)
            self.hrefs = []
        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.hrefs.append(dict(attrs).get("href"))

    parser = Links()
    parser.feed('<a href="?a=1&copy=2&amp;b=3">x</a><script>&amp;</script>')
    parser.close()
    assert parser.hrefs == ["?a=1&copy=2&b=3"]
    assert brisart_unescape("&lt;b&gt; &#65;&#x42;") == "<b> AB"
    assert brisart_unescape("&copy=1", attribute=True) == "&copy=1"
"""

_WS = " \t\n\f\r"
_TAG_NAME_END = frozenset(" \t\n\f\r/>")
_ATTR_NAME_END = frozenset(" \t\n\f\r/>=")
_UNQUOTED_END = frozenset(" \t\n\f\r>")
_ALPHA = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
_ALNUM = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
_DEC = frozenset("0123456789")
_HEX = frozenset("0123456789abcdefABCDEF")
_ASCII_LOWER = {c: c + 32 for c in range(65, 91)}
_RAWTEXT = frozenset(("script", "style", "xmp", "iframe", "noembed", "noframes"))
_RCDATA = frozenset(("textarea", "title"))
_LEGACY_MAX = 6
_NAME_MAX = 32
_NUMERIC_MAX_DIGITS = 8                      # after stripping leading zeros; longer is certainly > 0x10FFFF


def _numeric_character(code):
    if code in _INVALID_CHARREFS:
        return _INVALID_CHARREFS[code]
    if 0xD800 <= code <= 0xDFFF or code > 0x10FFFF:
        return "\ufffd"
    if code in _INVALID_CODEPOINTS:
        return ""
    return chr(code)


def brisart_unescape(text, *, attribute=False):
    """Decode HTML character references in `text` (or, with attribute=True, in an attribute value)."""
    if not isinstance(text, str):
        raise TypeError("text must be str, not %s" % type(text).__name__)
    if "&" not in text:
        return text
    out = []
    length = len(text)
    i = 0
    while True:
        amp = text.find("&", i)
        if amp == -1:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:amp])
        start = amp + 1
        i = start
        if start < length and text[start] == "#":
            end = start + 1
            hexadecimal = end < length and text[end] in "xX"
            if hexadecimal:
                end += 1
            first = end
            digits = _HEX if hexadecimal else _DEC
            while end < length and text[end] in digits:
                end += 1
            if end == first:
                out.append("&")
                continue
            significant = text[first:end].lstrip("0") or "0"
            if len(significant) > _NUMERIC_MAX_DIGITS:
                code = 0x110000
            else:
                code = int(significant, 16 if hexadecimal else 10)
            if end < length and text[end] == ";":
                end += 1
            out.append(_numeric_character(code))
            i = end
            continue
        end = start
        limit = min(length, start + _NAME_MAX)
        while end < limit and text[end] in _ALNUM:
            end += 1
        name = text[start:end]
        if not name:
            out.append("&")
            continue
        if end < length and text[end] == ";" and name in _ENTITIES:
            out.append(_ENTITIES[name])
            i = end + 1
            continue
        decoded = False
        for size in range(min(len(name), _LEGACY_MAX), 1, -1):
            if name[:size] in _LEGACY:               # the longest legacy name decides, decoded or not
                following = text[start + size] if start + size < length else ""
                if not (attribute and (following == "=" or following in _ALNUM)):
                    out.append(_ENTITIES[name[:size]])
                    i = start + size
                    decoded = True
                break
        if not decoded:
            out.append("&")


class BrisartMarkupParser:
    """HTML tokenizer: feed() text, receive handle_*() callbacks, close() when the input ends."""

    def __init__(self, convert_charrefs=True):
        self._convert = bool(convert_charrefs)
        self.reset()

    def reset(self):
        """Discard all state so the parser can read a new document."""
        self._pending = []              # input chunks not yet merged into _buffer
        self._pending_length = 0
        self._buffer = ""               # unconsumed input
        self._mode = None               # None, "plaintext", or the name of the open raw-text element
        self._retry_at = 0              # do not re-scan an incomplete construct until this much input is held
        self._text = []                 # text of the current text node, decoded when the node ends
        self._bang_at = -2              # cached position of the next "--!>" in the buffer (-2: unknown)

    # ------------------------------------------------------------------ public input
    def feed(self, chunk):
        """Add more input. Callbacks fire for every construct that is now complete."""
        if not isinstance(chunk, str):
            raise TypeError("feed() requires str, not %s" % type(chunk).__name__)
        if not chunk:
            return
        self._pending.append(chunk)
        self._pending_length += len(chunk)
        if len(self._buffer) + self._pending_length >= self._retry_at:
            self._consume(False)

    def close(self):
        """Signal the end of input and flush everything still held."""
        self._consume(True)
        self._flush_text()

    # ------------------------------------------------------------------ callbacks to override
    def handle_starttag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        pass

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        pass

    def handle_comment(self, data):
        pass

    def handle_decl(self, decl):
        pass

    # ------------------------------------------------------------------ text handling
    def _flush_text(self):
        if self._text:
            text = "".join(self._text)
            self._text = []
            if self._convert:
                text = brisart_unescape(text)
            if text:
                self.handle_data(text)

    def _emit_content(self, text, decode):
        self._flush_text()
        if text:
            self.handle_data(brisart_unescape(text) if (decode and self._convert) else text)

    # ------------------------------------------------------------------ main loop
    def _consume(self, final):
        buf = self._buffer
        if self._pending:
            buf = buf + "".join(self._pending) if buf else "".join(self._pending)
            self._pending = []
            self._pending_length = 0
        n = len(buf)
        self._bang_at = -2
        i = 0
        stuck = False
        while i < n:
            mode = self._mode
            if mode is None:
                lt = buf.find("<", i)
                if lt == -1:
                    self._text.append(buf[i:])
                    i = n
                    break
                if lt > i:
                    self._text.append(buf[i:lt])
                    i = lt
                step = self._markup(buf, i, n, final)
                if step < 0:
                    stuck = True
                    break
                i = step
            elif mode == "plaintext":
                self._emit_content(buf[i:], False)
                i = n
            else:
                close = self._find_end_tag(buf, i, n, mode)
                if close == -1:
                    if final:
                        self._emit_content(buf[i:], mode in _RCDATA)
                        i = n
                    else:
                        stuck = True
                    break
                self._emit_content(buf[i:close], mode in _RCDATA)
                self._mode = None
                i = close
        self._buffer = buf[i:]
        self._retry_at = 2 * len(self._buffer) if stuck else 0

    def _find_end_tag(self, buf, pos, n, name):
        size = len(name)
        while True:
            at = buf.find("</", pos, n)
            if at == -1:
                return -1
            after = at + 2 + size
            if buf[at + 2:after].translate(_ASCII_LOWER) == name and after < n and buf[after] in " \t\n\f\r/>":
                return at
            pos = at + 2

    # ------------------------------------------------------------------ markup
    def _markup(self, buf, i, n, final):
        """Handle the construct starting at buf[i] == '<'. Return the next index, or -1 if more input is needed."""
        if i + 1 >= n:
            if final:
                self._text.append("<")
                return n
            return -1
        char = buf[i + 1]
        if char in _ALPHA:
            return self._tag(buf, i, i + 1, n, final, False)
        if char == "!":
            return self._declaration(buf, i, n, final)
        if char == "?":
            return self._bogus_comment(buf, i + 1, n, final)
        if char == "/":
            if i + 2 >= n:
                if final:
                    self._text.append("</")
                    return n
                return -1
            after = buf[i + 2]
            if after in _ALPHA:
                return self._tag(buf, i, i + 2, n, final, True)
            if after == ">":
                return i + 3
            return self._bogus_comment(buf, i + 2, n, final)
        self._text.append("<")
        return i + 1

    def _bogus_comment(self, buf, start, n, final):
        end = buf.find(">", start)
        if end == -1:
            if not final:
                return -1
            self._flush_text()
            self.handle_comment(buf[start:])
            return n
        self._flush_text()
        self.handle_comment(buf[start:end])
        return end + 1

    def _declaration(self, buf, i, n, final):
        if buf.startswith("<!--", i):
            return self._comment(buf, i + 4, n, final)
        lowered = buf[i:i + 9].translate(_ASCII_LOWER)
        if lowered == "<!doctype":
            end = buf.find(">", i + 9)
            if end == -1:
                if not final:
                    return -1
                self._flush_text()
                self.handle_decl(buf[i + 2:])
                return n
            self._flush_text()
            self.handle_decl(buf[i + 2:end])
            return end + 1
        if buf.startswith("<![CDATA[", i):
            return self._bogus_comment(buf, i + 2, n, final)
        if not final and n - i < 9 and ("<!doctype".startswith(lowered) or "<![cdata[".startswith(lowered)
                                        or "<!--".startswith(lowered)):
            return -1
        return self._bogus_comment(buf, i + 2, n, final)

    def _comment(self, buf, start, n, final):
        if buf.startswith(">", start):
            self._flush_text()
            self.handle_comment("")
            return start + 1
        if buf.startswith("->", start):
            self._flush_text()
            self.handle_comment("")
            return start + 2
        dash = buf.find("-->", start)
        if self._bang_at == -2 or (self._bang_at != -1 and self._bang_at < start):
            self._bang_at = buf.find("--!>", start)
        bang = self._bang_at
        if dash == -1 and bang == -1:
            if not final:
                return -1
            self._flush_text()
            self.handle_comment(buf[start:])
            return n
        if bang == -1 or (dash != -1 and dash < bang):
            end, after = dash, dash + 3
        else:
            end, after = bang, bang + 4
        self._flush_text()
        self.handle_comment(buf[start:end])
        return after

    def _tag(self, buf, i, name_at, n, final, is_end):
        scanned = self._scan_tag(buf, name_at, n)
        if scanned is None:
            return n if final else -1           # a tag cut off by the end of input is dropped
        name, attrs, self_closing, end = scanned
        self._flush_text()
        if is_end:
            self.handle_endtag(name)
            return end
        if self_closing:
            self.handle_startendtag(name, attrs)
        else:
            self.handle_starttag(name, attrs)
        if name in _RAWTEXT or name in _RCDATA:
            self._mode = name
        elif name == "plaintext":
            self._mode = "plaintext"
        return end

    def _scan_tag(self, buf, pos, n):
        """Scan a tag name and its attributes; return (name, attrs, self_closing, end) or None if incomplete."""
        start = pos
        while pos < n and buf[pos] not in _TAG_NAME_END:
            pos += 1
        if pos >= n:
            return None
        name = buf[start:pos].translate(_ASCII_LOWER)
        if "\x00" in name:
            name = name.replace("\x00", "\ufffd")
        attrs = []
        seen = set()
        while True:
            while pos < n and buf[pos] in _WS:
                pos += 1
            if pos >= n:
                return None
            char = buf[pos]
            if char == ">":
                return name, attrs, False, pos + 1
            if char == "/":
                pos += 1
                if pos >= n:
                    return None
                if buf[pos] == ">":
                    return name, attrs, True, pos + 1
                continue
            start = pos
            pos += 1                                  # the first character is always part of the name, even "="
            while pos < n and buf[pos] not in _ATTR_NAME_END:
                pos += 1
            if pos >= n:
                return None
            attr = buf[start:pos].translate(_ASCII_LOWER)
            while pos < n and buf[pos] in _WS:
                pos += 1
            if pos >= n:
                return None
            value = None
            if buf[pos] == "=":
                pos += 1
                while pos < n and buf[pos] in _WS:
                    pos += 1
                if pos >= n:
                    return None
                quote = buf[pos]
                if quote == '"' or quote == "'":
                    close = buf.find(quote, pos + 1, n)
                    if close == -1:
                        return None
                    value = buf[pos + 1:close]
                    pos = close + 1
                elif quote == ">":
                    value = ""
                else:
                    start = pos
                    while pos < n and buf[pos] not in _UNQUOTED_END:
                        pos += 1
                    if pos >= n:
                        return None
                    value = buf[start:pos]
            if attr not in seen:
                seen.add(attr)
                if "\x00" in attr:
                    attr = attr.replace("\x00", "\ufffd")
                if value is not None:
                    if "\x00" in value:
                        value = value.replace("\x00", "\ufffd")
                    if self._convert:
                        value = brisart_unescape(value, attribute=True)
                attrs.append((attr, value))


# --------------------------------------------------------------------------- generated data
_ENTITY_DATA = (
    'AElig=\xc6\x00AMP=&\x00Aacute=\xc1\x00Abreve=\u0102\x00Acirc=\xc2\x00Acy=\u0410\x00Afr=\U0001d504\x00'
    'Agrave=\xc0\x00Alpha=\u0391\x00Amacr=\u0100\x00And=\u2a53\x00Aogon=\u0104\x00Aopf=\U0001d538\x00ApplyFunction=\u2061\x00'
    'Aring=\xc5\x00Ascr=\U0001d49c\x00Assign=\u2254\x00Atilde=\xc3\x00Auml=\xc4\x00Backslash=\u2216\x00Barv=\u2ae7\x00'
    'Barwed=\u2306\x00Bcy=\u0411\x00Because=\u2235\x00Bernoullis=\u212c\x00Beta=\u0392\x00Bfr=\U0001d505\x00'
    'Bopf=\U0001d539\x00Breve=\u02d8\x00Bscr=\u212c\x00Bumpeq=\u224e\x00CHcy=\u0427\x00COPY=\xa9\x00Cacute=\u0106\x00'
    'Cap=\u22d2\x00CapitalDifferentialD=\u2145\x00Cayleys=\u212d\x00Ccaron=\u010c\x00Ccedil=\xc7\x00Ccirc=\u0108\x00'
    'Cconint=\u2230\x00Cdot=\u010a\x00Cedilla=\xb8\x00CenterDot=\xb7\x00Cfr=\u212d\x00Chi=\u03a7\x00CircleDot=\u2299\x00'
    'CircleMinus=\u2296\x00CirclePlus=\u2295\x00CircleTimes=\u2297\x00ClockwiseContourIntegral=\u2232\x00'
    'CloseCurlyDoubleQuote=\u201d\x00CloseCurlyQuote=\u2019\x00Colon=\u2237\x00Colone=\u2a74\x00Congruent=\u2261\x00'
    'Conint=\u222f\x00ContourIntegral=\u222e\x00Copf=\u2102\x00Coproduct=\u2210\x00CounterClockwiseContourIntegral=\u2233\x00'
    'Cross=\u2a2f\x00Cscr=\U0001d49e\x00Cup=\u22d3\x00CupCap=\u224d\x00DD=\u2145\x00DDotrahd=\u2911\x00DJcy=\u0402\x00'
    'DScy=\u0405\x00DZcy=\u040f\x00Dagger=\u2021\x00Darr=\u21a1\x00Dashv=\u2ae4\x00Dcaron=\u010e\x00Dcy=\u0414\x00'
    'Del=\u2207\x00Delta=\u0394\x00Dfr=\U0001d507\x00DiacriticalAcute=\xb4\x00DiacriticalDot=\u02d9\x00'
    'DiacriticalDoubleAcute=\u02dd\x00DiacriticalGrave=`\x00DiacriticalTilde=\u02dc\x00Diamond=\u22c4\x00'
    'DifferentialD=\u2146\x00Dopf=\U0001d53b\x00Dot=\xa8\x00DotDot=\u20dc\x00DotEqual=\u2250\x00DoubleContourIntegral=\u222f\x00'
    'DoubleDot=\xa8\x00DoubleDownArrow=\u21d3\x00DoubleLeftArrow=\u21d0\x00DoubleLeftRightArrow=\u21d4\x00'
    'DoubleLeftTee=\u2ae4\x00DoubleLongLeftArrow=\u27f8\x00DoubleLongLeftRightArrow=\u27fa\x00DoubleLongRightArrow=\u27f9\x00'
    'DoubleRightArrow=\u21d2\x00DoubleRightTee=\u22a8\x00DoubleUpArrow=\u21d1\x00DoubleUpDownArrow=\u21d5\x00'
    'DoubleVerticalBar=\u2225\x00DownArrow=\u2193\x00DownArrowBar=\u2913\x00DownArrowUpArrow=\u21f5\x00'
    'DownBreve=\u0311\x00DownLeftRightVector=\u2950\x00DownLeftTeeVector=\u295e\x00DownLeftVector=\u21bd\x00'
    'DownLeftVectorBar=\u2956\x00DownRightTeeVector=\u295f\x00DownRightVector=\u21c1\x00DownRightVectorBar=\u2957\x00'
    'DownTee=\u22a4\x00DownTeeArrow=\u21a7\x00Downarrow=\u21d3\x00Dscr=\U0001d49f\x00Dstrok=\u0110\x00'
    'ENG=\u014a\x00ETH=\xd0\x00Eacute=\xc9\x00Ecaron=\u011a\x00Ecirc=\xca\x00Ecy=\u042d\x00Edot=\u0116\x00'
    'Efr=\U0001d508\x00Egrave=\xc8\x00Element=\u2208\x00Emacr=\u0112\x00EmptySmallSquare=\u25fb\x00EmptyVerySmallSquare=\u25ab\x00'
    'Eogon=\u0118\x00Eopf=\U0001d53c\x00Epsilon=\u0395\x00Equal=\u2a75\x00EqualTilde=\u2242\x00Equilibrium=\u21cc\x00'
    'Escr=\u2130\x00Esim=\u2a73\x00Eta=\u0397\x00Euml=\xcb\x00Exists=\u2203\x00ExponentialE=\u2147\x00Fcy=\u0424\x00'
    'Ffr=\U0001d509\x00FilledSmallSquare=\u25fc\x00FilledVerySmallSquare=\u25aa\x00Fopf=\U0001d53d\x00'
    'ForAll=\u2200\x00Fouriertrf=\u2131\x00Fscr=\u2131\x00GJcy=\u0403\x00GT=>\x00Gamma=\u0393\x00Gammad=\u03dc\x00'
    'Gbreve=\u011e\x00Gcedil=\u0122\x00Gcirc=\u011c\x00Gcy=\u0413\x00Gdot=\u0120\x00Gfr=\U0001d50a\x00Gg=\u22d9\x00'
    'Gopf=\U0001d53e\x00GreaterEqual=\u2265\x00GreaterEqualLess=\u22db\x00GreaterFullEqual=\u2267\x00'
    'GreaterGreater=\u2aa2\x00GreaterLess=\u2277\x00GreaterSlantEqual=\u2a7e\x00GreaterTilde=\u2273\x00'
    'Gscr=\U0001d4a2\x00Gt=\u226b\x00HARDcy=\u042a\x00Hacek=\u02c7\x00Hat=^\x00Hcirc=\u0124\x00Hfr=\u210c\x00'
    'HilbertSpace=\u210b\x00Hopf=\u210d\x00HorizontalLine=\u2500\x00Hscr=\u210b\x00Hstrok=\u0126\x00HumpDownHump=\u224e\x00'
    'HumpEqual=\u224f\x00IEcy=\u0415\x00IJlig=\u0132\x00IOcy=\u0401\x00Iacute=\xcd\x00Icirc=\xce\x00Icy=\u0418\x00'
    'Idot=\u0130\x00Ifr=\u2111\x00Igrave=\xcc\x00Im=\u2111\x00Imacr=\u012a\x00ImaginaryI=\u2148\x00Implies=\u21d2\x00'
    'Int=\u222c\x00Integral=\u222b\x00Intersection=\u22c2\x00InvisibleComma=\u2063\x00InvisibleTimes=\u2062\x00'
    'Iogon=\u012e\x00Iopf=\U0001d540\x00Iota=\u0399\x00Iscr=\u2110\x00Itilde=\u0128\x00Iukcy=\u0406\x00Iuml=\xcf\x00'
    'Jcirc=\u0134\x00Jcy=\u0419\x00Jfr=\U0001d50d\x00Jopf=\U0001d541\x00Jscr=\U0001d4a5\x00Jsercy=\u0408\x00'
    'Jukcy=\u0404\x00KHcy=\u0425\x00KJcy=\u040c\x00Kappa=\u039a\x00Kcedil=\u0136\x00Kcy=\u041a\x00Kfr=\U0001d50e\x00'
    'Kopf=\U0001d542\x00Kscr=\U0001d4a6\x00LJcy=\u0409\x00LT=<\x00Lacute=\u0139\x00Lambda=\u039b\x00Lang=\u27ea\x00'
    'Laplacetrf=\u2112\x00Larr=\u219e\x00Lcaron=\u013d\x00Lcedil=\u013b\x00Lcy=\u041b\x00LeftAngleBracket=\u27e8\x00'
    'LeftArrow=\u2190\x00LeftArrowBar=\u21e4\x00LeftArrowRightArrow=\u21c6\x00LeftCeiling=\u2308\x00'
    'LeftDoubleBracket=\u27e6\x00LeftDownTeeVector=\u2961\x00LeftDownVector=\u21c3\x00LeftDownVectorBar=\u2959\x00'
    'LeftFloor=\u230a\x00LeftRightArrow=\u2194\x00LeftRightVector=\u294e\x00LeftTee=\u22a3\x00LeftTeeArrow=\u21a4\x00'
    'LeftTeeVector=\u295a\x00LeftTriangle=\u22b2\x00LeftTriangleBar=\u29cf\x00LeftTriangleEqual=\u22b4\x00'
    'LeftUpDownVector=\u2951\x00LeftUpTeeVector=\u2960\x00LeftUpVector=\u21bf\x00LeftUpVectorBar=\u2958\x00'
    'LeftVector=\u21bc\x00LeftVectorBar=\u2952\x00Leftarrow=\u21d0\x00Leftrightarrow=\u21d4\x00LessEqualGreater=\u22da\x00'
    'LessFullEqual=\u2266\x00LessGreater=\u2276\x00LessLess=\u2aa1\x00LessSlantEqual=\u2a7d\x00LessTilde=\u2272\x00'
    'Lfr=\U0001d50f\x00Ll=\u22d8\x00Lleftarrow=\u21da\x00Lmidot=\u013f\x00LongLeftArrow=\u27f5\x00LongLeftRightArrow=\u27f7\x00'
    'LongRightArrow=\u27f6\x00Longleftarrow=\u27f8\x00Longleftrightarrow=\u27fa\x00Longrightarrow=\u27f9\x00'
    'Lopf=\U0001d543\x00LowerLeftArrow=\u2199\x00LowerRightArrow=\u2198\x00Lscr=\u2112\x00Lsh=\u21b0\x00'
    'Lstrok=\u0141\x00Lt=\u226a\x00Map=\u2905\x00Mcy=\u041c\x00MediumSpace=\u205f\x00Mellintrf=\u2133\x00'
    'Mfr=\U0001d510\x00MinusPlus=\u2213\x00Mopf=\U0001d544\x00Mscr=\u2133\x00Mu=\u039c\x00NJcy=\u040a\x00'
    'Nacute=\u0143\x00Ncaron=\u0147\x00Ncedil=\u0145\x00Ncy=\u041d\x00NegativeMediumSpace=\u200b\x00NegativeThickSpace=\u200b\x00'
    'NegativeThinSpace=\u200b\x00NegativeVeryThinSpace=\u200b\x00NestedGreaterGreater=\u226b\x00NestedLessLess=\u226a\x00'
    'NewLine=\n\x00Nfr=\U0001d511\x00NoBreak=\u2060\x00NonBreakingSpace=\xa0\x00Nopf=\u2115\x00Not=\u2aec\x00'
    'NotCongruent=\u2262\x00NotCupCap=\u226d\x00NotDoubleVerticalBar=\u2226\x00NotElement=\u2209\x00'
    'NotEqual=\u2260\x00NotEqualTilde=\u2242\u0338\x00NotExists=\u2204\x00NotGreater=\u226f\x00NotGreaterEqual=\u2271\x00'
    'NotGreaterFullEqual=\u2267\u0338\x00NotGreaterGreater=\u226b\u0338\x00NotGreaterLess=\u2279\x00'
    'NotGreaterSlantEqual=\u2a7e\u0338\x00NotGreaterTilde=\u2275\x00NotHumpDownHump=\u224e\u0338\x00'
    'NotHumpEqual=\u224f\u0338\x00NotLeftTriangle=\u22ea\x00NotLeftTriangleBar=\u29cf\u0338\x00NotLeftTriangleEqual=\u22ec\x00'
    'NotLess=\u226e\x00NotLessEqual=\u2270\x00NotLessGreater=\u2278\x00NotLessLess=\u226a\u0338\x00NotLessSlantEqual=\u2a7d\u0338\x00'
    'NotLessTilde=\u2274\x00NotNestedGreaterGreater=\u2aa2\u0338\x00NotNestedLessLess=\u2aa1\u0338\x00'
    'NotPrecedes=\u2280\x00NotPrecedesEqual=\u2aaf\u0338\x00NotPrecedesSlantEqual=\u22e0\x00NotReverseElement=\u220c\x00'
    'NotRightTriangle=\u22eb\x00NotRightTriangleBar=\u29d0\u0338\x00NotRightTriangleEqual=\u22ed\x00'
    'NotSquareSubset=\u228f\u0338\x00NotSquareSubsetEqual=\u22e2\x00NotSquareSuperset=\u2290\u0338\x00'
    'NotSquareSupersetEqual=\u22e3\x00NotSubset=\u2282\u20d2\x00NotSubsetEqual=\u2288\x00NotSucceeds=\u2281\x00'
    'NotSucceedsEqual=\u2ab0\u0338\x00NotSucceedsSlantEqual=\u22e1\x00NotSucceedsTilde=\u227f\u0338\x00'
    'NotSuperset=\u2283\u20d2\x00NotSupersetEqual=\u2289\x00NotTilde=\u2241\x00NotTildeEqual=\u2244\x00'
    'NotTildeFullEqual=\u2247\x00NotTildeTilde=\u2249\x00NotVerticalBar=\u2224\x00Nscr=\U0001d4a9\x00'
    'Ntilde=\xd1\x00Nu=\u039d\x00OElig=\u0152\x00Oacute=\xd3\x00Ocirc=\xd4\x00Ocy=\u041e\x00Odblac=\u0150\x00'
    'Ofr=\U0001d512\x00Ograve=\xd2\x00Omacr=\u014c\x00Omega=\u03a9\x00Omicron=\u039f\x00Oopf=\U0001d546\x00'
    'OpenCurlyDoubleQuote=\u201c\x00OpenCurlyQuote=\u2018\x00Or=\u2a54\x00Oscr=\U0001d4aa\x00Oslash=\xd8\x00'
    'Otilde=\xd5\x00Otimes=\u2a37\x00Ouml=\xd6\x00OverBar=\u203e\x00OverBrace=\u23de\x00OverBracket=\u23b4\x00'
    'OverParenthesis=\u23dc\x00PartialD=\u2202\x00Pcy=\u041f\x00Pfr=\U0001d513\x00Phi=\u03a6\x00Pi=\u03a0\x00'
    'PlusMinus=\xb1\x00Poincareplane=\u210c\x00Popf=\u2119\x00Pr=\u2abb\x00Precedes=\u227a\x00PrecedesEqual=\u2aaf\x00'
    'PrecedesSlantEqual=\u227c\x00PrecedesTilde=\u227e\x00Prime=\u2033\x00Product=\u220f\x00Proportion=\u2237\x00'
    'Proportional=\u221d\x00Pscr=\U0001d4ab\x00Psi=\u03a8\x00QUOT="\x00Qfr=\U0001d514\x00Qopf=\u211a\x00'
    'Qscr=\U0001d4ac\x00RBarr=\u2910\x00REG=\xae\x00Racute=\u0154\x00Rang=\u27eb\x00Rarr=\u21a0\x00Rarrtl=\u2916\x00'
    'Rcaron=\u0158\x00Rcedil=\u0156\x00Rcy=\u0420\x00Re=\u211c\x00ReverseElement=\u220b\x00ReverseEquilibrium=\u21cb\x00'
    'ReverseUpEquilibrium=\u296f\x00Rfr=\u211c\x00Rho=\u03a1\x00RightAngleBracket=\u27e9\x00RightArrow=\u2192\x00'
    'RightArrowBar=\u21e5\x00RightArrowLeftArrow=\u21c4\x00RightCeiling=\u2309\x00RightDoubleBracket=\u27e7\x00'
    'RightDownTeeVector=\u295d\x00RightDownVector=\u21c2\x00RightDownVectorBar=\u2955\x00RightFloor=\u230b\x00'
    'RightTee=\u22a2\x00RightTeeArrow=\u21a6\x00RightTeeVector=\u295b\x00RightTriangle=\u22b3\x00RightTriangleBar=\u29d0\x00'
    'RightTriangleEqual=\u22b5\x00RightUpDownVector=\u294f\x00RightUpTeeVector=\u295c\x00RightUpVector=\u21be\x00'
    'RightUpVectorBar=\u2954\x00RightVector=\u21c0\x00RightVectorBar=\u2953\x00Rightarrow=\u21d2\x00'
    'Ropf=\u211d\x00RoundImplies=\u2970\x00Rrightarrow=\u21db\x00Rscr=\u211b\x00Rsh=\u21b1\x00RuleDelayed=\u29f4\x00'
    'SHCHcy=\u0429\x00SHcy=\u0428\x00SOFTcy=\u042c\x00Sacute=\u015a\x00Sc=\u2abc\x00Scaron=\u0160\x00Scedil=\u015e\x00'
    'Scirc=\u015c\x00Scy=\u0421\x00Sfr=\U0001d516\x00ShortDownArrow=\u2193\x00ShortLeftArrow=\u2190\x00'
    'ShortRightArrow=\u2192\x00ShortUpArrow=\u2191\x00Sigma=\u03a3\x00SmallCircle=\u2218\x00Sopf=\U0001d54a\x00'
    'Sqrt=\u221a\x00Square=\u25a1\x00SquareIntersection=\u2293\x00SquareSubset=\u228f\x00SquareSubsetEqual=\u2291\x00'
    'SquareSuperset=\u2290\x00SquareSupersetEqual=\u2292\x00SquareUnion=\u2294\x00Sscr=\U0001d4ae\x00'
    'Star=\u22c6\x00Sub=\u22d0\x00Subset=\u22d0\x00SubsetEqual=\u2286\x00Succeeds=\u227b\x00SucceedsEqual=\u2ab0\x00'
    'SucceedsSlantEqual=\u227d\x00SucceedsTilde=\u227f\x00SuchThat=\u220b\x00Sum=\u2211\x00Sup=\u22d1\x00'
    'Superset=\u2283\x00SupersetEqual=\u2287\x00Supset=\u22d1\x00THORN=\xde\x00TRADE=\u2122\x00TSHcy=\u040b\x00'
    'TScy=\u0426\x00Tab=\t\x00Tau=\u03a4\x00Tcaron=\u0164\x00Tcedil=\u0162\x00Tcy=\u0422\x00Tfr=\U0001d517\x00'
    'Therefore=\u2234\x00Theta=\u0398\x00ThickSpace=\u205f\u200a\x00ThinSpace=\u2009\x00Tilde=\u223c\x00'
    'TildeEqual=\u2243\x00TildeFullEqual=\u2245\x00TildeTilde=\u2248\x00Topf=\U0001d54b\x00TripleDot=\u20db\x00'
    'Tscr=\U0001d4af\x00Tstrok=\u0166\x00Uacute=\xda\x00Uarr=\u219f\x00Uarrocir=\u2949\x00Ubrcy=\u040e\x00'
    'Ubreve=\u016c\x00Ucirc=\xdb\x00Ucy=\u0423\x00Udblac=\u0170\x00Ufr=\U0001d518\x00Ugrave=\xd9\x00Umacr=\u016a\x00'
    'UnderBar=_\x00UnderBrace=\u23df\x00UnderBracket=\u23b5\x00UnderParenthesis=\u23dd\x00Union=\u22c3\x00'
    'UnionPlus=\u228e\x00Uogon=\u0172\x00Uopf=\U0001d54c\x00UpArrow=\u2191\x00UpArrowBar=\u2912\x00UpArrowDownArrow=\u21c5\x00'
    'UpDownArrow=\u2195\x00UpEquilibrium=\u296e\x00UpTee=\u22a5\x00UpTeeArrow=\u21a5\x00Uparrow=\u21d1\x00'
    'Updownarrow=\u21d5\x00UpperLeftArrow=\u2196\x00UpperRightArrow=\u2197\x00Upsi=\u03d2\x00Upsilon=\u03a5\x00'
    'Uring=\u016e\x00Uscr=\U0001d4b0\x00Utilde=\u0168\x00Uuml=\xdc\x00VDash=\u22ab\x00Vbar=\u2aeb\x00Vcy=\u0412\x00'
    'Vdash=\u22a9\x00Vdashl=\u2ae6\x00Vee=\u22c1\x00Verbar=\u2016\x00Vert=\u2016\x00VerticalBar=\u2223\x00'
    'VerticalLine=|\x00VerticalSeparator=\u2758\x00VerticalTilde=\u2240\x00VeryThinSpace=\u200a\x00Vfr=\U0001d519\x00'
    'Vopf=\U0001d54d\x00Vscr=\U0001d4b1\x00Vvdash=\u22aa\x00Wcirc=\u0174\x00Wedge=\u22c0\x00Wfr=\U0001d51a\x00'
    'Wopf=\U0001d54e\x00Wscr=\U0001d4b2\x00Xfr=\U0001d51b\x00Xi=\u039e\x00Xopf=\U0001d54f\x00Xscr=\U0001d4b3\x00'
    'YAcy=\u042f\x00YIcy=\u0407\x00YUcy=\u042e\x00Yacute=\xdd\x00Ycirc=\u0176\x00Ycy=\u042b\x00Yfr=\U0001d51c\x00'
    'Yopf=\U0001d550\x00Yscr=\U0001d4b4\x00Yuml=\u0178\x00ZHcy=\u0416\x00Zacute=\u0179\x00Zcaron=\u017d\x00'
    'Zcy=\u0417\x00Zdot=\u017b\x00ZeroWidthSpace=\u200b\x00Zeta=\u0396\x00Zfr=\u2128\x00Zopf=\u2124\x00Zscr=\U0001d4b5\x00'
    'aacute=\xe1\x00abreve=\u0103\x00ac=\u223e\x00acE=\u223e\u0333\x00acd=\u223f\x00acirc=\xe2\x00acute=\xb4\x00'
    'acy=\u0430\x00aelig=\xe6\x00af=\u2061\x00afr=\U0001d51e\x00agrave=\xe0\x00alefsym=\u2135\x00aleph=\u2135\x00'
    'alpha=\u03b1\x00amacr=\u0101\x00amalg=\u2a3f\x00amp=&\x00and=\u2227\x00andand=\u2a55\x00andd=\u2a5c\x00'
    'andslope=\u2a58\x00andv=\u2a5a\x00ang=\u2220\x00ange=\u29a4\x00angle=\u2220\x00angmsd=\u2221\x00angmsdaa=\u29a8\x00'
    'angmsdab=\u29a9\x00angmsdac=\u29aa\x00angmsdad=\u29ab\x00angmsdae=\u29ac\x00angmsdaf=\u29ad\x00angmsdag=\u29ae\x00'
    'angmsdah=\u29af\x00angrt=\u221f\x00angrtvb=\u22be\x00angrtvbd=\u299d\x00angsph=\u2222\x00angst=\xc5\x00'
    'angzarr=\u237c\x00aogon=\u0105\x00aopf=\U0001d552\x00ap=\u2248\x00apE=\u2a70\x00apacir=\u2a6f\x00ape=\u224a\x00'
    "apid=\u224b\x00apos='\x00approx=\u2248\x00approxeq=\u224a\x00aring=\xe5\x00ascr=\U0001d4b6\x00ast=*\x00"
    'asymp=\u2248\x00asympeq=\u224d\x00atilde=\xe3\x00auml=\xe4\x00awconint=\u2233\x00awint=\u2a11\x00bNot=\u2aed\x00'
    'backcong=\u224c\x00backepsilon=\u03f6\x00backprime=\u2035\x00backsim=\u223d\x00backsimeq=\u22cd\x00'
    'barvee=\u22bd\x00barwed=\u2305\x00barwedge=\u2305\x00bbrk=\u23b5\x00bbrktbrk=\u23b6\x00bcong=\u224c\x00'
    'bcy=\u0431\x00bdquo=\u201e\x00becaus=\u2235\x00because=\u2235\x00bemptyv=\u29b0\x00bepsi=\u03f6\x00'
    'bernou=\u212c\x00beta=\u03b2\x00beth=\u2136\x00between=\u226c\x00bfr=\U0001d51f\x00bigcap=\u22c2\x00'
    'bigcirc=\u25ef\x00bigcup=\u22c3\x00bigodot=\u2a00\x00bigoplus=\u2a01\x00bigotimes=\u2a02\x00bigsqcup=\u2a06\x00'
    'bigstar=\u2605\x00bigtriangledown=\u25bd\x00bigtriangleup=\u25b3\x00biguplus=\u2a04\x00bigvee=\u22c1\x00'
    'bigwedge=\u22c0\x00bkarow=\u290d\x00blacklozenge=\u29eb\x00blacksquare=\u25aa\x00blacktriangle=\u25b4\x00'
    'blacktriangledown=\u25be\x00blacktriangleleft=\u25c2\x00blacktriangleright=\u25b8\x00blank=\u2423\x00'
    'blk12=\u2592\x00blk14=\u2591\x00blk34=\u2593\x00block=\u2588\x00bne==\u20e5\x00bnequiv=\u2261\u20e5\x00'
    'bnot=\u2310\x00bopf=\U0001d553\x00bot=\u22a5\x00bottom=\u22a5\x00bowtie=\u22c8\x00boxDL=\u2557\x00boxDR=\u2554\x00'
    'boxDl=\u2556\x00boxDr=\u2553\x00boxH=\u2550\x00boxHD=\u2566\x00boxHU=\u2569\x00boxHd=\u2564\x00boxHu=\u2567\x00'
    'boxUL=\u255d\x00boxUR=\u255a\x00boxUl=\u255c\x00boxUr=\u2559\x00boxV=\u2551\x00boxVH=\u256c\x00boxVL=\u2563\x00'
    'boxVR=\u2560\x00boxVh=\u256b\x00boxVl=\u2562\x00boxVr=\u255f\x00boxbox=\u29c9\x00boxdL=\u2555\x00boxdR=\u2552\x00'
    'boxdl=\u2510\x00boxdr=\u250c\x00boxh=\u2500\x00boxhD=\u2565\x00boxhU=\u2568\x00boxhd=\u252c\x00boxhu=\u2534\x00'
    'boxminus=\u229f\x00boxplus=\u229e\x00boxtimes=\u22a0\x00boxuL=\u255b\x00boxuR=\u2558\x00boxul=\u2518\x00'
    'boxur=\u2514\x00boxv=\u2502\x00boxvH=\u256a\x00boxvL=\u2561\x00boxvR=\u255e\x00boxvh=\u253c\x00boxvl=\u2524\x00'
    'boxvr=\u251c\x00bprime=\u2035\x00breve=\u02d8\x00brvbar=\xa6\x00bscr=\U0001d4b7\x00bsemi=\u204f\x00'
    'bsim=\u223d\x00bsime=\u22cd\x00bsol=\\\x00bsolb=\u29c5\x00bsolhsub=\u27c8\x00bull=\u2022\x00bullet=\u2022\x00'
    'bump=\u224e\x00bumpE=\u2aae\x00bumpe=\u224f\x00bumpeq=\u224f\x00cacute=\u0107\x00cap=\u2229\x00capand=\u2a44\x00'
    'capbrcup=\u2a49\x00capcap=\u2a4b\x00capcup=\u2a47\x00capdot=\u2a40\x00caps=\u2229\ufe00\x00caret=\u2041\x00'
    'caron=\u02c7\x00ccaps=\u2a4d\x00ccaron=\u010d\x00ccedil=\xe7\x00ccirc=\u0109\x00ccups=\u2a4c\x00ccupssm=\u2a50\x00'
    'cdot=\u010b\x00cedil=\xb8\x00cemptyv=\u29b2\x00cent=\xa2\x00centerdot=\xb7\x00cfr=\U0001d520\x00chcy=\u0447\x00'
    'check=\u2713\x00checkmark=\u2713\x00chi=\u03c7\x00cir=\u25cb\x00cirE=\u29c3\x00circ=\u02c6\x00circeq=\u2257\x00'
    'circlearrowleft=\u21ba\x00circlearrowright=\u21bb\x00circledR=\xae\x00circledS=\u24c8\x00circledast=\u229b\x00'
    'circledcirc=\u229a\x00circleddash=\u229d\x00cire=\u2257\x00cirfnint=\u2a10\x00cirmid=\u2aef\x00cirscir=\u29c2\x00'
    'clubs=\u2663\x00clubsuit=\u2663\x00colon=:\x00colone=\u2254\x00coloneq=\u2254\x00comma=,\x00commat=@\x00'
    'comp=\u2201\x00compfn=\u2218\x00complement=\u2201\x00complexes=\u2102\x00cong=\u2245\x00congdot=\u2a6d\x00'
    'conint=\u222e\x00copf=\U0001d554\x00coprod=\u2210\x00copy=\xa9\x00copysr=\u2117\x00crarr=\u21b5\x00'
    'cross=\u2717\x00cscr=\U0001d4b8\x00csub=\u2acf\x00csube=\u2ad1\x00csup=\u2ad0\x00csupe=\u2ad2\x00ctdot=\u22ef\x00'
    'cudarrl=\u2938\x00cudarrr=\u2935\x00cuepr=\u22de\x00cuesc=\u22df\x00cularr=\u21b6\x00cularrp=\u293d\x00'
    'cup=\u222a\x00cupbrcap=\u2a48\x00cupcap=\u2a46\x00cupcup=\u2a4a\x00cupdot=\u228d\x00cupor=\u2a45\x00'
    'cups=\u222a\ufe00\x00curarr=\u21b7\x00curarrm=\u293c\x00curlyeqprec=\u22de\x00curlyeqsucc=\u22df\x00'
    'curlyvee=\u22ce\x00curlywedge=\u22cf\x00curren=\xa4\x00curvearrowleft=\u21b6\x00curvearrowright=\u21b7\x00'
    'cuvee=\u22ce\x00cuwed=\u22cf\x00cwconint=\u2232\x00cwint=\u2231\x00cylcty=\u232d\x00dArr=\u21d3\x00'
    'dHar=\u2965\x00dagger=\u2020\x00daleth=\u2138\x00darr=\u2193\x00dash=\u2010\x00dashv=\u22a3\x00dbkarow=\u290f\x00'
    'dblac=\u02dd\x00dcaron=\u010f\x00dcy=\u0434\x00dd=\u2146\x00ddagger=\u2021\x00ddarr=\u21ca\x00ddotseq=\u2a77\x00'
    'deg=\xb0\x00delta=\u03b4\x00demptyv=\u29b1\x00dfisht=\u297f\x00dfr=\U0001d521\x00dharl=\u21c3\x00dharr=\u21c2\x00'
    'diam=\u22c4\x00diamond=\u22c4\x00diamondsuit=\u2666\x00diams=\u2666\x00die=\xa8\x00digamma=\u03dd\x00'
    'disin=\u22f2\x00div=\xf7\x00divide=\xf7\x00divideontimes=\u22c7\x00divonx=\u22c7\x00djcy=\u0452\x00'
    'dlcorn=\u231e\x00dlcrop=\u230d\x00dollar=$\x00dopf=\U0001d555\x00dot=\u02d9\x00doteq=\u2250\x00doteqdot=\u2251\x00'
    'dotminus=\u2238\x00dotplus=\u2214\x00dotsquare=\u22a1\x00doublebarwedge=\u2306\x00downarrow=\u2193\x00'
    'downdownarrows=\u21ca\x00downharpoonleft=\u21c3\x00downharpoonright=\u21c2\x00drbkarow=\u2910\x00'
    'drcorn=\u231f\x00drcrop=\u230c\x00dscr=\U0001d4b9\x00dscy=\u0455\x00dsol=\u29f6\x00dstrok=\u0111\x00'
    'dtdot=\u22f1\x00dtri=\u25bf\x00dtrif=\u25be\x00duarr=\u21f5\x00duhar=\u296f\x00dwangle=\u29a6\x00dzcy=\u045f\x00'
    'dzigrarr=\u27ff\x00eDDot=\u2a77\x00eDot=\u2251\x00eacute=\xe9\x00easter=\u2a6e\x00ecaron=\u011b\x00'
    'ecir=\u2256\x00ecirc=\xea\x00ecolon=\u2255\x00ecy=\u044d\x00edot=\u0117\x00ee=\u2147\x00efDot=\u2252\x00'
    'efr=\U0001d522\x00eg=\u2a9a\x00egrave=\xe8\x00egs=\u2a96\x00egsdot=\u2a98\x00el=\u2a99\x00elinters=\u23e7\x00'
    'ell=\u2113\x00els=\u2a95\x00elsdot=\u2a97\x00emacr=\u0113\x00empty=\u2205\x00emptyset=\u2205\x00emptyv=\u2205\x00'
    'emsp=\u2003\x00emsp13=\u2004\x00emsp14=\u2005\x00eng=\u014b\x00ensp=\u2002\x00eogon=\u0119\x00eopf=\U0001d556\x00'
    'epar=\u22d5\x00eparsl=\u29e3\x00eplus=\u2a71\x00epsi=\u03b5\x00epsilon=\u03b5\x00epsiv=\u03f5\x00eqcirc=\u2256\x00'
    'eqcolon=\u2255\x00eqsim=\u2242\x00eqslantgtr=\u2a96\x00eqslantless=\u2a95\x00equals==\x00equest=\u225f\x00'
    'equiv=\u2261\x00equivDD=\u2a78\x00eqvparsl=\u29e5\x00erDot=\u2253\x00erarr=\u2971\x00escr=\u212f\x00'
    'esdot=\u2250\x00esim=\u2242\x00eta=\u03b7\x00eth=\xf0\x00euml=\xeb\x00euro=\u20ac\x00excl=!\x00exist=\u2203\x00'
    'expectation=\u2130\x00exponentiale=\u2147\x00fallingdotseq=\u2252\x00fcy=\u0444\x00female=\u2640\x00'
    'ffilig=\ufb03\x00fflig=\ufb00\x00ffllig=\ufb04\x00ffr=\U0001d523\x00filig=\ufb01\x00fjlig=fj\x00flat=\u266d\x00'
    'fllig=\ufb02\x00fltns=\u25b1\x00fnof=\u0192\x00fopf=\U0001d557\x00forall=\u2200\x00fork=\u22d4\x00forkv=\u2ad9\x00'
    'fpartint=\u2a0d\x00frac12=\xbd\x00frac13=\u2153\x00frac14=\xbc\x00frac15=\u2155\x00frac16=\u2159\x00'
    'frac18=\u215b\x00frac23=\u2154\x00frac25=\u2156\x00frac34=\xbe\x00frac35=\u2157\x00frac38=\u215c\x00'
    'frac45=\u2158\x00frac56=\u215a\x00frac58=\u215d\x00frac78=\u215e\x00frasl=\u2044\x00frown=\u2322\x00'
    'fscr=\U0001d4bb\x00gE=\u2267\x00gEl=\u2a8c\x00gacute=\u01f5\x00gamma=\u03b3\x00gammad=\u03dd\x00gap=\u2a86\x00'
    'gbreve=\u011f\x00gcirc=\u011d\x00gcy=\u0433\x00gdot=\u0121\x00ge=\u2265\x00gel=\u22db\x00geq=\u2265\x00'
    'geqq=\u2267\x00geqslant=\u2a7e\x00ges=\u2a7e\x00gescc=\u2aa9\x00gesdot=\u2a80\x00gesdoto=\u2a82\x00'
    'gesdotol=\u2a84\x00gesl=\u22db\ufe00\x00gesles=\u2a94\x00gfr=\U0001d524\x00gg=\u226b\x00ggg=\u22d9\x00'
    'gimel=\u2137\x00gjcy=\u0453\x00gl=\u2277\x00glE=\u2a92\x00gla=\u2aa5\x00glj=\u2aa4\x00gnE=\u2269\x00gnap=\u2a8a\x00'
    'gnapprox=\u2a8a\x00gne=\u2a88\x00gneq=\u2a88\x00gneqq=\u2269\x00gnsim=\u22e7\x00gopf=\U0001d558\x00'
    'grave=`\x00gscr=\u210a\x00gsim=\u2273\x00gsime=\u2a8e\x00gsiml=\u2a90\x00gt=>\x00gtcc=\u2aa7\x00gtcir=\u2a7a\x00'
    'gtdot=\u22d7\x00gtlPar=\u2995\x00gtquest=\u2a7c\x00gtrapprox=\u2a86\x00gtrarr=\u2978\x00gtrdot=\u22d7\x00'
    'gtreqless=\u22db\x00gtreqqless=\u2a8c\x00gtrless=\u2277\x00gtrsim=\u2273\x00gvertneqq=\u2269\ufe00\x00'
    'gvnE=\u2269\ufe00\x00hArr=\u21d4\x00hairsp=\u200a\x00half=\xbd\x00hamilt=\u210b\x00hardcy=\u044a\x00'
    'harr=\u2194\x00harrcir=\u2948\x00harrw=\u21ad\x00hbar=\u210f\x00hcirc=\u0125\x00hearts=\u2665\x00heartsuit=\u2665\x00'
    'hellip=\u2026\x00hercon=\u22b9\x00hfr=\U0001d525\x00hksearow=\u2925\x00hkswarow=\u2926\x00hoarr=\u21ff\x00'
    'homtht=\u223b\x00hookleftarrow=\u21a9\x00hookrightarrow=\u21aa\x00hopf=\U0001d559\x00horbar=\u2015\x00'
    'hscr=\U0001d4bd\x00hslash=\u210f\x00hstrok=\u0127\x00hybull=\u2043\x00hyphen=\u2010\x00iacute=\xed\x00'
    'ic=\u2063\x00icirc=\xee\x00icy=\u0438\x00iecy=\u0435\x00iexcl=\xa1\x00iff=\u21d4\x00ifr=\U0001d526\x00'
    'igrave=\xec\x00ii=\u2148\x00iiiint=\u2a0c\x00iiint=\u222d\x00iinfin=\u29dc\x00iiota=\u2129\x00ijlig=\u0133\x00'
    'imacr=\u012b\x00image=\u2111\x00imagline=\u2110\x00imagpart=\u2111\x00imath=\u0131\x00imof=\u22b7\x00'
    'imped=\u01b5\x00in=\u2208\x00incare=\u2105\x00infin=\u221e\x00infintie=\u29dd\x00inodot=\u0131\x00int=\u222b\x00'
    'intcal=\u22ba\x00integers=\u2124\x00intercal=\u22ba\x00intlarhk=\u2a17\x00intprod=\u2a3c\x00iocy=\u0451\x00'
    'iogon=\u012f\x00iopf=\U0001d55a\x00iota=\u03b9\x00iprod=\u2a3c\x00iquest=\xbf\x00iscr=\U0001d4be\x00'
    'isin=\u2208\x00isinE=\u22f9\x00isindot=\u22f5\x00isins=\u22f4\x00isinsv=\u22f3\x00isinv=\u2208\x00it=\u2062\x00'
    'itilde=\u0129\x00iukcy=\u0456\x00iuml=\xef\x00jcirc=\u0135\x00jcy=\u0439\x00jfr=\U0001d527\x00jmath=\u0237\x00'
    'jopf=\U0001d55b\x00jscr=\U0001d4bf\x00jsercy=\u0458\x00jukcy=\u0454\x00kappa=\u03ba\x00kappav=\u03f0\x00'
    'kcedil=\u0137\x00kcy=\u043a\x00kfr=\U0001d528\x00kgreen=\u0138\x00khcy=\u0445\x00kjcy=\u045c\x00kopf=\U0001d55c\x00'
    'kscr=\U0001d4c0\x00lAarr=\u21da\x00lArr=\u21d0\x00lAtail=\u291b\x00lBarr=\u290e\x00lE=\u2266\x00lEg=\u2a8b\x00'
    'lHar=\u2962\x00lacute=\u013a\x00laemptyv=\u29b4\x00lagran=\u2112\x00lambda=\u03bb\x00lang=\u27e8\x00'
    'langd=\u2991\x00langle=\u27e8\x00lap=\u2a85\x00laquo=\xab\x00larr=\u2190\x00larrb=\u21e4\x00larrbfs=\u291f\x00'
    'larrfs=\u291d\x00larrhk=\u21a9\x00larrlp=\u21ab\x00larrpl=\u2939\x00larrsim=\u2973\x00larrtl=\u21a2\x00'
    'lat=\u2aab\x00latail=\u2919\x00late=\u2aad\x00lates=\u2aad\ufe00\x00lbarr=\u290c\x00lbbrk=\u2772\x00'
    'lbrace={\x00lbrack=[\x00lbrke=\u298b\x00lbrksld=\u298f\x00lbrkslu=\u298d\x00lcaron=\u013e\x00lcedil=\u013c\x00'
    'lceil=\u2308\x00lcub={\x00lcy=\u043b\x00ldca=\u2936\x00ldquo=\u201c\x00ldquor=\u201e\x00ldrdhar=\u2967\x00'
    'ldrushar=\u294b\x00ldsh=\u21b2\x00le=\u2264\x00leftarrow=\u2190\x00leftarrowtail=\u21a2\x00leftharpoondown=\u21bd\x00'
    'leftharpoonup=\u21bc\x00leftleftarrows=\u21c7\x00leftrightarrow=\u2194\x00leftrightarrows=\u21c6\x00'
    'leftrightharpoons=\u21cb\x00leftrightsquigarrow=\u21ad\x00leftthreetimes=\u22cb\x00leg=\u22da\x00'
    'leq=\u2264\x00leqq=\u2266\x00leqslant=\u2a7d\x00les=\u2a7d\x00lescc=\u2aa8\x00lesdot=\u2a7f\x00lesdoto=\u2a81\x00'
    'lesdotor=\u2a83\x00lesg=\u22da\ufe00\x00lesges=\u2a93\x00lessapprox=\u2a85\x00lessdot=\u22d6\x00lesseqgtr=\u22da\x00'
    'lesseqqgtr=\u2a8b\x00lessgtr=\u2276\x00lesssim=\u2272\x00lfisht=\u297c\x00lfloor=\u230a\x00lfr=\U0001d529\x00'
    'lg=\u2276\x00lgE=\u2a91\x00lhard=\u21bd\x00lharu=\u21bc\x00lharul=\u296a\x00lhblk=\u2584\x00ljcy=\u0459\x00'
    'll=\u226a\x00llarr=\u21c7\x00llcorner=\u231e\x00llhard=\u296b\x00lltri=\u25fa\x00lmidot=\u0140\x00lmoust=\u23b0\x00'
    'lmoustache=\u23b0\x00lnE=\u2268\x00lnap=\u2a89\x00lnapprox=\u2a89\x00lne=\u2a87\x00lneq=\u2a87\x00lneqq=\u2268\x00'
    'lnsim=\u22e6\x00loang=\u27ec\x00loarr=\u21fd\x00lobrk=\u27e6\x00longleftarrow=\u27f5\x00longleftrightarrow=\u27f7\x00'
    'longmapsto=\u27fc\x00longrightarrow=\u27f6\x00looparrowleft=\u21ab\x00looparrowright=\u21ac\x00'
    'lopar=\u2985\x00lopf=\U0001d55d\x00loplus=\u2a2d\x00lotimes=\u2a34\x00lowast=\u2217\x00lowbar=_\x00'
    'loz=\u25ca\x00lozenge=\u25ca\x00lozf=\u29eb\x00lpar=(\x00lparlt=\u2993\x00lrarr=\u21c6\x00lrcorner=\u231f\x00'
    'lrhar=\u21cb\x00lrhard=\u296d\x00lrm=\u200e\x00lrtri=\u22bf\x00lsaquo=\u2039\x00lscr=\U0001d4c1\x00'
    'lsh=\u21b0\x00lsim=\u2272\x00lsime=\u2a8d\x00lsimg=\u2a8f\x00lsqb=[\x00lsquo=\u2018\x00lsquor=\u201a\x00'
    'lstrok=\u0142\x00lt=<\x00ltcc=\u2aa6\x00ltcir=\u2a79\x00ltdot=\u22d6\x00lthree=\u22cb\x00ltimes=\u22c9\x00'
    'ltlarr=\u2976\x00ltquest=\u2a7b\x00ltrPar=\u2996\x00ltri=\u25c3\x00ltrie=\u22b4\x00ltrif=\u25c2\x00'
    'lurdshar=\u294a\x00luruhar=\u2966\x00lvertneqq=\u2268\ufe00\x00lvnE=\u2268\ufe00\x00mDDot=\u223a\x00'
    'macr=\xaf\x00male=\u2642\x00malt=\u2720\x00maltese=\u2720\x00map=\u21a6\x00mapsto=\u21a6\x00mapstodown=\u21a7\x00'
    'mapstoleft=\u21a4\x00mapstoup=\u21a5\x00marker=\u25ae\x00mcomma=\u2a29\x00mcy=\u043c\x00mdash=\u2014\x00'
    'measuredangle=\u2221\x00mfr=\U0001d52a\x00mho=\u2127\x00micro=\xb5\x00mid=\u2223\x00midast=*\x00midcir=\u2af0\x00'
    'middot=\xb7\x00minus=\u2212\x00minusb=\u229f\x00minusd=\u2238\x00minusdu=\u2a2a\x00mlcp=\u2adb\x00mldr=\u2026\x00'
    'mnplus=\u2213\x00models=\u22a7\x00mopf=\U0001d55e\x00mp=\u2213\x00mscr=\U0001d4c2\x00mstpos=\u223e\x00'
    'mu=\u03bc\x00multimap=\u22b8\x00mumap=\u22b8\x00nGg=\u22d9\u0338\x00nGt=\u226b\u20d2\x00nGtv=\u226b\u0338\x00'
    'nLeftarrow=\u21cd\x00nLeftrightarrow=\u21ce\x00nLl=\u22d8\u0338\x00nLt=\u226a\u20d2\x00nLtv=\u226a\u0338\x00'
    'nRightarrow=\u21cf\x00nVDash=\u22af\x00nVdash=\u22ae\x00nabla=\u2207\x00nacute=\u0144\x00nang=\u2220\u20d2\x00'
    'nap=\u2249\x00napE=\u2a70\u0338\x00napid=\u224b\u0338\x00napos=\u0149\x00napprox=\u2249\x00natur=\u266e\x00'
    'natural=\u266e\x00naturals=\u2115\x00nbsp=\xa0\x00nbump=\u224e\u0338\x00nbumpe=\u224f\u0338\x00ncap=\u2a43\x00'
    'ncaron=\u0148\x00ncedil=\u0146\x00ncong=\u2247\x00ncongdot=\u2a6d\u0338\x00ncup=\u2a42\x00ncy=\u043d\x00'
    'ndash=\u2013\x00ne=\u2260\x00neArr=\u21d7\x00nearhk=\u2924\x00nearr=\u2197\x00nearrow=\u2197\x00nedot=\u2250\u0338\x00'
    'nequiv=\u2262\x00nesear=\u2928\x00nesim=\u2242\u0338\x00nexist=\u2204\x00nexists=\u2204\x00nfr=\U0001d52b\x00'
    'ngE=\u2267\u0338\x00nge=\u2271\x00ngeq=\u2271\x00ngeqq=\u2267\u0338\x00ngeqslant=\u2a7e\u0338\x00'
    'nges=\u2a7e\u0338\x00ngsim=\u2275\x00ngt=\u226f\x00ngtr=\u226f\x00nhArr=\u21ce\x00nharr=\u21ae\x00nhpar=\u2af2\x00'
    'ni=\u220b\x00nis=\u22fc\x00nisd=\u22fa\x00niv=\u220b\x00njcy=\u045a\x00nlArr=\u21cd\x00nlE=\u2266\u0338\x00'
    'nlarr=\u219a\x00nldr=\u2025\x00nle=\u2270\x00nleftarrow=\u219a\x00nleftrightarrow=\u21ae\x00nleq=\u2270\x00'
    'nleqq=\u2266\u0338\x00nleqslant=\u2a7d\u0338\x00nles=\u2a7d\u0338\x00nless=\u226e\x00nlsim=\u2274\x00'
    'nlt=\u226e\x00nltri=\u22ea\x00nltrie=\u22ec\x00nmid=\u2224\x00nopf=\U0001d55f\x00not=\xac\x00notin=\u2209\x00'
    'notinE=\u22f9\u0338\x00notindot=\u22f5\u0338\x00notinva=\u2209\x00notinvb=\u22f7\x00notinvc=\u22f6\x00'
    'notni=\u220c\x00notniva=\u220c\x00notnivb=\u22fe\x00notnivc=\u22fd\x00npar=\u2226\x00nparallel=\u2226\x00'
    'nparsl=\u2afd\u20e5\x00npart=\u2202\u0338\x00npolint=\u2a14\x00npr=\u2280\x00nprcue=\u22e0\x00npre=\u2aaf\u0338\x00'
    'nprec=\u2280\x00npreceq=\u2aaf\u0338\x00nrArr=\u21cf\x00nrarr=\u219b\x00nrarrc=\u2933\u0338\x00nrarrw=\u219d\u0338\x00'
    'nrightarrow=\u219b\x00nrtri=\u22eb\x00nrtrie=\u22ed\x00nsc=\u2281\x00nsccue=\u22e1\x00nsce=\u2ab0\u0338\x00'
    'nscr=\U0001d4c3\x00nshortmid=\u2224\x00nshortparallel=\u2226\x00nsim=\u2241\x00nsime=\u2244\x00nsimeq=\u2244\x00'
    'nsmid=\u2224\x00nspar=\u2226\x00nsqsube=\u22e2\x00nsqsupe=\u22e3\x00nsub=\u2284\x00nsubE=\u2ac5\u0338\x00'
    'nsube=\u2288\x00nsubset=\u2282\u20d2\x00nsubseteq=\u2288\x00nsubseteqq=\u2ac5\u0338\x00nsucc=\u2281\x00'
    'nsucceq=\u2ab0\u0338\x00nsup=\u2285\x00nsupE=\u2ac6\u0338\x00nsupe=\u2289\x00nsupset=\u2283\u20d2\x00'
    'nsupseteq=\u2289\x00nsupseteqq=\u2ac6\u0338\x00ntgl=\u2279\x00ntilde=\xf1\x00ntlg=\u2278\x00ntriangleleft=\u22ea\x00'
    'ntrianglelefteq=\u22ec\x00ntriangleright=\u22eb\x00ntrianglerighteq=\u22ed\x00nu=\u03bd\x00num=#\x00'
    'numero=\u2116\x00numsp=\u2007\x00nvDash=\u22ad\x00nvHarr=\u2904\x00nvap=\u224d\u20d2\x00nvdash=\u22ac\x00'
    'nvge=\u2265\u20d2\x00nvgt=>\u20d2\x00nvinfin=\u29de\x00nvlArr=\u2902\x00nvle=\u2264\u20d2\x00nvlt=<\u20d2\x00'
    'nvltrie=\u22b4\u20d2\x00nvrArr=\u2903\x00nvrtrie=\u22b5\u20d2\x00nvsim=\u223c\u20d2\x00nwArr=\u21d6\x00'
    'nwarhk=\u2923\x00nwarr=\u2196\x00nwarrow=\u2196\x00nwnear=\u2927\x00oS=\u24c8\x00oacute=\xf3\x00oast=\u229b\x00'
    'ocir=\u229a\x00ocirc=\xf4\x00ocy=\u043e\x00odash=\u229d\x00odblac=\u0151\x00odiv=\u2a38\x00odot=\u2299\x00'
    'odsold=\u29bc\x00oelig=\u0153\x00ofcir=\u29bf\x00ofr=\U0001d52c\x00ogon=\u02db\x00ograve=\xf2\x00ogt=\u29c1\x00'
    'ohbar=\u29b5\x00ohm=\u03a9\x00oint=\u222e\x00olarr=\u21ba\x00olcir=\u29be\x00olcross=\u29bb\x00oline=\u203e\x00'
    'olt=\u29c0\x00omacr=\u014d\x00omega=\u03c9\x00omicron=\u03bf\x00omid=\u29b6\x00ominus=\u2296\x00oopf=\U0001d560\x00'
    'opar=\u29b7\x00operp=\u29b9\x00oplus=\u2295\x00or=\u2228\x00orarr=\u21bb\x00ord=\u2a5d\x00order=\u2134\x00'
    'orderof=\u2134\x00ordf=\xaa\x00ordm=\xba\x00origof=\u22b6\x00oror=\u2a56\x00orslope=\u2a57\x00orv=\u2a5b\x00'
    'oscr=\u2134\x00oslash=\xf8\x00osol=\u2298\x00otilde=\xf5\x00otimes=\u2297\x00otimesas=\u2a36\x00ouml=\xf6\x00'
    'ovbar=\u233d\x00par=\u2225\x00para=\xb6\x00parallel=\u2225\x00parsim=\u2af3\x00parsl=\u2afd\x00part=\u2202\x00'
    'pcy=\u043f\x00percnt=%\x00period=.\x00permil=\u2030\x00perp=\u22a5\x00pertenk=\u2031\x00pfr=\U0001d52d\x00'
    'phi=\u03c6\x00phiv=\u03d5\x00phmmat=\u2133\x00phone=\u260e\x00pi=\u03c0\x00pitchfork=\u22d4\x00piv=\u03d6\x00'
    'planck=\u210f\x00planckh=\u210e\x00plankv=\u210f\x00plus=+\x00plusacir=\u2a23\x00plusb=\u229e\x00pluscir=\u2a22\x00'
    'plusdo=\u2214\x00plusdu=\u2a25\x00pluse=\u2a72\x00plusmn=\xb1\x00plussim=\u2a26\x00plustwo=\u2a27\x00'
    'pm=\xb1\x00pointint=\u2a15\x00popf=\U0001d561\x00pound=\xa3\x00pr=\u227a\x00prE=\u2ab3\x00prap=\u2ab7\x00'
    'prcue=\u227c\x00pre=\u2aaf\x00prec=\u227a\x00precapprox=\u2ab7\x00preccurlyeq=\u227c\x00preceq=\u2aaf\x00'
    'precnapprox=\u2ab9\x00precneqq=\u2ab5\x00precnsim=\u22e8\x00precsim=\u227e\x00prime=\u2032\x00primes=\u2119\x00'
    'prnE=\u2ab5\x00prnap=\u2ab9\x00prnsim=\u22e8\x00prod=\u220f\x00profalar=\u232e\x00profline=\u2312\x00'
    'profsurf=\u2313\x00prop=\u221d\x00propto=\u221d\x00prsim=\u227e\x00prurel=\u22b0\x00pscr=\U0001d4c5\x00'
    'psi=\u03c8\x00puncsp=\u2008\x00qfr=\U0001d52e\x00qint=\u2a0c\x00qopf=\U0001d562\x00qprime=\u2057\x00'
    'qscr=\U0001d4c6\x00quaternions=\u210d\x00quatint=\u2a16\x00quest=?\x00questeq=\u225f\x00quot="\x00rAarr=\u21db\x00'
    'rArr=\u21d2\x00rAtail=\u291c\x00rBarr=\u290f\x00rHar=\u2964\x00race=\u223d\u0331\x00racute=\u0155\x00'
    'radic=\u221a\x00raemptyv=\u29b3\x00rang=\u27e9\x00rangd=\u2992\x00range=\u29a5\x00rangle=\u27e9\x00'
    'raquo=\xbb\x00rarr=\u2192\x00rarrap=\u2975\x00rarrb=\u21e5\x00rarrbfs=\u2920\x00rarrc=\u2933\x00rarrfs=\u291e\x00'
    'rarrhk=\u21aa\x00rarrlp=\u21ac\x00rarrpl=\u2945\x00rarrsim=\u2974\x00rarrtl=\u21a3\x00rarrw=\u219d\x00'
    'ratail=\u291a\x00ratio=\u2236\x00rationals=\u211a\x00rbarr=\u290d\x00rbbrk=\u2773\x00rbrace=}\x00rbrack=]\x00'
    'rbrke=\u298c\x00rbrksld=\u298e\x00rbrkslu=\u2990\x00rcaron=\u0159\x00rcedil=\u0157\x00rceil=\u2309\x00'
    'rcub=}\x00rcy=\u0440\x00rdca=\u2937\x00rdldhar=\u2969\x00rdquo=\u201d\x00rdquor=\u201d\x00rdsh=\u21b3\x00'
    'real=\u211c\x00realine=\u211b\x00realpart=\u211c\x00reals=\u211d\x00rect=\u25ad\x00reg=\xae\x00rfisht=\u297d\x00'
    'rfloor=\u230b\x00rfr=\U0001d52f\x00rhard=\u21c1\x00rharu=\u21c0\x00rharul=\u296c\x00rho=\u03c1\x00rhov=\u03f1\x00'
    'rightarrow=\u2192\x00rightarrowtail=\u21a3\x00rightharpoondown=\u21c1\x00rightharpoonup=\u21c0\x00'
    'rightleftarrows=\u21c4\x00rightleftharpoons=\u21cc\x00rightrightarrows=\u21c9\x00rightsquigarrow=\u219d\x00'
    'rightthreetimes=\u22cc\x00ring=\u02da\x00risingdotseq=\u2253\x00rlarr=\u21c4\x00rlhar=\u21cc\x00rlm=\u200f\x00'
    'rmoust=\u23b1\x00rmoustache=\u23b1\x00rnmid=\u2aee\x00roang=\u27ed\x00roarr=\u21fe\x00robrk=\u27e7\x00'
    'ropar=\u2986\x00ropf=\U0001d563\x00roplus=\u2a2e\x00rotimes=\u2a35\x00rpar=)\x00rpargt=\u2994\x00rppolint=\u2a12\x00'
    'rrarr=\u21c9\x00rsaquo=\u203a\x00rscr=\U0001d4c7\x00rsh=\u21b1\x00rsqb=]\x00rsquo=\u2019\x00rsquor=\u2019\x00'
    'rthree=\u22cc\x00rtimes=\u22ca\x00rtri=\u25b9\x00rtrie=\u22b5\x00rtrif=\u25b8\x00rtriltri=\u29ce\x00'
    'ruluhar=\u2968\x00rx=\u211e\x00sacute=\u015b\x00sbquo=\u201a\x00sc=\u227b\x00scE=\u2ab4\x00scap=\u2ab8\x00'
    'scaron=\u0161\x00sccue=\u227d\x00sce=\u2ab0\x00scedil=\u015f\x00scirc=\u015d\x00scnE=\u2ab6\x00scnap=\u2aba\x00'
    'scnsim=\u22e9\x00scpolint=\u2a13\x00scsim=\u227f\x00scy=\u0441\x00sdot=\u22c5\x00sdotb=\u22a1\x00sdote=\u2a66\x00'
    'seArr=\u21d8\x00searhk=\u2925\x00searr=\u2198\x00searrow=\u2198\x00sect=\xa7\x00semi=;\x00seswar=\u2929\x00'
    'setminus=\u2216\x00setmn=\u2216\x00sext=\u2736\x00sfr=\U0001d530\x00sfrown=\u2322\x00sharp=\u266f\x00'
    'shchcy=\u0449\x00shcy=\u0448\x00shortmid=\u2223\x00shortparallel=\u2225\x00shy=\xad\x00sigma=\u03c3\x00'
    'sigmaf=\u03c2\x00sigmav=\u03c2\x00sim=\u223c\x00simdot=\u2a6a\x00sime=\u2243\x00simeq=\u2243\x00simg=\u2a9e\x00'
    'simgE=\u2aa0\x00siml=\u2a9d\x00simlE=\u2a9f\x00simne=\u2246\x00simplus=\u2a24\x00simrarr=\u2972\x00'
    'slarr=\u2190\x00smallsetminus=\u2216\x00smashp=\u2a33\x00smeparsl=\u29e4\x00smid=\u2223\x00smile=\u2323\x00'
    'smt=\u2aaa\x00smte=\u2aac\x00smtes=\u2aac\ufe00\x00softcy=\u044c\x00sol=/\x00solb=\u29c4\x00solbar=\u233f\x00'
    'sopf=\U0001d564\x00spades=\u2660\x00spadesuit=\u2660\x00spar=\u2225\x00sqcap=\u2293\x00sqcaps=\u2293\ufe00\x00'
    'sqcup=\u2294\x00sqcups=\u2294\ufe00\x00sqsub=\u228f\x00sqsube=\u2291\x00sqsubset=\u228f\x00sqsubseteq=\u2291\x00'
    'sqsup=\u2290\x00sqsupe=\u2292\x00sqsupset=\u2290\x00sqsupseteq=\u2292\x00squ=\u25a1\x00square=\u25a1\x00'
    'squarf=\u25aa\x00squf=\u25aa\x00srarr=\u2192\x00sscr=\U0001d4c8\x00ssetmn=\u2216\x00ssmile=\u2323\x00'
    'sstarf=\u22c6\x00star=\u2606\x00starf=\u2605\x00straightepsilon=\u03f5\x00straightphi=\u03d5\x00strns=\xaf\x00'
    'sub=\u2282\x00subE=\u2ac5\x00subdot=\u2abd\x00sube=\u2286\x00subedot=\u2ac3\x00submult=\u2ac1\x00subnE=\u2acb\x00'
    'subne=\u228a\x00subplus=\u2abf\x00subrarr=\u2979\x00subset=\u2282\x00subseteq=\u2286\x00subseteqq=\u2ac5\x00'
    'subsetneq=\u228a\x00subsetneqq=\u2acb\x00subsim=\u2ac7\x00subsub=\u2ad5\x00subsup=\u2ad3\x00succ=\u227b\x00'
    'succapprox=\u2ab8\x00succcurlyeq=\u227d\x00succeq=\u2ab0\x00succnapprox=\u2aba\x00succneqq=\u2ab6\x00'
    'succnsim=\u22e9\x00succsim=\u227f\x00sum=\u2211\x00sung=\u266a\x00sup=\u2283\x00sup1=\xb9\x00sup2=\xb2\x00'
    'sup3=\xb3\x00supE=\u2ac6\x00supdot=\u2abe\x00supdsub=\u2ad8\x00supe=\u2287\x00supedot=\u2ac4\x00suphsol=\u27c9\x00'
    'suphsub=\u2ad7\x00suplarr=\u297b\x00supmult=\u2ac2\x00supnE=\u2acc\x00supne=\u228b\x00supplus=\u2ac0\x00'
    'supset=\u2283\x00supseteq=\u2287\x00supseteqq=\u2ac6\x00supsetneq=\u228b\x00supsetneqq=\u2acc\x00'
    'supsim=\u2ac8\x00supsub=\u2ad4\x00supsup=\u2ad6\x00swArr=\u21d9\x00swarhk=\u2926\x00swarr=\u2199\x00'
    'swarrow=\u2199\x00swnwar=\u292a\x00szlig=\xdf\x00target=\u2316\x00tau=\u03c4\x00tbrk=\u23b4\x00tcaron=\u0165\x00'
    'tcedil=\u0163\x00tcy=\u0442\x00tdot=\u20db\x00telrec=\u2315\x00tfr=\U0001d531\x00there4=\u2234\x00therefore=\u2234\x00'
    'theta=\u03b8\x00thetasym=\u03d1\x00thetav=\u03d1\x00thickapprox=\u2248\x00thicksim=\u223c\x00thinsp=\u2009\x00'
    'thkap=\u2248\x00thksim=\u223c\x00thorn=\xfe\x00tilde=\u02dc\x00times=\xd7\x00timesb=\u22a0\x00timesbar=\u2a31\x00'
    'timesd=\u2a30\x00tint=\u222d\x00toea=\u2928\x00top=\u22a4\x00topbot=\u2336\x00topcir=\u2af1\x00topf=\U0001d565\x00'
    'topfork=\u2ada\x00tosa=\u2929\x00tprime=\u2034\x00trade=\u2122\x00triangle=\u25b5\x00triangledown=\u25bf\x00'
    'triangleleft=\u25c3\x00trianglelefteq=\u22b4\x00triangleq=\u225c\x00triangleright=\u25b9\x00trianglerighteq=\u22b5\x00'
    'tridot=\u25ec\x00trie=\u225c\x00triminus=\u2a3a\x00triplus=\u2a39\x00trisb=\u29cd\x00tritime=\u2a3b\x00'
    'trpezium=\u23e2\x00tscr=\U0001d4c9\x00tscy=\u0446\x00tshcy=\u045b\x00tstrok=\u0167\x00twixt=\u226c\x00'
    'twoheadleftarrow=\u219e\x00twoheadrightarrow=\u21a0\x00uArr=\u21d1\x00uHar=\u2963\x00uacute=\xfa\x00'
    'uarr=\u2191\x00ubrcy=\u045e\x00ubreve=\u016d\x00ucirc=\xfb\x00ucy=\u0443\x00udarr=\u21c5\x00udblac=\u0171\x00'
    'udhar=\u296e\x00ufisht=\u297e\x00ufr=\U0001d532\x00ugrave=\xf9\x00uharl=\u21bf\x00uharr=\u21be\x00uhblk=\u2580\x00'
    'ulcorn=\u231c\x00ulcorner=\u231c\x00ulcrop=\u230f\x00ultri=\u25f8\x00umacr=\u016b\x00uml=\xa8\x00uogon=\u0173\x00'
    'uopf=\U0001d566\x00uparrow=\u2191\x00updownarrow=\u2195\x00upharpoonleft=\u21bf\x00upharpoonright=\u21be\x00'
    'uplus=\u228e\x00upsi=\u03c5\x00upsih=\u03d2\x00upsilon=\u03c5\x00upuparrows=\u21c8\x00urcorn=\u231d\x00'
    'urcorner=\u231d\x00urcrop=\u230e\x00uring=\u016f\x00urtri=\u25f9\x00uscr=\U0001d4ca\x00utdot=\u22f0\x00'
    'utilde=\u0169\x00utri=\u25b5\x00utrif=\u25b4\x00uuarr=\u21c8\x00uuml=\xfc\x00uwangle=\u29a7\x00vArr=\u21d5\x00'
    'vBar=\u2ae8\x00vBarv=\u2ae9\x00vDash=\u22a8\x00vangrt=\u299c\x00varepsilon=\u03f5\x00varkappa=\u03f0\x00'
    'varnothing=\u2205\x00varphi=\u03d5\x00varpi=\u03d6\x00varpropto=\u221d\x00varr=\u2195\x00varrho=\u03f1\x00'
    'varsigma=\u03c2\x00varsubsetneq=\u228a\ufe00\x00varsubsetneqq=\u2acb\ufe00\x00varsupsetneq=\u228b\ufe00\x00'
    'varsupsetneqq=\u2acc\ufe00\x00vartheta=\u03d1\x00vartriangleleft=\u22b2\x00vartriangleright=\u22b3\x00'
    'vcy=\u0432\x00vdash=\u22a2\x00vee=\u2228\x00veebar=\u22bb\x00veeeq=\u225a\x00vellip=\u22ee\x00verbar=|\x00'
    'vert=|\x00vfr=\U0001d533\x00vltri=\u22b2\x00vnsub=\u2282\u20d2\x00vnsup=\u2283\u20d2\x00vopf=\U0001d567\x00'
    'vprop=\u221d\x00vrtri=\u22b3\x00vscr=\U0001d4cb\x00vsubnE=\u2acb\ufe00\x00vsubne=\u228a\ufe00\x00'
    'vsupnE=\u2acc\ufe00\x00vsupne=\u228b\ufe00\x00vzigzag=\u299a\x00wcirc=\u0175\x00wedbar=\u2a5f\x00'
    'wedge=\u2227\x00wedgeq=\u2259\x00weierp=\u2118\x00wfr=\U0001d534\x00wopf=\U0001d568\x00wp=\u2118\x00'
    'wr=\u2240\x00wreath=\u2240\x00wscr=\U0001d4cc\x00xcap=\u22c2\x00xcirc=\u25ef\x00xcup=\u22c3\x00xdtri=\u25bd\x00'
    'xfr=\U0001d535\x00xhArr=\u27fa\x00xharr=\u27f7\x00xi=\u03be\x00xlArr=\u27f8\x00xlarr=\u27f5\x00xmap=\u27fc\x00'
    'xnis=\u22fb\x00xodot=\u2a00\x00xopf=\U0001d569\x00xoplus=\u2a01\x00xotime=\u2a02\x00xrArr=\u27f9\x00'
    'xrarr=\u27f6\x00xscr=\U0001d4cd\x00xsqcup=\u2a06\x00xuplus=\u2a04\x00xutri=\u25b3\x00xvee=\u22c1\x00'
    'xwedge=\u22c0\x00yacute=\xfd\x00yacy=\u044f\x00ycirc=\u0177\x00ycy=\u044b\x00yen=\xa5\x00yfr=\U0001d536\x00'
    'yicy=\u0457\x00yopf=\U0001d56a\x00yscr=\U0001d4ce\x00yucy=\u044e\x00yuml=\xff\x00zacute=\u017a\x00zcaron=\u017e\x00'
    'zcy=\u0437\x00zdot=\u017c\x00zeetrf=\u2128\x00zeta=\u03b6\x00zfr=\U0001d537\x00zhcy=\u0436\x00zigrarr=\u21dd\x00'
    'zopf=\U0001d56b\x00zscr=\U0001d4cf\x00zwj=\u200d\x00zwnj=\u200c\x00'
)
_LEGACY_NAMES = (
    'AElig AMP Aacute Acirc Agrave Aring Atilde Auml COPY Ccedil ETH Eacute Ecirc Egrave '
    'Euml GT Iacute Icirc Igrave Iuml LT Ntilde Oacute Ocirc Ograve Oslash Otilde Ouml '
    'QUOT REG THORN Uacute Ucirc Ugrave Uuml Yacute aacute acirc acute aelig agrave '
    'amp aring atilde auml brvbar ccedil cedil cent copy curren deg divide eacute ecirc '
    'egrave eth euml frac12 frac14 frac34 gt iacute icirc iexcl igrave iquest iuml laquo '
    'lt macr micro middot nbsp not ntilde oacute ocirc ograve ordf ordm oslash otilde '
    'ouml para plusmn pound quot raquo reg sect shy sup1 sup2 sup3 szlig thorn times '
    'uacute ucirc ugrave uml uuml yacute yen yuml '
)
_INVALID_CHARREFS = {
    0x00: '\ufffd',
    0x0d: '\r',
    0x80: '\u20ac',
    0x81: '\x81',
    0x82: '\u201a',
    0x83: '\u0192',
    0x84: '\u201e',
    0x85: '\u2026',
    0x86: '\u2020',
    0x87: '\u2021',
    0x88: '\u02c6',
    0x89: '\u2030',
    0x8a: '\u0160',
    0x8b: '\u2039',
    0x8c: '\u0152',
    0x8d: '\x8d',
    0x8e: '\u017d',
    0x8f: '\x8f',
    0x90: '\x90',
    0x91: '\u2018',
    0x92: '\u2019',
    0x93: '\u201c',
    0x94: '\u201d',
    0x95: '\u2022',
    0x96: '\u2013',
    0x97: '\u2014',
    0x98: '\u02dc',
    0x99: '\u2122',
    0x9a: '\u0161',
    0x9b: '\u203a',
    0x9c: '\u0153',
    0x9d: '\x9d',
    0x9e: '\u017e',
    0x9f: '\u0178',
}
_INVALID_CODEPOINTS = frozenset(
    set(range(0x1, 0x9)) |
    {0xb} |
    set(range(0xe, 0x20)) |
    set(range(0x7f, 0xa0)) |
    set(range(0xfdd0, 0xfdf0)) |
    set(range(0xfffe, 0x10000)) |
    set(range(0x1fffe, 0x20000)) |
    set(range(0x2fffe, 0x30000)) |
    set(range(0x3fffe, 0x40000)) |
    set(range(0x4fffe, 0x50000)) |
    set(range(0x5fffe, 0x60000)) |
    set(range(0x6fffe, 0x70000)) |
    set(range(0x7fffe, 0x80000)) |
    set(range(0x8fffe, 0x90000)) |
    set(range(0x9fffe, 0xa0000)) |
    set(range(0xafffe, 0xb0000)) |
    set(range(0xbfffe, 0xc0000)) |
    set(range(0xcfffe, 0xd0000)) |
    set(range(0xdfffe, 0xe0000)) |
    set(range(0xefffe, 0xf0000)) |
    set(range(0xffffe, 0x100000)) |
    set(range(0x10fffe, 0x110000))
)


_ENTITIES = {}
for _item in _ENTITY_DATA.split("\x00"):
    if _item:
        _name, _, _value = _item.partition("=")
        _ENTITIES[_name] = _value
_LEGACY = frozenset(_LEGACY_NAMES.split())
del _item, _name, _value

__all__ = ["BrisartMarkupParser", "brisart_unescape"]
