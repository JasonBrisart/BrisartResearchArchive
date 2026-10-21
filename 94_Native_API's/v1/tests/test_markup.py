"""
File: v1/tests/test_markup.py

Purpose
-------
Characterise v1/brisart_markup.py: simple well-formed documents tokenize
as html.parser tokenizes them, raw-text elements hide their content, the
embedded self-test passes, and the known defects (quote-unaware tags,
decoded script content, duplicate attributes, Unicode case folding, NBSP
separators, the 15-name entity table, chunk-dependent decoding and
quadratic time) are pinned down.

Communication / relationships
-----------------------------
Standard library: unittest, gc, time, html.parser (reference only), plus
support.py in this folder.
Verifies: v1/brisart_markup.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
v1 emits several data callbacks per text run; the recorder merges
adjacent data events before comparing with html.parser.

Known limitations
-----------------
The quadratic-time check (M8) uses wall-clock timing with a wide margin;
a heavily loaded machine could still disturb it.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_markup.py
"""

import gc
import time
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

    def handle_endtag(self, tag):
        self.events.append(("end", tag))

    def handle_data(self, data):
        if self.events and self.events[-1][0] == "data":
            self.events[-1] = ("data", self.events[-1][1] + data)
        else:
            self.events.append(("data", data))


class Ours(Recorder, BrisartMarkupParser):
    def __init__(self):
        BrisartMarkupParser.__init__(self)
        self._init()


class Theirs(Recorder, HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self._init()


def tokens(text, chunk=None, parser=Ours):
    p = parser()
    if chunk:
        for i in range(0, len(text), chunk):
            p.feed(text[i:i + chunk])
    else:
        p.feed(text)
    p.close()
    return p.events


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_markup._self_test()

    def test_simple_documents_match_html_parser(self):
        r = support.rng("v1-markup")
        for _ in range(support.scaled(800)):
            parts = []
            for _ in range(r.randint(1, 10)):
                k = r.random()
                if k < 0.35:
                    parts.append(r.choice(["hello", "a &amp; b", "&lt;x&gt;", "&#65;", "caf\u00e9", " "]))
                elif k < 0.7:
                    parts.append("<%s%s>" % (r.choice(["a", "div", "p", "span"]), r.choice(["", ' class="c"', " href=x"])))
                else:
                    parts.append("</%s>" % r.choice(["a", "div", "p", "span"]))
            doc = "".join(parts)
            self.assertEqual(tokens(doc), tokens(doc, parser=Theirs), doc)

    def test_raw_text_hides_markup(self):
        events = tokens("<script>if (a < b) { x = '<b>'; }</script><p>t</p>")
        self.assertNotIn(("start", "b", ()), events)
        self.assertIn(("data", "t"), events)

    def test_known_entities_decode(self):
        self.assertEqual(brisart_unescape("&lt;b&gt; &amp; &#65;&#x42; &copy;"), "<b> & AB \u00a9")


class KnownDefectTests(unittest.TestCase):
    def test_M1_gt_inside_a_quoted_value_ends_the_tag(self):
        self.assertEqual(tokens('<a title="x>y">')[0], ("start", "a", (("title", "x"),)))

    def test_M2_references_decoded_inside_script(self):
        self.assertIn(("data", "&"), tokens("<script>&amp;</script>"))

    def test_M3_repeated_attributes_reported_twice(self):
        self.assertEqual(len(tokens("<a href=1 href=2>")[0][2]), 2)

    def test_M4_long_s_closes_a_script(self):
        self.assertEqual(tokens("<script>x</\u017fcript>y</script>")[:2], [("start", "script", ()), ("data", "xy")])

    def test_M5_nbsp_separates_attributes(self):
        self.assertEqual(tokens("<a\u00a0href=x>")[0], ("start", "a", (("href", "x"),)))

    def test_M6_tab_entity_not_decoded(self):
        self.assertEqual(tokens('<a href="java&Tab;script:x">')[0][2], (("href", "java&Tab;script:x"),))

    def test_M7_decoding_depends_on_feed_boundaries(self):
        whole = "".join(e[1] for e in tokens("a &amp; b") if e[0] == "data")
        split = "".join(e[1] for e in tokens("a &amp; b", chunk=5) if e[0] == "data")
        self.assertNotEqual(whole, split)

    def test_M8_tokenizing_time_grows_quadratically(self):
        def run(k):
            doc = '<p class="a">hello <b>world</b></p>\n' * k
            best = None
            was_enabled = gc.isenabled()
            gc.disable()
            try:
                for _ in range(2):
                    started = time.perf_counter()
                    tokens(doc)
                    elapsed = time.perf_counter() - started
                    best = elapsed if best is None or elapsed < best else best
            finally:
                if was_enabled:
                    gc.enable()
            return best
        run(500)
        small, large = run(4000), run(16000)
        # Four times the input: about 4x for linear code, about 16x for quadratic code.
        self.assertGreater(large / max(small, 1e-4), 7.0)


if __name__ == "__main__":
    unittest.main()
