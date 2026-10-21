"""
File: v3/tests/test_url.py

Purpose
-------
Verify v3/brisart_url.py against the RFC 3986 section 5.4 reference
table, urllib.parse on generated valid URLs and encodings, the host and
scheme attacks it is built to refuse, lossless split/unsplit round trips,
the v3 immutability of BrisartSplitResult and its replace() method, and
linear running time.

Communication / relationships
-----------------------------
Standard library: unittest, urllib.parse (reference only), plus
support.py in this folder.
Verifies: v3/brisart_url.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Every ASCII character is tried inside a host and inside userinfo; tabs
and newlines inside schemes; the Kelvin sign, long s and dotted capital I
in hosts and schemes.

Known limitations
-----------------
Agreement with urllib.parse is checked only where both are meant to
agree; deliberate differences have their own tests.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_url.py
"""

import unittest
import urllib.parse as up

import support
from brisart_url import (
    BrisartSplitResult, brisart_parse_qsl, brisart_quote, brisart_unquote, brisart_urlencode, brisart_urljoin,
    brisart_urlsplit, brisart_urlunsplit)

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


class ResolutionTests(unittest.TestCase):
    def test_rfc3986_section_5_4(self):
        self.assertEqual(len(RFC), 42)
        for ref, want in RFC.items():
            self.assertEqual(brisart_urljoin(BASE, ref), want, ref)

    def test_matches_urllib_on_ordinary_joins(self):
        for base in ("https://x.org/", "http://h/p/q/", "http://h/a?b", "file:///a/b/c"):
            for ref in ("g", "../g", "/g", "g?y", "?y", "x/./y", "//o/p", "https://z/q", "../../g"):
                self.assertEqual(brisart_urljoin(base, ref), up.urljoin(base, ref), (base, ref))


class SplitTests(unittest.TestCase):
    def test_components_and_helpers(self):
        p = brisart_urlsplit("HTTPS://user:pw@Example.COM:8080/a/b;c?x=1#frag")
        self.assertEqual(tuple(p), ("https", "user:pw@Example.COM:8080", "/a/b;c", "x=1", "frag"))
        self.assertEqual((p.hostname, p.port, p.geturl()), ("example.com", 8080, "https://user:pw@Example.COM:8080/a/b;c?x=1#frag"))

    def test_matches_urllib_for_generated_valid_urls(self):
        r = support.rng("url-diff")
        for _ in range(support.scaled(4000)):
            scheme = r.choice(["http", "https", "x-y.z+1", ""])
            host = r.choice(["example.com", "EXAMPLE.org", "[::1]", "1.2.3.4", ""])
            authority = ("//" + r.choice(["", "u@", "u:p@"]) + host + r.choice(["", ":80", ":65535"])) if host else ""
            path = r.choice(["", "/", "/a/b/", "/%7Euser", "/a;b=c"])
            url = (scheme + ":" if scheme else "") + authority + path + r.choice(["", "?a=1&b=2"]) + r.choice(["", "#f"])
            ours, theirs = brisart_urlsplit(url), up.urlsplit(url)
            self.assertEqual(tuple(ours), tuple(theirs), url)
            if host:
                self.assertEqual((ours.hostname, ours.port), (theirs.hostname, theirs.port), url)

    def test_round_trip_is_lossless(self):
        r = support.rng("url-rt")
        alphabet = list("ab1:/?#@[]%.\\ \t\n+-;=&") + ["http", "//", ".."]
        strip = "".join(chr(i) for i in range(33))
        for _ in range(support.scaled(10000)):
            url = "".join(r.choice(alphabet) for _ in range(r.randint(0, 14)))
            parts = brisart_urlsplit(url)
            self.assertEqual(brisart_urlsplit(brisart_urlunsplit(parts)), parts, repr(url))
            cleaned = url.strip(strip).translate({9: None, 10: None, 13: None})
            if parts.scheme or not cleaned.startswith(":"):
                expected = parts.scheme + cleaned[len(parts.scheme):] if parts.scheme else cleaned
                self.assertEqual(brisart_urlunsplit(parts), expected, repr(url))


class ImmutabilityTests(unittest.TestCase):
    def test_attributes_cannot_be_changed_or_deleted(self):
        p = brisart_urlsplit("http://a/b?c#d")
        for name in ("scheme", "netloc", "path", "query", "fragment", "has_query", "other"):
            with self.assertRaises(AttributeError):
                setattr(p, name, "x")
        with self.assertRaises(AttributeError):
            del p.path
        self.assertEqual(p.geturl(), "http://a/b?c#d")

    def test_hash_is_stable_for_dictionary_use(self):
        p = brisart_urlsplit("http://a/b")
        table = {p: 1}
        with self.assertRaises(AttributeError):
            p.path = "/changed"
        self.assertEqual(table[brisart_urlsplit("http://a/b")], 1)

    def test_replace(self):
        p = brisart_urlsplit("http://a/b?c#d")
        self.assertEqual(p.replace(path="/x").geturl(), "http://a/x?c#d")
        self.assertEqual(p.replace(query="").geturl(), "http://a/b#d")
        self.assertEqual(p.replace(query="", has_query=True).geturl(), "http://a/b?#d")
        self.assertEqual(p.replace(netloc="").geturl(), "http:/b?c#d")
        self.assertEqual(p.geturl(), "http://a/b?c#d")
        with self.assertRaises(TypeError):
            p.replace(port=80)
        with self.assertRaises(TypeError):
            p.replace(path=None)
        with self.assertRaises(TypeError):
            BrisartSplitResult("http", "a", 5, "", "")


class AttackTests(unittest.TestCase):
    def test_control_characters_cannot_hide_a_scheme(self):
        for url in ("java\tscript:alert(1)", "java\nscript:x", " javascript:x", "\x00javascript:x"):
            self.assertEqual(brisart_urlsplit(url).scheme, "javascript", repr(url))
        for url in ("jav\x0bascript:x", "jav ascript:x", "jav\u00e0script:x", "\u017fhttps://x"):
            self.assertNotEqual(brisart_urlsplit(url).scheme, "javascript")

    def test_ambiguous_authorities_are_refused(self):
        for url in ("http://good.com\\@evil.com/", "http://a@b@evil.com/", "http://ev il.com/", "http://a.com:80:90/",
                    "http://[::1/", "http://[]/", "http://a<b>.com/", "http://a%41.com/", "http://a.com\x7f/"):
            self.assertIsNone(brisart_urlsplit(url).hostname, url)
            with self.assertRaises(ValueError):
                brisart_urlsplit(url).port

    def test_userinfo_tricks_resolve_to_the_real_host(self):
        for url, host in (("http://good.com@evil.com/", "evil.com"), ("http://evil.com#@good.com/", "evil.com"),
                          ("http://evil.com/@good.com", "evil.com"), ("http://good.com%2f@evil.com/", "evil.com")):
            self.assertEqual(brisart_urlsplit(url).hostname, host, url)

    def test_ascii_only_case_folding(self):
        self.assertEqual(brisart_urlsplit("http://\u212a.com/").hostname, "\u212a.com")
        self.assertEqual(brisart_urlsplit("http://K.com/").hostname, "k.com")
        self.assertEqual("\u212a".lower(), "k")

    def test_every_ascii_character_in_host_and_userinfo(self):
        allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=")
        for code in range(128):
            char = chr(code)
            if char in "/?#@[]:":
                continue
            host = brisart_urlsplit("http://a%sb.com/" % char).hostname
            if char in allowed:
                self.assertEqual(host, ("a%sb.com" % char).lower())
            elif code in (9, 10, 13):
                self.assertEqual(host, "ab.com")
            else:
                self.assertIsNone(host, repr(char))

    def test_ports(self):
        self.assertEqual(brisart_urlsplit("http://a:65535/").port, 65535)
        for bad in ("http://a:65536/", "http://a:-1/", "http://a:\u0661/", "http://a:1e2/"):
            with self.assertRaises(ValueError):
                brisart_urlsplit(bad).port


class EncodingTests(unittest.TestCase):
    def test_quote_unquote_match_urllib(self):
        r = support.rng("url-quote")
        pool = [chr(i) for i in range(0, 0x250) if not 0xD800 <= i <= 0xDFFF] + ["\u20ac", "\U0001f600"]
        for _ in range(support.scaled(3000)):
            text = "".join(r.choice(pool) for _ in range(r.randint(0, 15)))
            for safe in ("/", ""):
                self.assertEqual(brisart_quote(text, safe=safe), up.quote(text, safe=safe))
            mixed = "".join(r.choice(["%41", "%C3%A9", "%ff", "%", "%4", "a", "\u00e9", "%zz"]) for _ in range(r.randint(0, 8)))
            self.assertEqual(brisart_unquote(mixed), up.unquote(mixed))

    def test_query_helpers_match_urllib(self):
        r = support.rng("url-qs")
        for _ in range(support.scaled(3000)):
            query = "".join(r.choice(["a=1", "b=", "=v", "&", "x", "k=%20", "a+b=c", ";"]) for _ in range(r.randint(0, 6)))
            for keep in (False, True):
                self.assertEqual(brisart_parse_qsl(query, keep_blank_values=keep), up.parse_qsl(query, keep_blank_values=keep))
        pairs = [("a b", "c&d"), ("k", "\u00e9"), ("n", 1), ("z", None), ("b", b"x y\xff")]
        self.assertEqual(brisart_urlencode(pairs), up.urlencode(pairs))
        self.assertEqual(brisart_urlencode(dict(pairs)), up.urlencode(dict(pairs)))
        with self.assertRaises(ValueError):
            brisart_parse_qsl("&".join("a=1" for _ in range(1001)))
        self.assertEqual(len(brisart_parse_qsl("&".join("a=1" for _ in range(1000)))), 1000)
        with self.assertRaises(ValueError):
            brisart_quote("\ud800")


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        from brisart_url import _remove_dot_segments
        for unit in ("/./", "/../", "../", "/a/../"):
            support.assert_roughly_linear(self, lambda k, u=unit: u * (40_000 * k), _remove_dot_segments)
        support.assert_roughly_linear(self, lambda k: "%41" * (60_000 * k), brisart_unquote)
        support.assert_roughly_linear(self, lambda k: " " * (150_000 * k) + "http://a/", brisart_urlsplit)


if __name__ == "__main__":
    unittest.main()
