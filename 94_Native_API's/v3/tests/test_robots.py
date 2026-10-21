"""
File: v3/tests/test_robots.py

Purpose
-------
Verify v3/brisart_robots.py against RFC 9309 semantics and Google's
published path-matching examples, against urllib.robotparser where the
two algorithms must agree, against hostile input (catastrophic
backtracking patterns, oversized files, URL control characters), and the
v3 change that the size budget counts UTF-8 bytes for every input form.

Communication / relationships
-----------------------------
Standard library: unittest, urllib.robotparser (reference only), plus
support.py in this folder.
Verifies: v3/brisart_robots.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
The differential test uses robots files whose rules cannot overlap, so
first-match and longest-match must agree; overlap, wildcards and group
merging have explicit tests.

Known limitations
-----------------
No third-party RFC 9309 implementation is run; expectations come from the
RFC and Google's examples.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_robots.py
"""

import unittest
import urllib.robotparser as stdlib_robots

import support
from brisart_robots import MAX_PATH_LENGTH, BrisartRobotsPolicy

UA = "BrisartAI/1.0 (+https://example.org/bot)"


def policy(text, **kw):
    p = BrisartRobotsPolicy(**kw)
    p.parse(text)
    return p


def allowed(text, path, agent=UA):
    return policy(text).can_fetch(agent, "https://example.com" + path)


class MatchingTests(unittest.TestCase):
    def check(self, rule, blocked, open_):
        text = "user-agent: *\ndisallow: %s\n" % rule
        for path in blocked:
            self.assertFalse(allowed(text, path), (rule, path))
        for path in open_:
            self.assertTrue(allowed(text, path), (rule, path))

    def test_google_path_examples(self):
        self.check("/fish", ["/fish", "/fish.html", "/fishheads/yummy.html", "/fish.php?id=x"], ["/Fish.asp", "/catfish", "/?id=fish"])
        self.check("/fish/", ["/fish/", "/fish/salmon.htm"], ["/fish", "/fish.html"])
        self.check("/*.php", ["/filename.php", "/folder/any.php.file.html"], ["/", "/windows.PHP"])
        self.check("/*.php$", ["/filename.php", "/folder/filename.php"], ["/filename.php?x", "/filename.php/", "/filename.php5"])
        self.check("/fish*.php", ["/fish.php", "/fishheads/catfish.php?x"], ["/Fish.PHP"])

    def test_precedence(self):
        self.assertTrue(allowed("user-agent: *\nallow: /p\ndisallow: /\n", "/page"))
        self.assertTrue(allowed("user-agent: *\nallow: /folder\ndisallow: /folder\n", "/folder/page"))
        self.assertFalse(allowed("user-agent: *\nallow: /page\ndisallow: /*.htm\n", "/page.htm"))
        self.assertTrue(allowed("user-agent: *\nallow: /$\ndisallow: /\n", "/"))
        self.assertFalse(allowed("user-agent: *\nallow: /$\ndisallow: /\n", "/page.htm"))
        for text in ("user-agent: *\ndisallow: /a\nallow: /a/b\n", "user-agent: *\nallow: /a/b\ndisallow: /a\n"):
            self.assertTrue(allowed(text, "/a/b/c"))
            self.assertFalse(allowed(text, "/a/x"))


class GroupTests(unittest.TestCase):
    def test_groups(self):
        text = "user-agent: *\ndisallow: /\n\nuser-agent: brisartai\nallow: /\n"
        self.assertTrue(allowed(text, "/x", UA))
        self.assertFalse(allowed(text, "/x", "Other/1"))
        self.assertTrue(allowed("user-agent: bot\ndisallow: /\n", "/x", "Googlebot/2.1"))       # exact token, not substring
        self.assertFalse(allowed("user-agent: *\n\n# c\ndisallow: /a\n", "/a"))                  # blank line keeps the group
        merged = "user-agent: brisartai\ndisallow: /a\n\nuser-agent: x\ndisallow: /o\n\nuser-agent: BrisartAI\ndisallow: /b\n"
        self.assertFalse(allowed(merged, "/a"))
        self.assertFalse(allowed(merged, "/b"))
        self.assertTrue(allowed(merged, "/o"))

    def test_status_handling(self):
        for status in (429, 500, 503, 0, 999):
            self.assertFalse(BrisartRobotsPolicy.for_status(status, "user-agent: *\nallow: /\n").can_fetch(UA, "/"))
        for status in (301, 401, 403, 404, 410):
            self.assertTrue(BrisartRobotsPolicy.for_status(status).can_fetch(UA, "/x"))
        self.assertFalse(BrisartRobotsPolicy.for_status(200, "user-agent: *\ndisallow: /p\n").can_fetch(UA, "/p"))

    def test_crawl_delay(self):
        self.assertEqual(policy("user-agent: *\ncrawl-delay: 2.5\n").crawl_delay(UA), 2.5)
        for value in ("abc", "-1", "1e3", "\u0663", "NaN"):
            self.assertIsNone(policy("user-agent: *\ncrawl-delay: %s\n" % value).crawl_delay(UA))
        self.assertEqual(policy("user-agent: *\ncrawl-delay: 99999999\n").crawl_delay(UA), 86400.0)


class NormalisationTests(unittest.TestCase):
    def test_percent_encoding(self):
        self.assertFalse(allowed("user-agent: *\ndisallow: /~user\n", "/%7Euser"))
        self.assertFalse(allowed("user-agent: *\ndisallow: /caf\u00e9\n", "/caf%C3%A9"))
        self.assertTrue(allowed("user-agent: *\ndisallow: /a/b\n", "/a%2Fb"))
        self.assertTrue(allowed("user-agent: *\ndisallow: /a?b\n", "/a%3Fb"))

    def test_control_characters_cannot_smuggle(self):
        for url in ("/ad\tmin", "/ad\nmin", "/ad\rmin", "  /admin"):
            self.assertFalse(policy("user-agent: *\ndisallow: /admin\n").can_fetch(UA, url), repr(url))


class BudgetTests(unittest.TestCase):
    def test_budget_counts_utf8_bytes_for_every_input_form(self):
        line = "disallow: /\u20ac\u20ac\u20ac\n"                     # 15 characters, 21 UTF-8 bytes
        text = "user-agent: *\n" + line * 100
        budget = 14 + 21 * 10 + 5                                     # ten whole rules and part of an eleventh
        for source in (text, text.encode("utf-8"), text.splitlines()):
            p = BrisartRobotsPolicy(max_bytes=budget)
            p.parse(source)
            self.assertTrue(p.truncated, type(source))
            self.assertEqual(p.rule_count, 10, type(source))

    def test_a_line_cut_by_the_budget_is_dropped_not_shortened(self):
        text = "user-agent: *\ndisallow: /\nallow: /public/reports/only\n"
        p = BrisartRobotsPolicy(max_bytes=len(text) - 15)            # cuts "allow: /public/r..."
        p.parse(text)
        self.assertTrue(p.truncated)
        self.assertEqual(p.rule_count, 1)
        self.assertFalse(p.can_fetch(UA, "/public/x"))                 # a shortened Allow would have opened this

    def test_rule_and_path_limits(self):
        p = policy("user-agent: *\n" + "".join("disallow: /p%d\n" % i for i in range(20000)))
        self.assertEqual(p.rule_count, 10000)
        self.assertTrue(p.truncated)
        self.assertFalse(BrisartRobotsPolicy().can_fetch(UA, "/" + "x" * MAX_PATH_LENGTH))


class DifferentialTests(unittest.TestCase):
    def test_non_overlapping_rules_agree_with_urllib(self):
        r = support.rng("robots-diff")
        segments = ["a", "b", "private", "tmp", "img", "docs"]
        for _ in range(support.scaled(800)):
            lines = ["User-agent: " + a for a in r.choice([["*"], ["brisartai"], ["brisartai", "*"]])]
            for seg in r.sample(segments, r.randint(1, 4)):
                lines.append("%s: /%s%s" % (r.choice(["Disallow", "Allow"]), seg, r.choice(["", "/", "/sub"])))
            text = "\n".join(lines) + "\n"
            ours = policy(text)
            theirs = stdlib_robots.RobotFileParser()
            theirs.parse(text.splitlines())
            for _ in range(6):
                path = "/" + r.choice(segments + ["zzz"]) + r.choice(["", "/", "/sub/page", ".html"])
                for agent in ("BrisartAI/1.0", "Other/2"):
                    self.assertEqual(ours.can_fetch(agent, "http://h" + path), theirs.can_fetch(agent, "http://h" + path),
                                     (text, path, agent))


class ResourceTests(unittest.TestCase):
    def test_backtracking_patterns_are_linear(self):
        for pattern in ("/" + "*a" * 2000 + "b$", "/*" * 2000 + "x$"):
            p = policy("user-agent: *\ndisallow: %s\n" % pattern)
            support.assert_roughly_linear(self, lambda k: "/" + "a" * (2000 * k), lambda path: p.can_fetch(UA, path))

    def test_parse_is_linear(self):
        support.assert_roughly_linear(self, lambda k: "user-agent: *\n" + "".join("disallow: /p%d\n" % i for i in range(1500 * k)),
                                      lambda t: BrisartRobotsPolicy().parse(t))


if __name__ == "__main__":
    unittest.main()
