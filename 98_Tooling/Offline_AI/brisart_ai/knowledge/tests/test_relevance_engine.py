r"""
File: brisart_ai/knowledge/tests/test_relevance_engine.py

Purpose
-------
Exercise term weights, shape and proximity behavior.

Protected scenarios: TestRarityWeight verifies zero document frequency returns zero;
TestRarityWeight verifies zero total documents returns zero; TestRarityWeight verifies
common term gets lowest tier; TestRarityWeight verifies distinctive term gets highest
tier; TestRarityWeight verifies tier boundaries are fixed regardless of scale.

Protected scenarios: TestPresencePoints verifies zero occurrences is zero;
TestPresencePoints verifies single occurrence gets baseline; TestPresencePoints verifies
many occurrences capped; TestPresencePoints verifies more occurrences never scores
lower; TestTermContribution verifies combines presence and rarity.

Protected scenarios: TestShapeMultiplier verifies zero average length returns neutral;
TestShapeMultiplier verifies typical length gets full credit; TestShapeMultiplier
verifies short document is boosted above neutral; TestShapeMultiplier verifies long
document is diluted; TestShapeMultiplier verifies much longer document diluted more than
slightly longer.

Protected scenarios: TestProximityBonus verifies single term returns neutral;
TestProximityBonus verifies no terms returns neutral; TestProximityBonus verifies terms
close together get bonus; TestProximityBonus verifies terms far apart get no bonus;
TestProximityBonus verifies bonus is capped.

Protected scenarios: TestProximityBonus verifies terms matched case insensitively.

Communication / relationships
-----------------------------
Uses small explicit scored token and text examples.

Direct project imports: brisart_ai.knowledge.relevance_engine.

The cases use self.assertEqual, self.assertLessEqual, self.assertGreater,
self.assertLess, self.assertTrue to check returned values, persisted state or raised
errors. The suite is run through scripts/run_tests.py so Native API discovery happens
before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Near, distant and absent terms plus capped repetition.

Regression coverage includes TestProximityBonus.test_single_term_returns_neutral,
TestProximityBonus.test_no_terms_returns_neutral,
TestProximityBonus.test_terms_close_together_get_bonus,
TestProximityBonus.test_terms_far_apart_get_no_bonus,
TestProximityBonus.test_bonus_is_capped,
TestProximityBonus.test_terms_matched_case_insensitively.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_relevance_engine.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_relevance_engine.py
-k test_zero_total_documents_returns_zero.
"""

import unittest
from brisart_ai.knowledge.relevance_engine import (
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


if __name__ == "__main__":
    unittest.main()
