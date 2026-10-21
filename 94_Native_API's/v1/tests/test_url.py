"""
File: v1/tests/test_url.py

Purpose
-------
Characterise v1/brisart_url.py: splitting, quoting and query handling
agree with urllib.parse on ordinary input, the RFC 3986 reference
resolutions v1 gets right resolve correctly, the embedded self-test
passes, and the known defects are pinned down.

Communication / relationships
-----------------------------
Standard library: unittest, urllib.parse (reference only), plus
support.py in this folder.
Verifies: v1/brisart_url.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
The RFC 3986 section 5.4 table is split: the 39 cases v1 resolves
correctly are asserted as correct, and the three it gets wrong (".",
".." and "./g/.") are asserted as defect U6.

Known limitations
-----------------
Generated URLs are well-formed; v1's handling of malformed authorities
is covered only by the defect tests.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_url.py
"""

import unittest
import urllib.parse as up

import support
import brisart_url
from brisart_url import (
    brisart_parse_qsl, brisart_quote, brisart_unquote, brisart_urlencode, brisart_urljoin, brisart_urlsplit)

BASE = "http://a/b/c/d;p?q"
RFC = {"g:h": "g:h", "g": "http://a/b/c/g", "./g": "http://a/b/c/g", "g/": "http://a/b/c/g/", "/g": "http://a/g",
       "//g": "http://g", "?y": "http://a/b/c/d;p?y", "g?y": "http://a/b/c/g?y", "#s": "http://a/b/c/d;p?q#s",
       "g#s": "http://a/b/c/g#s", "g?y#s": "http://a/b/c/g?y#s", ";x": "http://a/b/c/;x", "g;x": "http://a/b/c/g;x",
       "g;x?y#s": "http://a/b/c/g;x?y#s", "": "http://a/b/c/d;p?q", ".": "http://a/b/c/", "./": "http://a/b/c/",
       "..": "http://a/b/", "../": "http://a/b/", "../g": "http://a/b/g", "../..": "http://a/", "../../": "http://a/",
       "../../g": "http://a/g", "../../../g": "http://a/g", "../../../../g": "http://a/g", "/./g": "http://a/g",
       "/../g": "http://a/g", "g.": "http://a/b/c/g.", ".g": "http://a/b/c/.g", "g..": "http://a/b/c/g..",
       "..g": "http://a/b/c/..g", "./../g": "http://a/b/g", "./g/.": "http://a/b/c/g/", "g/./h": "http://a/b/c/g/h",
       "g/../h": "http://a/b/c/h", "g;x=1/./y": "http://a/b/c/g;x=1/y", "g;x=1/../y": "http://a/b/c/y",
       "g?y/./x": "http://a/b/c/g?y/./x", "g?y/../x": "http://a/b/c/g?y/../x", "g#s/./x": "http://a/b/c/g#s/./x",
       "g#s/../x": "http://a/b/c/g#s/../x", "http:g": "http:g"}
V1_WRONG = {".": "http://a/b/c", "..": "http://a/b", "./g/.": "http://a/b/c/g"}


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_url._self_test()

    def test_rfc3986_cases_v1_resolves_correctly(self):
        correct = {k: v for k, v in RFC.items() if k not in V1_WRONG}
        self.assertEqual(len(correct), 39)
        for ref, want in correct.items():
            self.assertEqual(brisart_urljoin(BASE, ref), want, ref)

    def test_split_matches_urllib_on_ordinary_urls(self):
        r = support.rng("v1-url")
        for _ in range(support.scaled(2000)):
            scheme = r.choice(["http", "https", ""])
            host = r.choice(["example.com", "EXAMPLE.org", "1.2.3.4", "[::1]"])
            url = (scheme + "://" if scheme else "//") + r.choice(["", "u@"]) + host + r.choice(["", ":80"]) + \
                r.choice(["", "/", "/a/b"]) + r.choice(["", "?a=1"]) + r.choice(["", "#f"])
            ours, theirs = brisart_urlsplit(url), up.urlsplit(url)
            self.assertEqual((ours.scheme, ours.netloc, ours.path, ours.query, ours.fragment), tuple(theirs), url)
            self.assertEqual(ours.hostname, theirs.hostname, url)

    def test_quote_unquote_and_query_parsing_match_urllib(self):
        r = support.rng("v1-quote")
        pool = [chr(i) for i in range(32, 0x250)] + ["\u20ac", "\U0001f600"]
        for _ in range(support.scaled(1500)):
            text = "".join(r.choice(pool) for _ in range(r.randint(0, 12)))
            self.assertEqual(brisart_quote(text), up.quote(text))
            self.assertEqual(brisart_unquote(up.quote(text)), text)
            query = "".join(r.choice(["a=1", "b=", "&", "x", "k=%20", "a+b=c"]) for _ in range(r.randint(0, 5)))
            self.assertEqual(brisart_parse_qsl(query, keep_blank_values=True), up.parse_qsl(query, keep_blank_values=True))
        self.assertEqual(brisart_urlencode([("a b", "c&d"), ("k", "\u00e9")]), up.urlencode([("a b", "c&d"), ("k", "\u00e9")]))


class KnownDefectTests(unittest.TestCase):
    def test_U1_U2_control_characters_hide_the_scheme(self):
        self.assertEqual(brisart_urlsplit("java\tscript:x").scheme, "")
        self.assertEqual(brisart_urlsplit(" javascript:x").scheme, "")

    def test_U3_unicode_case_folding_spoofs_a_host(self):
        self.assertEqual(brisart_urlsplit("http://\u212a.com/").hostname, "k.com")

    def test_U4_non_ascii_scheme_accepted(self):
        self.assertEqual(brisart_urlsplit("\u00e9x://a").scheme, "\u00e9x")

    def test_U5_lone_surrogate_quotes_like_a_question_mark(self):
        self.assertEqual(brisart_quote("\ud800"), brisart_quote("?"))

    def test_U6_trailing_slash_dropped_in_three_rfc_cases(self):
        for ref, wrong in V1_WRONG.items():
            self.assertEqual(brisart_urljoin(BASE, ref), wrong)
            self.assertNotEqual(wrong, RFC[ref])

    def test_U7_U8_urlencode_rejects_dicts_and_mangles_bytes(self):
        with self.assertRaises(ValueError):
            brisart_urlencode({"a": "b"})
        self.assertEqual(brisart_urlencode([("a", b"x y")]), "a=b%27x+y%27")

    def test_U9_no_query_field_limit(self):
        self.assertEqual(len(brisart_parse_qsl("&".join("a=1" for _ in range(5000)))), 5000)

    def test_U10_ambiguous_authority_resolves_to_a_host(self):
        self.assertEqual(brisart_urlsplit("http://good.com\\@evil.com/").hostname, "evil.com")


if __name__ == "__main__":
    unittest.main()
