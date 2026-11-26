"""
File: brisart_ai/knowledge/tests/test_relevance_engine.py

Purpose
-------
Verify passage coverage, proximity, windowing and evidence scoring.

This regression test module defines `TestRarityWeight`, `TestPresencePoints`,
`TestTermContribution`, `TestShapeMultiplier`, `TestProximityBonus`. Its scope is deliberately
limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Its fixtures and assertions describe observable behavior without
changing the installed application.

Communication / relationships
-----------------------------
Calls the Brisart evidence engine directly rather than through the answer renderer.

The direct in-project imports visible in this module are
`brisart_ai.knowledge.relevance_engine`. Test methods
`test_zero_document_frequency_returns_zero`, `test_zero_total_documents_returns_zero`,
`test_common_term_gets_lowest_tier`, `test_distinctive_term_gets_highest_tier`,
`test_tier_boundaries_are_fixed_regardless_of_scale`; this identifies where behavior is
invoked without implying a separate hidden dependency. The test runner supplies the test
lifecycle and any temporary fixtures.

Settings / parameters
---------------------
Exercises fixed passages and bounded candidate scoring.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Scattered concepts, unrelated text, numeric answers, and comparative and causal cues.

The behaviors documented above must be read together with the actual branches in
test_relevance_engine.py; assertions should reject regressions rather than merely checking
file layout. Error handling, input validation, and early returns remain the responsibility of
the concrete functions in this module. No additional fallback is created by this
documentation.

Known limitations
-----------------
Small fixtures are not a full-archive benchmark.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_relevance_engine.py -q

For a concrete entry point, inspect `TestRarityWeight`, `TestPresencePoints`,
`TestTermContribution`, `TestShapeMultiplier`, `TestProximityBonus`; run this module through
the existing project test runner with its actual test path. The example above is illustrative
of this file's present interface; do not treat it as an instruction to create additional state
or call private functions directly.
"""

import unittest
from brisart_ai.knowledge.relevance_engine import (
    sentence_score,
    presence_points, proximity_bonus, rarity_weight, shape_multiplier, term_contribution,
)


class TestRarityWeight(unittest.TestCase):
    def test_zero_document_frequency_returns_zero(self):
        self.assertEqual(rarity_weight(0, 100), 0.0)

    def test_zero_total_documents_returns_zero(self):
        self.assertEqual(rarity_weight(5, 0), 0.0)

    def test_common_term_gets_lowest_tier(self):
        # 25% share -> "common" tier (weight 0.4)
        self.assertEqual(rarity_weight(25, 100), 0.4)

    def test_distinctive_term_gets_highest_tier(self):
        # under 1% share -> "distinctive" tier (weight 2.6)
        self.assertEqual(rarity_weight(1, 1000), 2.6)

    def test_tier_boundaries_are_fixed_regardless_of_scale(self):
        # Same share (5%) should give same weight regardless of corpus size.
        self.assertEqual(rarity_weight(5, 100), rarity_weight(500, 10000))


class TestPresencePoints(unittest.TestCase):
    def test_zero_occurrences_is_zero(self):
        self.assertEqual(presence_points(0), 0.0)

    def test_single_occurrence_gets_baseline(self):
        self.assertEqual(presence_points(1), 1.0)

    def test_many_occurrences_capped(self):
        # Going from 8 to 800 occurrences should not increase the score further.
        self.assertEqual(presence_points(8), presence_points(800))

    def test_more_occurrences_never_scores_lower(self):
        self.assertLessEqual(presence_points(1), presence_points(2))
        self.assertLessEqual(presence_points(2), presence_points(4))
        self.assertLessEqual(presence_points(4), presence_points(8))


class TestTermContribution(unittest.TestCase):
    def test_combines_presence_and_rarity(self):
        expected = presence_points(3) * rarity_weight(2, 100)
        self.assertEqual(term_contribution(3, 2, 100), expected)


class TestShapeMultiplier(unittest.TestCase):
    def test_zero_average_length_returns_neutral(self):
        self.assertEqual(shape_multiplier(100, 0), 1.0)

    def test_typical_length_gets_full_credit(self):
        self.assertEqual(shape_multiplier(100, 100), 1.00)

    def test_short_document_is_boosted_above_neutral(self):
        # Unlike BM25, a notably short document is boosted, not just spared.
        self.assertGreater(shape_multiplier(10, 100), 1.0)

    def test_long_document_is_diluted(self):
        self.assertLess(shape_multiplier(300, 100), 1.0)

    def test_much_longer_document_diluted_more_than_slightly_longer(self):
        self.assertLess(shape_multiplier(300, 100), shape_multiplier(160, 100))


class TestProximityBonus(unittest.TestCase):
    def test_single_term_returns_neutral(self):
        bonus, signals = proximity_bonus("some text here", ["term"])
        self.assertEqual(bonus, 1.0)
        self.assertEqual(signals, [])

    def test_no_terms_returns_neutral(self):
        bonus, signals = proximity_bonus("some text here", [])
        self.assertEqual(bonus, 1.0)

    def test_terms_close_together_get_bonus(self):
        text = "the quick brown fox jumps"
        bonus, signals = proximity_bonus(text, ["quick", "fox"])
        self.assertGreater(bonus, 1.0)
        self.assertTrue(any("proximity" in s for s in signals))

    def test_terms_far_apart_get_no_bonus(self):
        text = "quick " + ("filler word " * 50) + "fox"
        bonus, signals = proximity_bonus(text, ["quick", "fox"])
        self.assertEqual(bonus, 1.0)

    def test_bonus_is_capped(self):
        # Many overlapping close terms should not exceed the documented cap.
        text = "alpha beta gamma delta epsilon zeta"
        bonus, _signals = proximity_bonus(text, ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"])
        self.assertLessEqual(bonus, 1.6)  # 1.0 + PROXIMITY_BONUS_CAP (0.6)

    def test_terms_matched_case_insensitively(self):
        text = "Quick Brown FOX"
        bonus, _signals = proximity_bonus(text, ["quick", "fox"])
        self.assertGreater(bonus, 1.0)


class TestSentenceScore(unittest.TestCase):
    def test_no_overlap_scores_zero(self):
        self.assertEqual(sentence_score("completely unrelated content here", {"zebra"}), 0.0)

    def test_overlap_scores_positive(self):
        self.assertGreater(sentence_score("the zebra ran quickly across the field", {"zebra"}), 0.0)

    def test_quantity_mode_boosts_numeric_sentence(self):
        numeric = sentence_score("an estimated 73.8 million cats live here", {"cats"}, quantity_mode=True)
        non_numeric = sentence_score("cats are generally independent animals", {"cats"}, quantity_mode=True)
        self.assertGreater(numeric, non_numeric)

    def test_comparison_mode_boosts_comparative_sentence(self):
        comparative = sentence_score("dogs usually outlive cats in captivity", {"dogs", "cats"}, comparison_mode=True)
        plain = sentence_score("dogs and cats are both popular pets", {"dogs", "cats"}, comparison_mode=True)
        self.assertGreater(comparative, plain)

    def test_reason_mode_boosts_causal_sentence(self):
        causal = sentence_score("cats purr because of muscle twitching in the larynx", {"cats", "purr"}, reason_mode=True)
        plain = sentence_score("cats purr often while resting comfortably", {"cats", "purr"}, reason_mode=True)
        self.assertGreater(causal, plain)


if __name__ == "__main__":
    unittest.main()
