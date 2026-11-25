r"""
File: brisart_ai/knowledge/tests/test_synthesizer.py

Purpose
-------
Exercise selection and citation of indexed excerpts.

Protected scenarios: TestQueryIntentDelegation verifies wants quantity for how many;
TestQueryIntentDelegation verifies wants comparison for outlive;
TestQueryIntentDelegation verifies wants reason for why; TestQueryIntentDelegation
verifies general query wants none of them; TestSentenceScore verifies no overlap scores
zero.

Protected scenarios: TestSentenceScore verifies overlap scores positive;
TestSentenceScore verifies quantity mode boosts numeric sentence; TestSentenceScore
verifies comparison mode boosts comparative sentence; TestSentenceScore verifies reason
mode boosts causal sentence; TestFormatSource verifies formats with title and location.

Protected scenarios: TestFormatSource verifies falls back to location when no title;
TestSynthesize verifies short structured lines and low coverage; TestSynthesize verifies
comparison does not let one subject win; TestSynthesize verifies long unpunctuated
passage is not dropped; TestSynthesize verifies split label and value stay together in
cited excerpt.

Protected scenarios: TestSynthesize verifies empty docs returns no information message;
TestSynthesize verifies docs with no matching sentences returns distinct message;
TestSynthesize verifies matching docs produce cited answer; TestSynthesize verifies
citations are sequential with no gaps; TestSynthesizerInflection verifies singular
sentence answers plural question.

Communication / relationships
-----------------------------
Uses document dictionaries with known answer passages.

Direct project imports: brisart_ai.knowledge.synthesizer.

The cases use self.assertTrue, self.assertFalse, self.assertEqual, self.assertGreater,
self.assertIn, self.assertNotIn to check returned values, persisted state or raised
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
Short fields, comparisons, partial coverage and long lines.

Regression coverage includes
TestSynthesize.test_split_label_and_value_stay_together_in_cited_excerpt,
TestSynthesize.test_empty_docs_returns_no_information_message,
TestSynthesize.test_docs_with_no_matching_sentences_returns_distinct_message,
TestSynthesize.test_matching_docs_produce_cited_answer,
TestSynthesize.test_citations_are_sequential_with_no_gaps,
TestSynthesizerInflection.test_singular_sentence_answers_plural_question.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_synthesizer.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_synthesizer.py -k
test_wants_comparison_for_outlive.
"""

import unittest
from brisart_ai.knowledge.synthesizer import (
    format_source, query_wants_comparison, query_wants_quantity, query_wants_reason, sentence_score, synthesize,
)


class TestQueryIntentDelegation(unittest.TestCase):
    def test_wants_quantity_for_how_many(self):
        self.assertTrue(query_wants_quantity("how many cats are in america?"))

    def test_wants_comparison_for_outlive(self):
        self.assertTrue(query_wants_comparison("do dogs outlive cats?"))

    def test_wants_reason_for_why(self):
        self.assertTrue(query_wants_reason("why do cats purr?"))

    def test_general_query_wants_none_of_them(self):
        self.assertFalse(query_wants_quantity("tell me about cats"))
        self.assertFalse(query_wants_comparison("tell me about cats"))
        self.assertFalse(query_wants_reason("tell me about cats"))


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


class TestFormatSource(unittest.TestCase):
    def test_formats_with_title_and_location(self):
        doc = {"source_type": "file", "location": "/a.txt", "title": "My Doc"}
        self.assertEqual(format_source(doc), "file: My Doc :: /a.txt")

    def test_falls_back_to_location_when_no_title(self):
        doc = {"source_type": "web", "location": "https://x.com"}
        result = format_source(doc)
        self.assertIn("https://x.com", result)


class TestSynthesize(unittest.TestCase):
    def test_short_structured_lines_and_low_coverage(self):
        docs = [{"title": "A", "location": "/a.txt", "text": "Permit expiry: June 30\nUnrelated heading"}]
        self.assertIn("Permit expiry: June 30", synthesize("When does the permit expire?", docs))
        self.assertIn("may not answer the whole question", synthesize("permit renewal fee", docs))

    def test_comparison_does_not_let_one_subject_win(self):
        docs = [{"title": "A", "location": "/a.txt", "text":
                 "Trains are faster than bicycles on longer routes. "
                 "Ferries and trains serve different parts of the coastline."}]
        answer = synthesize("compare ferries versus trains", docs)
        self.assertIn("Ferries and trains", answer)
        self.assertNotIn("bicycles", answer)

    def test_long_unpunctuated_passage_is_not_dropped(self):
        docs = [{"text": "background " * 150 + "permit renewal opens April 3"}]
        self.assertIn("permit renewal opens April 3", synthesize("permit renewal", docs))

    def test_split_label_and_value_stay_together_in_cited_excerpt(self):
        docs = [{"title": "Permit", "location": "/permit.txt", "text": "Permit fee:\n$42\n\nUnrelated text"}]
        self.assertIn("[1] Permit fee: $42", synthesize("What is the permit fee?", docs))

    def test_empty_docs_returns_no_information_message(self):
        result = synthesize("anything", [])
        self.assertIn("don't have any indexed information", result)

    def test_docs_with_no_matching_sentences_returns_distinct_message(self):
        docs = [{"source_type": "file", "location": "/a.txt", "title": "A", "text": "completely unrelated filler content padding out this sentence to be long enough"}]
        result = synthesize("zzzznonexistentterm", docs)
        self.assertIn("none of them", result.lower())
        # Distinct from the "no docs at all" message.
        self.assertNotIn("don't have any indexed information", result)

    def test_matching_docs_produce_cited_answer(self):
        docs = [{"source_type": "file", "location": "/a.txt", "title": "Microsoft History",
                 "text": "Microsoft was founded by Bill Gates and Paul Allen in nineteen seventy five in Albuquerque."}]
        result = synthesize("who founded microsoft", docs)
        self.assertIn("Sources:", result)
        self.assertIn("Gates", result)

    def test_citations_are_sequential_with_no_gaps(self):
        docs = [
            {"source_type": "file", "location": "/a.txt", "title": "Doc A", "text": "widget alpha appears in this sentence about widgets here today."},
            {"source_type": "file", "location": "/b.txt", "title": "Doc B", "text": "widget beta appears in this other sentence about widgets here too."},
        ]
        result = synthesize("widget", docs)
        self.assertIn("[1]", result)
        # If two sources both contribute, citation numbers should be sequential.
        if "[2]" in result:
            self.assertNotIn("[3]", result.split("Sources:")[0])



class TestSynthesizerInflection(unittest.TestCase):
    def test_singular_sentence_answers_plural_question(self):
        from brisart_ai.knowledge.synthesizer import synthesize
        docs = [{"title": "Legal", "location": "/legal.txt", "source_type": "file",
                 "text": "Every lawsuit begins when the company is served with a claim by a plaintiff."}]
        answer = synthesize("how do lawsuits work?", docs)
        self.assertIn("Every lawsuit begins", answer)

if __name__ == "__main__":
    unittest.main()
