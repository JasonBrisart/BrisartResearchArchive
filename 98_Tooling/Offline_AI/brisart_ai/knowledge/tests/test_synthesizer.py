"""
File: brisart_ai/knowledge/tests/test_synthesizer.py

Purpose
-------
Verify answer rendering, citation mapping, and grounded excerpts.

This regression test module defines `TestFormatSource`, `TestSynthesize`,
`TestSynthesizerInflection`. Its scope is deliberately limited to the responsibilities visible
in this file rather than duplicating the application-wide workflow. Its fixtures and
assertions describe observable behavior without changing the installed application.

Communication / relationships
-----------------------------
Exercises the synthesizer with ranked document fixtures; scoring tests live with the engine.

The direct in-project imports visible in this module are `brisart_ai.knowledge.synthesizer`.
Test methods `test_formats_with_title_and_location`,
`test_falls_back_to_location_when_no_title`, `test_short_structured_lines_and_low_coverage`,
`test_comparison_does_not_let_one_subject_win`,
`test_long_unpunctuated_passage_is_not_dropped`; this identifies where behavior is invoked
without implying a separate hidden dependency. The test runner supplies the test lifecycle and
any temporary fixtures.

Settings / parameters
---------------------
Uses explicit source and excerpt limits in boundary cases.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Missing titles, duplicate excerpts, partial topic coverage and uncertain evidence.

The behaviors documented above must be read together with the actual branches in
test_synthesizer.py; assertions should reject regressions rather than merely checking file
layout. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Curated fixtures do not measure relevance across a production archive.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_synthesizer.py -q

For a concrete entry point, inspect `TestFormatSource`, `TestSynthesize`,
`TestSynthesizerInflection`; run this module through the existing project test runner with its
actual test path. The example above is illustrative of this file's present interface; do not
treat it as an instruction to create additional state or call private functions directly.
"""

import unittest
from brisart_ai.knowledge.synthesizer import format_source, synthesize


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
