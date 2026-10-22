"""
File: v1/tests/test_robots.py

Purpose
-------
Characterise v1/brisart_robots.py: the embedded self-test passes; empty
policies allow access; and the decisions that RFC 9309 (and v2) treat
differently are pinned down as known defects.

Communication / relationships
-----------------------------
Standard library: unittest.
support.py in this folder installs the brisart_ai.native package stand-in
v1 robots imports at call time.
Verifies: v1/brisart_robots.py.

Settings / parameters
---------------------
No configurable test parameters are used directly by this file.

Edge cases
----------
Known v1 behavior is pinned for literal wildcard and anchor handling,
first-match rule selection, substring agent matching, blank-line group
handling, encoded question marks, and tab characters inside URLs.

Known limitations
-----------------
This file characterises the frozen v1 behavior directly and does not
compare decisions against the currently installed urllib.robotparser.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_robots.py
"""

import unittest

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
