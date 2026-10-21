"""
File: v3/tests/test_v2_compat.py

Purpose
-------
Show that v3 changes nothing it does not announce: for the seven modules
v3 inherits from v2, the same random and hostile inputs must give the
same result (or an exception of the same class) from both versions,
except for the inputs covered by the documented v3 changes.

Communication / relationships
-----------------------------
Standard library: unittest, importlib.util, json, zlib, pathlib, plus
support.py in this folder.
Verifies: v3/brisart_codec.py, brisart_hash.py, brisart_inflate.py,
brisart_json.py, brisart_markup.py, brisart_robots.py and brisart_url.py
against the files in the sibling v2/ folder. Skipped if v2/ is absent.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Robots budgets are left at their default and inputs are ASCII so the
v3 UTF-8 budget change does not apply; URL results are compared through
their public values, not object identity, because v3 results are
immutable.

Known limitations
-----------------
Equivalence is sampled, not proven.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_v2_compat.py
"""

import importlib.util
import json
import unittest
import zlib
from pathlib import Path

import support

V2 = Path(__file__).resolve().parents[2] / "v2"
NAMES = ("codec", "hash", "inflate", "json", "markup", "robots", "url")


def load(folder, prefix):
    modules = {}
    for name in NAMES:
        spec = importlib.util.spec_from_file_location(prefix + name, Path(folder) / ("brisart_%s.py" % name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def outcome(function):
    try:
        return ("ok", function())
    except Exception as error:
        return ("err", type(error).__name__)


@unittest.skipUnless(V2.is_dir(), "v2/ folder not present")
class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = load(V2, "compat_v2_")
        cls.new = load(support.V3, "compat_v3_")

    def same(self, call, *args, **kw):
        a = outcome(lambda: call(self.old, *args, **kw))
        b = outcome(lambda: call(self.new, *args, **kw))
        self.assertEqual(a, b, (args, kw))

    def test_codec(self):
        r = support.rng("compat-codec")
        for _ in range(support.scaled(2000)):
            blob = support.random_bytes(r, r.randint(0, 30))
            text = "".join(r.choice("ABCabc+/=-_ \n!") for _ in range(r.randint(0, 16)))
            self.same(lambda m, x: m["codec"].brisart_b64encode(x), blob)
            for kw in ({}, {"urlsafe": True}, {"allow_whitespace": True}, {"padding": "required"}):
                self.same(lambda m, x, k=kw: m["codec"].brisart_b64decode(x, **k), text)

    def test_hash(self):
        r = support.rng("compat-hash")
        for _ in range(support.scaled(60)):
            blob = support.random_bytes(r, r.randint(0, 300))
            self.same(lambda m, x: m["hash"].brisart_sha256(x).hexdigest(), blob)
            self.same(lambda m, x: m["hash"].brisart_stable_hash(x), blob.decode("latin-1"))

    def test_inflate(self):
        r = support.rng("compat-inflate")
        for _ in range(support.scaled(800)):
            data = support.random_bytes(r, r.randint(0, 200)) + b"abc" * r.randint(0, 100)
            stream = bytearray(zlib.compress(data, r.randint(0, 9)))
            if r.random() < 0.7 and stream:
                stream[r.randrange(len(stream))] ^= 1 << r.randrange(8)
            for kw in ({}, {"max_output": 50}, {"allow_trailing": True}, {"verify_checksum": False}):
                self.same(lambda m, x, k=kw: m["inflate"].brisart_zlib_decompress(x, **k), bytes(stream))

    def test_json(self):
        r = support.rng("compat-json")
        alphabet = list('{}[],:"\\ -.e01tfnul') + ["true", "\\u00e9"]
        for _ in range(support.scaled(3000)):
            doc = json.dumps({"a": [1, 2.5, None, "x\u00e9"], "b": {"c": True}})
            for _ in range(r.randint(0, 3)):
                i = r.randrange(len(doc) + 1)
                doc = doc[:i] + r.choice(alphabet) + doc[i + 1:]
            for kw in ({}, {"duplicate_keys": "last"}, {"allow_nan": True}):
                self.same(lambda m, x, k=kw: m["json"].brisart_loads(x, **k), doc)
                self.same(lambda m, x, k=kw: m["json"].brisart_loads(x.encode(), **k), doc)
            self.same(lambda m: m["json"].brisart_dumps([doc, {"k": [1, None]}], indent=2, sort_keys=True))

    def test_markup(self):
        r = support.rng("compat-markup")
        pieces = ["<", "</", "<!--", "-->", "<a href='x>y'>", "&amp;", "&copy", "<script>", "</script>", "<title>",
                  "text", " ", "\n", '"', "=", "<br/>", "<!DOCTYPE html>"]

        def run(m, text):
            events = []

            class P(m["markup"].BrisartMarkupParser):
                def handle_starttag(self, tag, attrs):
                    events.append(("s", tag, tuple(attrs)))

                def handle_endtag(self, tag):
                    events.append(("e", tag))

                def handle_data(self, data):
                    events.append(("d", data))

                def handle_comment(self, data):
                    events.append(("c", data))

            p = P()
            p.feed(text)
            p.close()
            return events
        for _ in range(support.scaled(1500)):
            self.same(run, "".join(r.choice(pieces) for _ in range(r.randint(0, 20))))

    def test_robots(self):
        r = support.rng("compat-robots")
        lines = ["user-agent: *", "user-agent: brisartai", "disallow: /a", "allow: /a/b", "disallow: /*.pdf$",
                 "crawl-delay: 2", "", "# c", "disallow: /p?x=1"]
        for _ in range(support.scaled(800)):
            text = "\n".join(r.choice(lines) for _ in range(r.randint(0, 8)))
            for url in ("/", "/a", "/a/b/c", "/x.pdf", "/p?x=1", "/%7Ea"):
                def check(m, t=text, u=url):
                    p = m["robots"].BrisartRobotsPolicy()
                    p.parse(t)
                    return p.can_fetch("BrisartAI/1.0", u), p.crawl_delay("BrisartAI/1.0"), p.rule_count, p.truncated
                self.same(check)

    def test_url(self):
        r = support.rng("compat-url")
        alphabet = list("ab1:/?#@[]%.\\ \t+-;=&") + ["http", "//", "..", "%41"]
        for _ in range(support.scaled(3000)):
            a = "".join(r.choice(alphabet) for _ in range(r.randint(0, 14)))
            b = "".join(r.choice(alphabet) for _ in range(r.randint(0, 10)))

            def split(m, x=a):
                p = m["url"].brisart_urlsplit(x)
                port = outcome(lambda: p.port)
                return tuple(p), p.hostname, port, p.geturl()
            self.same(split)
            self.same(lambda m: m["url"].brisart_urljoin(a, b))
            self.same(lambda m: m["url"].brisart_quote(a))
            self.same(lambda m: m["url"].brisart_unquote(a))
            self.same(lambda m: m["url"].brisart_parse_qsl(a, keep_blank_values=True))


if __name__ == "__main__":
    unittest.main()
