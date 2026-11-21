"""
File: brisart_ai/knowledge/tests/test_ranker.py

Purpose
-------
Tests for brisart_ai/knowledge/ranker.py -- retrieval and intent-aware ranking.

Communication / relationships
-----------------------------
Direct module imports: tempfile, unittest, pathlib, brisart_ai.knowledge.index, brisart_ai.knowledge.ranker.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Run this test file with the project-scoped test runner.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ranker import (
    generic_concept_title_adjust, phrase_match_adjust, search, title_match_adjust,
)


class TestSearch(unittest.TestCase):
    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_empty_query_returns_no_results(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello world")
            self.assertEqual(search(idx, ""), [])
            idx.close()

    def test_no_matching_documents_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello world")
            self.assertEqual(search(idx, "zzzznonexistentterm"), [])
            idx.close()

    def test_matching_document_is_returned(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="the giraffe is tall")
            results = search(idx, "giraffe")
            self.assertEqual(len(results), 1)
            self.assertIn("giraffe", results[0]["text"])
            idx.close()

    def test_source_types_filter_restricts_scope(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="unique zephyr content")
            idx.add_source(source_type="web", location="https://x.com", title="X", text="unique zephyr content")
            file_only = search(idx, "zephyr", source_types={"file"})
            self.assertEqual(len(file_only), 1)
            self.assertEqual(file_only[0]["source_type"], "file")
            idx.close()

    def test_founder_intent_ranks_history_above_product_page(self):
        # The classic regression case: "who invented microsoft?" should
        # rank a founder/history document above a product manual page.
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/powerpoint.txt", title="Microsoft PowerPoint",
                text="Microsoft PowerPoint is a presentation program. Slides can include text and images. "
                     "Available for Windows and macOS. Use the ribbon to change slide layout.")
            idx.add_source(source_type="file", location="/history.txt", title="History of Microsoft",
                text="Microsoft was founded by Bill Gates and Paul Allen on April 4, 1975, in Albuquerque, "
                     "New Mexico. The two co-founders had previously written a BASIC interpreter.")
            results = search(idx, "who invented microsoft?")
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "History of Microsoft")
            idx.close()

    def test_statistic_intent_finds_numeric_content(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/breeds.txt", title="Cat breeds",
                text="There are many recognised cat breeds like the Siamese and Persian.")
            idx.add_source(source_type="file", location="/stats.txt", title="Pet cat population statistics",
                text="An estimated 73.8 million pet cats live in the United States according to survey data.")
            results = search(idx, "how many cats are in america?")
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0]["title"], "Pet cat population statistics")
            idx.close()

    def test_result_documents_have_expected_fields(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="unique searchable term xyzzy")
            results = search(idx, "xyzzy")
            doc = results[0]
            for field in ("id", "score", "source_type", "location", "title", "text", "intent", "intent_boosts", "intent_penalties"):
                self.assertIn(field, doc)
            idx.close()

    def test_limit_is_respected(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            for i in range(10):
                idx.add_source(source_type="file", location=f"/doc{i}.txt", title=f"Doc {i}",
                    text=f"this document number {i} discusses widgets extensively")
            results = search(idx, "widgets", limit=3)
            self.assertLessEqual(len(results), 3)
            idx.close()


class TestTitleMatchAdjust(unittest.TestCase):
    def test_no_title_returns_neutral(self):
        factor, signals = title_match_adjust("", {"cats"})
        self.assertEqual(factor, 1.0)
        self.assertEqual(signals, [])

    def test_matching_title_term_boosts(self):
        factor, signals = title_match_adjust("All About Cats", {"cats"})
        self.assertGreater(factor, 1.0)
        self.assertTrue(len(signals) > 0)

    def test_generic_verb_damped(self):
        # "explain" should contribute far less than a specific term of
        # equal rarity, per GENERIC_TERM_DAMPING.
        damped_factor, _s1 = title_match_adjust("Explain Something", {"explain"})
        normal_factor, _s2 = title_match_adjust("Zebra Something", {"zebra"})
        self.assertLess(damped_factor - 1.0, normal_factor - 1.0)


class TestGenericConceptTitleAdjust(unittest.TestCase):
    def test_bare_generic_title_penalized(self):
        factor, signals = generic_concept_title_adjust("Law", "/wiki/Law")
        self.assertLess(factor, 1.0)
        self.assertTrue(len(signals) > 0)

    def test_specific_title_not_penalized(self):
        factor, signals = generic_concept_title_adjust("History of the Transistor", "/wiki/History_of_the_transistor")
        self.assertEqual(factor, 1.0)
        self.assertEqual(signals, [])


class TestPhraseMatchAdjust(unittest.TestCase):
    def test_single_word_query_not_boosted(self):
        factor, signals = phrase_match_adjust("cats", "all about cats here")
        self.assertEqual(factor, 1.0)

    def test_exact_phrase_match_boosts(self):
        factor, signals = phrase_match_adjust("history of the transistor",
            "this article covers the history of the transistor in depth")
        self.assertGreater(factor, 1.0)
        self.assertTrue(len(signals) > 0)

    def test_scrambled_words_do_not_match(self):
        factor, signals = phrase_match_adjust("history of the transistor",
            "transistor history notes and timeline discussion")
        self.assertEqual(factor, 1.0)



class TestInflectionAndQuestionFrame(unittest.TestCase):
    """1.1.0: plural/singular matching, the "how does X work" frame, file-name titles."""

    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_plural_query_finds_singular_document(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="a lawsuit is filed by a plaintiff")
            results = search(idx, "lawsuits")
            self.assertEqual(len(results), 1)
            idx.close()

    def test_how_does_x_work_ranks_topic_above_work_pages(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/jobs.txt", title="Jobs",
                           text="work shifts work hours work pay work schedule at work every day of work")
            idx.add_source(source_type="file", location="/legal.txt", title="Legal",
                           text="a lawsuit starts when you are served and ends in settlement or trial")
            results = search(idx, "how do lawsuits work?")
            self.assertEqual(results[0]["location"], "/legal.txt")
            idx.close()

    def test_work_alone_is_still_searched(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/jobs.txt", title="Jobs", text="how work is scheduled")
            self.assertEqual(len(search(idx, "how does it work")), 1)
            idx.close()

    def test_both_forms_in_query_count_once(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="one lawsuit")
            single = search(idx, "lawsuit")[0]["score"]
            both = search(idx, "lawsuit lawsuits")[0]["score"]
            self.assertAlmostEqual(single, both)
            idx.close()

    def test_file_name_title_matches(self):
        factor, boosts = title_match_adjust("LEGAL_SIMULATION.md", {"legal"})
        self.assertGreater(factor, 1.0)
        self.assertTrue(boosts)

if __name__ == "__main__":
    unittest.main()


