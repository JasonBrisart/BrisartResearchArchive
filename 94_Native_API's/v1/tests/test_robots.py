"""
File: v1/tests/test_robots.py

Purpose
-------
Characterise v1/brisart_robots.py: it implements the same 1994 algorithm
as urllib.robotparser (first matching rule, literal prefixes, substring
agent match), so on ordinary files its decisions agree with the standard
library; the embedded self-test passes; and the decisions that RFC 9309
(and v2) treat differently are pinned down as known defects.

Communication / relationships
-----------------------------
Standard library: unittest, urllib.robotparser (reference only), plus
support.py in this folder, which installs the brisart_ai.native package
stand-in v1 robots imports at call time.
Verifies: v1/brisart_robots.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Generated files avoid percent-encoded rules and wildcards, where v1
unquotes differently from urllib.robotparser.

Known limitations
-----------------
Agreement is sampled on generated files, not proven.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_robots.py
"""

import unittest
import urllib.robotparser as stdlib_robots

import support
import brisart_robots
from brisart_robots import BrisartRobotsPolicy


def policy(text):
    p = BrisartRobotsPolicy()
    p.parse(text.splitlines())
    return p


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_robots._self_test()

    def test_decisions_match_urllib_robotparser(self):
        r = support.rng("v1-robots")
        segments = ["a", "b", "private", "tmp", "docs"]
        for _ in range(support.scaled(500)):
            lines = []
            for _ in range(r.randint(1, 3)):
                for agent in r.choice([["*"], ["brisartai"], ["otherbot"], ["brisartai", "otherbot"]]):
                    lines.append("User-agent: " + agent)
                for _ in range(r.randint(1, 4)):
                    lines.append("%s: /%s%s" % (r.choice(["Disallow", "Allow"]), r.choice(segments), r.choice(["", "/", "/x"])))
                if r.random() < 0.3:
                    lines.append("Crawl-delay: %d" % r.randint(0, 9))
                lines.append("")
            text = "\n".join(lines)
            ours = policy(text)
            theirs = stdlib_robots.RobotFileParser()
            theirs.parse(text.splitlines())
            for agent in ("BrisartAI/1.0", "OtherBot/2", "Nobody/3"):
                self.assertEqual(ours.crawl_delay(agent), theirs.crawl_delay(agent), text)
                for _ in range(5):
                    url = "http://h/" + r.choice(segments + ["z"]) + r.choice(["", "/", "/x", "/x/y"])
                    self.assertEqual(ours.can_fetch(agent, url), theirs.can_fetch(agent, url), (text, agent, url))

    def test_empty_policy_allows_everything(self):
        self.assertTrue(policy("").can_fetch("Any/1", "http://h/anything"))


class KnownDefectTests(unittest.TestCase):
    def test_R1_wildcards_and_anchor_are_literal(self):
        self.assertTrue(policy("User-agent: *\nDisallow: /*.pdf$\n").can_fetch("x", "http://h/a.pdf"))

    def test_R2_first_match_wins_over_a_longer_allow(self):
        self.assertFalse(policy("User-agent: *\nDisallow: /a\nAllow: /a/b\n").can_fetch("x", "http://h/a/b/c"))

    def test_R3_agent_names_match_by_substring(self):
        self.assertFalse(policy("User-agent: bot\nDisallow: /\n").can_fetch("Googlebot/2.1", "http://h/x"))

    def test_R4_blank_line_discards_a_group(self):
        self.assertTrue(policy("User-agent: *\n\nDisallow: /a\n").can_fetch("x", "http://h/a"))

    def test_R5_encoded_question_mark_becomes_a_delimiter(self):
        self.assertFalse(policy("User-agent: *\nDisallow: /a?b\n").can_fetch("x", "http://h/a%3Fb"))

    def test_R6_tab_inside_the_url_slips_past_a_rule(self):
        self.assertTrue(policy("User-agent: *\nDisallow: /admin\n").can_fetch("x", "/ad\tmin"))


if __name__ == "__main__":
    unittest.main()
