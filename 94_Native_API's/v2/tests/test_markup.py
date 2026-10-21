"""
File: v2/tests/test_markup.py

Purpose
-------
Verify v2/brisart_markup.py: character-reference decoding against
html.unescape for every named entity and every code point; tokenizer
behaviour against cases from the HTML Living Standard; agreement with
html.parser on well-formed documents; identical events however the
input is split across feed() calls; and linear time on adversarial
input.

Communication / relationships
-----------------------------
Standard library: unittest, html, html.entities, html.parser (reference
only), plus support.py in this folder.
Verifies: v2/brisart_markup.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED. The code-point
parity test visits every value from 0 to 0x10FFFF.

Edge cases
----------
Hostile fragments include unterminated comments, tags, quotes and
raw-text elements, NUL, the long s, the Kelvin sign and every markup
opener.

Known limitations
-----------------
Malformed input is checked for invariants (chunk-invariance, no
exceptions, linear time), not against html.parser, because the two are
meant to differ there.

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_markup.py
"""

import html
import html.entities
import unittest
from html.parser import HTMLParser

import support
import brisart_markup
from brisart_markup import BrisartMarkupParser, brisart_unescape


class Recorder:
    def _init(self):
        self.events = []

    def handle_starttag(self, tag, attrs):
        self.events.append(("start", tag, tuple(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.events.append(("startend", tag, tuple(attrs)))

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        if self.events and self.events[-1][0] == "data":
            self.events[-1] = ("data", self.events[-1][1] + data)
        else:
            self.events.append(("data", data))

    def handle_comment(self, data):
        self.events.append(("comment", data))

    def handle_decl(self, decl):
        self.events.append(("decl", decl))


class Ours(Recorder, BrisartMarkupParser):
    def __init__(self, **kw):
        BrisartMarkupParser.__init__(self, **kw)
        self._init()


class Theirs(Recorder, HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self._init()


def tokens(text, chunk=None):
    parser = Ours()
    if chunk is None:
        parser.feed(text)
    else:
        for i in range(0, len(text), chunk):
            parser.feed(text[i:i + chunk])
    parser.close()
    return parser.events


class UnescapeTests(unittest.TestCase):
    def test_every_named_entity_in_every_context(self):
        for key in html.entities.html5:
            for suffix in ("", "x", "=", "1", ";", "&", "\u00e9"):
                text = "[&" + key + suffix + "]"
                self.assertEqual(brisart_unescape(text), html.unescape(text), text)

    def test_entity_tables_equal_cpythons(self):
        self.assertEqual(brisart_markup._ENTITIES, {k[:-1]: v for k, v in html.entities.html5.items() if k.endswith(";")})
        self.assertEqual(set(brisart_markup._LEGACY), {k for k in html.entities.html5 if not k.endswith(";")})

    def test_every_code_point(self):
        for code in range(0, 0x110001):
            text = "&#%d;" % code
            self.assertEqual(brisart_unescape(text), html.unescape(text), text)

    def test_attribute_rule_and_huge_numbers(self):
        self.assertEqual(brisart_unescape("?a=1&copy=2", attribute=True), "?a=1&copy=2")
        self.assertEqual(brisart_unescape("?a=1&copy=2"), "?a=1\u00a9=2")
        self.assertEqual(brisart_unescape("&#" + "9" * 5000 + ";"), "\ufffd")


class TokenizerTests(unittest.TestCase):
    def test_quote_aware_tags_and_first_wins_attributes(self):
        self.assertEqual(tokens('<a href="x>y" title=z>'), [("start", "a", (("href", "x>y"), ("title", "z")))])
        self.assertEqual(tokens("<a href=good href=evil>"), [("start", "a", (("href", "good"),))])

    def test_ascii_case_rules(self):
        self.assertEqual(tokens("<script>x</\u017fcript>y</script>"),
                         [("start", "script", ()), ("data", "x</\u017fcript>y"), ("end", "script")])
        self.assertEqual(tokens("<a\u00a0href=x>"), [("start", "a\u00a0href=x", ())])

    def test_raw_text_and_rcdata(self):
        self.assertEqual(tokens("<script>&amp;<b></script>"), [("start", "script", ()), ("data", "&amp;<b>"), ("end", "script")])
        self.assertEqual(tokens("<title>a &amp; <b></title>"), [("start", "title", ()), ("data", "a & <b>"), ("end", "title")])
        self.assertEqual(tokens('<a href="java&Tab;script:x">')[0][2], (("href", "java\tscript:x"),))

    def test_comments_and_declarations(self):
        self.assertEqual(tokens("<!-- a --!> b -->"), [("comment", " a "), ("data", " b -->")])
        self.assertEqual(tokens("<!-->x"), [("comment", ""), ("data", "x")])
        self.assertEqual(tokens("<!DOCTYPE html>"), [("decl", "DOCTYPE html")])
        self.assertEqual(tokens("<?php x ?>y"), [("comment", "?php x ?"), ("data", "y")])

    def test_cut_off_input(self):
        self.assertEqual(tokens("x<a href='y"), [("data", "x")])
        self.assertEqual(tokens("<!-- abc"), [("comment", " abc")])
        self.assertEqual(tokens("<script>abc"), [("start", "script", ()), ("data", "abc")])


def gen_document(r):
    parts = []
    for _ in range(r.randint(1, 14)):
        k = r.random()
        if k < 0.3:
            parts.append(r.choice(["hello", "a &amp; b", "&lt;tag&gt;", "&#65;", "caf\u00e9", "\n  ", "1 &#8364; 2"]))
        elif k < 0.55:
            attrs = r.choice(["", ' class="c"', " href=x", " a='1' b=\"2\"", " disabled"])
            parts.append("<%s%s>" % (r.choice(["a", "div", "p", "SPAN", "li"]), attrs))
        elif k < 0.7:
            parts.append("</%s>" % r.choice(["a", "div", "p", "span"]))
        elif k < 0.8:
            parts.append("<br%s>" % r.choice(["", "/", " /"]))
        elif k < 0.9:
            parts.append("<!-- %s -->" % r.choice(["note", "<b>x</b>", ""]))
        else:
            tag = r.choice(["script", "style"])
            parts.append("<%s>%s</%s>" % (tag, r.choice(["if (a < b) { x = '</b>'; }", "a > b {}", ""]), tag))
    return "".join(parts)


HOSTILE = ["<", "</", "<!", "<!--", "-->", "--!>", "<?", ">", '"', "'", "=", "/", "&", "&#", ";", " ", "\n", "a",
           "<script>", "</script>", "<title>", "</title>", "<plaintext>", "<a ", "<a href='", '<a href="', "&amp;",
           "&copy", "\x00", "\u017f", "\u212a", "<![CDATA[", "<!DOCTYPE", "</>", "<script/>", "</scr", "x=1"]


class DifferentialAndChunkTests(unittest.TestCase):
    def test_well_formed_documents_match_html_parser(self):
        r = support.rng("markup-diff")
        for _ in range(support.scaled(3000)):
            doc = gen_document(r)
            theirs = Theirs()
            theirs.feed(doc)
            theirs.close()
            self.assertEqual(tokens(doc), theirs.events, doc)

    def test_chunking_never_changes_events(self):
        r = support.rng("markup-chunk")
        for _ in range(support.scaled(2000)):
            doc = "".join(r.choice(HOSTILE) for _ in range(r.randint(0, 30)))
            whole = tokens(doc)
            for chunk in (1, 2, 3, 7):
                self.assertEqual(tokens(doc, chunk), whole, (chunk, doc))


class ResourceTests(unittest.TestCase):
    def parse(self, text, size=None):
        p = BrisartMarkupParser()
        if size:
            for i in range(0, len(text), size):
                p.feed(text[i:i + size])
        else:
            p.feed(text)
        p.close()

    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: '<div class="a"><p>t &amp; x</p></div>' * (2000 * k), self.parse)
        support.assert_roughly_linear(self, lambda k: "<!--" * (40_000 * k), self.parse)
        support.assert_roughly_linear(self, lambda k: "<a " * (40_000 * k), self.parse)
        support.assert_roughly_linear(self, lambda k: "<!--" + "x" * (100_000 * k), lambda t: self.parse(t, 100))
        support.assert_roughly_linear(self, lambda k: "&amp" * (40_000 * k), brisart_unescape)


if __name__ == "__main__":
    unittest.main()
