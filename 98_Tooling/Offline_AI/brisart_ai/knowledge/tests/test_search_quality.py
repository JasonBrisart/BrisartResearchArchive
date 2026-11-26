"""Purpose
-------
Measure whether the real SQLite search ranks judged evidence above distractors.

This regression test module defines `TestSearchJudgments`. Its scope is deliberately limited
to the responsibilities visible in this file rather than duplicating the application-wide
workflow. Its fixtures and assertions describe observable behavior without changing the
installed application.

Communication / relationships
-----------------------------
Uses Index and ranker.search directly; the answer formatter is not involved.

The direct in-project imports visible in this module are `brisart_ai.knowledge.index`,
`brisart_ai.knowledge.ranker`. Test methods `make_index`,
`test_judged_evidence_ranks_first_over_distractors`,
`test_warm_results_are_stable_across_unrelated_searches`,
`test_unrelated_queries_have_no_results`,
`test_both_independent_sources_survive_comparison_retrieval`; this identifies where behavior
is invoked without implying a separate hidden dependency. The test runner supplies the test
lifecycle and any temporary fixtures.

Settings / parameters
---------------------
Fixed corpus, explicit relevance judgments and deterministic insertion orders.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Keyword stuffing, scattered concepts, filename-only matches, acronym lists,
source scope, missing topics, duplicate result pressure and warm-index repeatability.

The behaviors documented above must be read together with the actual branches in
test_search_quality.py; assertions should reject regressions rather than merely checking file
layout. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Small authored fixtures, not a relevance benchmark on the real Archive.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_search_quality.py -q

For a concrete entry point, inspect `TestSearchJudgments`; run this module through the
existing project test runner with its actual test path. The example above is illustrative of
this file's present interface; do not treat it as an instruction to create additional state or
call private functions directly.
"""

from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest

from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ranker import search


# Judgments are hand-authored before ranking; filenames are stable test identifiers.
CORPUS = {
    "mechanism.md": "TFL integrates sensory input, memory and prediction. The integrated state becomes the prior for the next cycle.",
    "framework-roster.md": "The framework display order is TFL, RIET, SST, PFT and IRE.",
    "teaching.md": "# How to teach TFL\nIntroduce it in the first lesson and announce the schedule.",
    "RIET SST comparison.md": "The workshop agenda lists RIET and SST. No comparison is included.",
    "roles.md": "Unlike SST, which stabilizes identity constraints, RIET describes prediction dominating perception under ambiguity.",
    "permit-policy.md": "The workshop permit renewal fee is $37. The renewal deadline is June 30.",
    "permit-renewal-fee.md": "Contains links to other documents and contact details for the office.",
    "scattered.md": "Permit records are archived.\n\nRenewal of the parking contract is annual.\n\nA fee applies to replacement badges.",
    "stuffed.md": "Permit permit permit permit permit. Renewal renewal renewal renewal. Fee fee fee fee fee.",
    "filter-manual.md": "The sediment filter traps particles before water enters the reservoir.",
    "filter-noise.md": "The filter label is blue. The housing and mounting bracket ship separately.",
    "network-only.md": "Guest wireless credentials are rotated monthly.",
}
CASES = (
    ("how does TFL work?", "mechanism.md", ("teaching.md", "framework-roster.md")),
    ("Explain how TFL operates", "mechanism.md", ("teaching.md", "framework-roster.md")),
    ("How does the TFL function?", "mechanism.md", ("teaching.md", "framework-roster.md")),
    ("TFL sensory input memory prediction", "mechanism.md", ("teaching.md",)),
    ("RIET versus SST", "roles.md", ("framework-roster.md", "RIET SST comparison.md")),
    ("compare SST and RIET", "roles.md", ("framework-roster.md", "RIET SST comparison.md")),
    ("how does RIET compare to SST?", "roles.md", ("framework-roster.md", "RIET SST comparison.md")),
    ("what is the workshop permit renewal fee?", "permit-policy.md", ("permit-renewal-fee.md", "stuffed.md")),
    ("how much is the permit renewal fee?", "permit-policy.md", ("scattered.md", "stuffed.md")),
    ("permit renewal fees", "permit-policy.md", ("scattered.md", "stuffed.md")),
    ("when does the permit expire?", "permit-policy.md", ("stuffed.md",)),
    ("how does the sediment filter work?", "filter-manual.md", ("filter-noise.md",)),
    ("explain how the sediment filter operates", "filter-manual.md", ("filter-noise.md",)),
    ("sediment filters trap particles", "filter-manual.md", ("filter-noise.md",)),
)


class TestSearchJudgments(unittest.TestCase):
    def make_index(self, rows):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        idx = Index(str(Path(temp.name) / "search.sqlite3"))
        self.addCleanup(idx.close)
        for name, text in rows:
            self.assertTrue(idx.add_source("file", name, name, text))
        return idx

    def test_judged_evidence_ranks_first_over_distractors(self):
        rows = list(CORPUS.items())
        shuffled = rows.copy()
        random.Random(17).shuffle(shuffled)
        for order, items in (("original", rows), ("reversed", rows[::-1]), ("shuffled", shuffled)):
            idx = self.make_index(items)
            for query, relevant, distractors in CASES:
                with self.subTest(order=order, query=query):
                    results = search(idx, query, limit=3, source_types={"file"})
                    paths = [doc["location"] for doc in results]
                    self.assertTrue(paths, query)
                    self.assertEqual(paths[0], relevant, paths)
                    self.assertNotIn(paths[0], distractors)
                    self.assertNotIn("network-only.md", paths)

    def test_warm_results_are_stable_across_unrelated_searches(self):
        idx = self.make_index(CORPUS.items())
        for query, relevant, _ in CASES:
            with self.subTest(query=query):
                first = search(idx, query, limit=3)
                search(idx, "wireless credentials", limit=1)
                later = search(idx, query, limit=3)
                self.assertEqual([doc["location"] for doc in first], [doc["location"] for doc in later])
                self.assertEqual(later[0]["location"], relevant)

    def test_unrelated_queries_have_no_results(self):
        idx = self.make_index(CORPUS.items())
        for query in ("saxophone embouchure", "antarctic penguins", "crochet stitches"):
            with self.subTest(query=query):
                self.assertEqual(search(idx, query), [])

    def test_both_independent_sources_survive_comparison_retrieval(self):
        rows = [
            ("riet-role.md", "RIET describes prediction dominating perception under ambiguity."),
            ("sst-role.md", "SST stabilizes identity constraints when evaluating outcomes."),
        ]
        # Distinct filenames reproduce duplicate context exports crowding out primary sources.
        rows.extend((f"export-{i}.md", "The workshop agenda lists RIET and SST in the display order.")
                    for i in range(12))
        idx = self.make_index(rows)
        for query in ("RIET vs SST", "compare SST and RIET", "how does RIET compare to SST?"):
            with self.subTest(query=query):
                paths = [doc["location"] for doc in search(idx, query, limit=8)]
                self.assertTrue({"riet-role.md", "sst-role.md"}.issubset(paths), paths)

    def test_comparison_reserves_single_side_evidence_beyond_candidate_cutoff(self):
        rows = [(f"RIET SST exports/{i}.md", "Workshop agenda: RIET and SST are listed together.")
                for i in range(60)]
        rows.extend([
            ("riet-role.md", "RIET describes prediction dominating perception under ambiguity."),
            ("sst-role.md", "SST stabilizes identity constraints when evaluating outcomes."),
        ])
        idx = self.make_index(rows)
        results = search(idx, "RIET vs SST", limit=2)
        self.assertEqual({doc["location"] for doc in results}, {"riet-role.md", "sst-role.md"})

    def test_exact_comparison_copies_do_not_consume_all_result_slots(self):
        contrast = "Unlike SST, RIET describes prediction dominating perception under ambiguity."
        rows = [(f"comparison-copy-{i}.md", contrast) for i in range(8)]
        rows.append(("sst-role.md", "SST stabilizes identity constraints when evaluating outcomes."))
        idx = self.make_index(rows)
        results = search(idx, "RIET vs SST", limit=2)
        self.assertEqual([doc["text"] for doc in results], [contrast, rows[-1][1]])

    def test_stronger_out_of_scope_result_cannot_win(self):
        idx = self.make_index(CORPUS.items())
        idx.add_source("web", "old-web", "Workshop permit renewal fee", "Workshop permit renewal fee is $999.")
        idx.add_source("note", "saved-note", "Workshop permit note", "The workshop permit renewal fee was recorded as $45.")
        query = "workshop permit renewal fee"
        files = search(idx, query, source_types={"file"})
        notes = search(idx, query, source_types={"note"})
        self.assertEqual(files[0]["location"], "permit-policy.md")
        self.assertTrue(all(result["source_type"] == "file" for result in files))
        self.assertEqual([result["location"] for result in notes], ["saved-note"])
        self.assertEqual(search(idx, query, source_types=set()), [])
