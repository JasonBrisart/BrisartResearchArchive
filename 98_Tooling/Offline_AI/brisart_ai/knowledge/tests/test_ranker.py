"""
File: brisart_ai/knowledge/tests/test_ranker.py

Purpose
-------
Exercise Brisart candidate selection and ordering.

These regression cases constrain the observable order and eligibility of retrieved
documents. They prevent a ranking optimization from silently turning lexical scope or
typo recovery into unrestricted search.

Protected scenarios: TestSearch verifies body evidence beats scattered keywords;
TestSearch verifies metadata and generic query do not replace evidence; TestSearch
verifies compound token remains searchable; TestSearch verifies exact python definition
outranks mentions; TestSearch verifies typo recovery is scoped and citations use
recovered term.

Protected scenarios: TestSearch verifies ambiguous typo does not guess; TestSearch
verifies lengths refresh after another handle commits; TestSearch verifies empty query
returns no results; TestSearch verifies no matching documents returns empty; TestSearch
verifies matching document is returned.

Protected scenarios: TestSearch verifies source types filter restricts scope; TestSearch
verifies founder intent ranks history above product page; TestSearch verifies statistic
intent finds numeric content; TestSearch verifies result documents have expected fields;
TestSearch verifies limit is respected.

Protected scenarios: TestTitleMatchAdjust verifies no title returns neutral;
TestTitleMatchAdjust verifies matching title term boosts; TestTitleMatchAdjust verifies
generic verb damped; TestGenericConceptTitleAdjust verifies bare generic title
penalized; TestGenericConceptTitleAdjust verifies specific title not penalized.

Protected scenarios: TestPhraseMatchAdjust verifies single word query not boosted;
TestPhraseMatchAdjust verifies exact phrase match boosts; TestPhraseMatchAdjust verifies
scrambled words do not match; TestInflectionAndQuestionFrame verifies plural query finds
singular document; TestInflectionAndQuestionFrame verifies how does x work ranks topic
above work pages.

Protected scenarios: TestInflectionAndQuestionFrame verifies work alone is still
searched; TestInflectionAndQuestionFrame verifies both forms in query count once;
TestInflectionAndQuestionFrame verifies file name title matches.

Communication / relationships
-----------------------------
Uses temporary indexes and representative query cases.

Temporary indexes hold deliberately competing documents: exact declarations, scattered
keywords, buried passages, source types and ambiguous spellings.

Direct project imports: brisart_ai.knowledge.index, brisart_ai.knowledge.ranker.

The cases use self.assertEqual, self.assertGreater, self.assertTrue, self.assertLess,
self.assertIn, self.assertNotIn, self.assertGreaterEqual, self.assertLessEqual to check
returned values, persisted state or raised errors. The suite is run through
scripts/run_tests.py so Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Typo scope, ambiguous terms, exact declarations, cache invalidation and empty scope.

An explicit empty scope returns nothing; a unique one-edit recovery is reported; an
ambiguous typo is not guessed. A commit through another connection must invalidate
cached lengths.

Regression coverage includes TestPhraseMatchAdjust.test_scrambled_words_do_not_match,
TestInflectionAndQuestionFrame.test_plural_query_finds_singular_document,
TestInflectionAndQuestionFrame.test_how_does_x_work_ranks_topic_above_work_pages,
TestInflectionAndQuestionFrame.test_work_alone_is_still_searched,
TestInflectionAndQuestionFrame.test_both_forms_in_query_count_once,
TestInflectionAndQuestionFrame.test_file_name_title_matches.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_ranker.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_ranker.py -k
test_body_evidence_beats_scattered_keywords.
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

    def test_body_evidence_beats_scattered_keywords(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/decoy.txt", "Permit renewal", "Permit. " * 20 + "Renewal. " * 20)
            idx.add_source("file", "/field.txt", "Field notes", "General background. " * 150 +
                           "Permit renewal opens in April.")
            self.assertEqual(search(idx, "permit renewal")[0]["title"], "Field notes")

    def test_metadata_and_generic_query_do_not_replace_evidence(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/decoy.txt", "Explain", "Explain every rule in the handbook.")
            self.assertEqual(search(idx, "explain aurora"), [])
            self.assertEqual(search(idx, "explain", source_types=[]), [])

    def test_compound_token_remains_searchable(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/a.txt", "History", "Pat is the co-founder.")
            self.assertEqual(len(search(idx, "co-founder")), 1)

    def test_exact_python_definition_outranks_mentions(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/guide.md", "MAX_RETRIES", "MAX_RETRIES permits repeated attempts.")
            idx.add_source("file", "/settings.py", "settings", "MAX_RETRIES = 3")
            idx.add_source("file", "/other.py", "other", "max_retries = 99")
            self.assertEqual(search(idx, "What is MAX_RETRIES?")[0]["location"], "/settings.py")

    def test_typo_recovery_is_scoped_and_citations_use_recovered_term(self):
        from brisart_ai.knowledge.synthesizer import synthesize
        with Index(":memory:") as idx:
            idx.add_source("file", "/work.txt", "Guide", "Calibration begins at noon.")
            idx.add_source("web", "https://example.invalid", "Old", "Calibratoin starts tomorrow.")
            docs = search(idx, "calibratoin", source_type="file")
            self.assertEqual(docs[0]["query_corrections"], {"calibratoin": "calibration"})
            answer = synthesize("calibratoin", docs)
            self.assertIn("[1] Calibration begins at noon.", answer)
            self.assertIn("calibratoin -> calibration", answer)
            self.assertNotIn("tomorrow", answer)

    def test_ambiguous_typo_does_not_guess(self):
        with Index(":memory:") as idx:
            idx.add_source("file", "/work.txt", "Guide", "Samples and sampled entries are different.")
            self.assertEqual(search(idx, "samplex"), [])

    def test_lengths_refresh_after_another_handle_commits(self):
        from brisart_ai.knowledge.ranker import _load_document_lengths
        with tempfile.TemporaryDirectory() as tmp, self._make(tmp) as reader, self._make(tmp) as writer:
            writer.add_source("file", "/one.txt", "A", "instrument logs")
            first, _mean = _load_document_lengths(reader, ["file"], None)
            writer.add_source("file", "/two.txt", "B", "instrument logs")
            second, _mean = _load_document_lengths(reader, ["file"], None)
            self.assertEqual((len(first), len(second)), (1, 2))

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

