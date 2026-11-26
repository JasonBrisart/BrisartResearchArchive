"""Purpose
-------
Verify intent classification and its effect on retrieval evidence.

This regression test module defines `TestQueryIntent`. Its scope is deliberately limited to
the responsibilities visible in this file rather than duplicating the application-wide
workflow. Its fixtures and assertions describe observable behavior without changing the
installed application.

Communication / relationships
-----------------------------
Uses the public classifier, topic extraction and SQLite search path.

The direct in-project imports visible in this module are `brisart_ai.core.conversation`,
`brisart_ai.core.session_memory`, `brisart_ai.intent`, `brisart_ai.knowledge`,
`brisart_ai.knowledge.index`. Test methods `test_classifier_and_evidence_route`,
`test_public_ranker_prioritizes_the_requested_evidence`,
`test_adversarial_cues_do_not_override_the_request`,
`test_adversarial_evidence_is_rejected_by_both_ranking_and_answer`,
`test_expiry_evidence_beats_renewal_context_in_rank_and_answer`; this identifies where
behavior is invoked without implying a separate hidden dependency. The test runner supplies
the test lifecycle and any temporary fixtures.

Settings / parameters
---------------------
Fixed query judgments and a temporary SQLite index for each ranking case.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Casing, paraphrases, statistics versus explanatory framing, empty queries,
misleading cues, comparison agendas, negated dates, and renewal versus expiry
when only one result can reach the answer. Date cases also distinguish past
submissions and opening dates from deadlines.
Dependency cases check direction, scope, aliases, inferred chains, polarity,
and whether limited citation space can present all necessary claims. Scale
replays put unique evidence behind repeated exports; scoped cases verify dates
and releases do not leak across links or citations.

Proof selection cases exercise citation budgets, ambiguous intermediates,
and mixed supported and disputed dependency lists. Confidence cases exercise
tentative dates, cross-format and paraphrased conflicts, invalid dates, duplicate notices and
citation limits.

Relationship dates cover active/passive paraphrases, separate start/end events,
release isolation, calendar validity and inclusive interval boundaries.

Version cases cover prefix/suffix equivalence, exact release and date
isolation, passive wording, invalid labels and citation budgets.

Known limitations
-----------------
Curated English examples; not a natural-language accuracy benchmark.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_query_intent.py -q

For a concrete entry point, inspect `TestQueryIntent`; run this module through the existing
project test runner with its actual test path. The example above is illustrative of this
file's present interface; do not treat it as an instruction to create additional state or call
private functions directly.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.intent import detect_intent, evidence_mode
from brisart_ai.knowledge import ranker
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ranker import query_groups, search


class TestQueryIntent(unittest.TestCase):
    def test_classifier_and_evidence_route(self):
        cases = (
            ('  HOW DOES TFL WORK?! ', 'explanation', 'mechanism'),
            ('How does TFL operate?', 'explanation', 'mechanism'),
            ('Explain how TFL functions.', 'explanation', 'mechanism'),
            ('How does the sediment filter work?', 'explanation', 'mechanism'),
            ('Why does the filter clog?', 'explanation', ''),
            ('What causes sediment buildup?', 'explanation', ''),
            ('RIET vs. SST', 'comparison', 'comparison'),
            ('Compare SST and RIET', 'comparison', 'comparison'),
            ('How does RIET compare to SST?', 'comparison', 'comparison'),
            ('Compare RIET, SST and TFL', 'comparison', ''),
            ('How many permits were renewed?', 'statistic', ''),
            ('How much does a permit cost?', 'statistic', ''),
            ('How many more permits were issued in July versus June?', 'statistic', ''),
            ('Who founded Microsoft?', 'founder', ''),
            ('Who created Microsoft Excel?', 'inventor', ''),
            ('When does the workshop permit expire?', 'general', 'deadline'),
            ('What date is the renewal deadline?', 'general', 'deadline'),
            ('When did the workshop open?', 'general', ''),
            ('permit expiration rules', 'general', ''),
            ('TFL notes', 'general', ''),
            ('', 'general', ''),
            (' ?! ', 'general', ''),
        )
        for query, label, route in cases:
            with self.subTest(query=query):
                self.assertEqual(detect_intent(query), label)
                self.assertEqual(evidence_mode(query, len(query_groups(query))), route)

    def test_public_ranker_prioritizes_the_requested_evidence(self):
        cases = (
            ('How does TFL operate?', 'explanation', 'mechanism',
             'TFL integrates sensory input, memory and prediction.',
             'TFL is listed on the workshop agenda.'),
            ('RIET vs. SST', 'comparison', 'comparison',
             'Unlike SST, RIET describes prediction dominating perception under ambiguity.',
             'RIET and SST are listed together on the workshop agenda.'),
            ('When does the permit expire?', 'general', 'deadline',
             'The permit expires on July 15.',
             'Permit expiration is discussed in the permit training materials.'),
        )
        for query, label, route, evidence, mention in cases:
            with self.subTest(query=query), TemporaryDirectory() as folder:
                idx = Index(str(Path(folder) / 'intent.sqlite3'))
                try:
                    idx.add_source('file', 'mention.md', query, mention)
                    idx.add_source('file', 'evidence.md', 'Evidence', evidence)
                    results = search(idx, query, limit=2)
                    self.assertTrue(results, query)
                    self.assertEqual(results[0]['location'], 'evidence.md')
                    self.assertEqual(results[0]['intent'], label)
                    self.assertIn(f'<intent-evidence>:{route}', results[0]['intent_boosts'])
                finally:
                    idx.close()


    def test_adversarial_cues_do_not_override_the_request(self):
        cases = (
            ("Explain how many permits were renewed", "statistic", ""),
            ("Explain how to compare RIET and SST", "comparison", "comparison"),
            ("Do not compare RIET and SST", "general", ""),
            ("Do not compare RIET and SST; why do they differ?", "explanation", ""),
            ("How does work affect TFL?", "explanation", ""),
            ("Explain how TFL works?!", "explanation", "mechanism"),
            ("Which is faster: RIET vs SST vs TFL?", "comparison", ""),
            ("Why does the permit expire?", "explanation", ""),
            ("When does the workshop permit expire?", "general", "deadline"),
            ("When did the workshop open?", "general", ""),
        )
        for query, intent, mode in cases:
            with self.subTest(query=query):
                plan = ranker.prepare_query(query)
                self.assertEqual((plan.intent, plan.mode), (intent, mode))

    def test_adversarial_evidence_is_rejected_by_both_ranking_and_answer(self):
        cases = (
            ("RIET vs SST", "While RIET and SST appear on the agenda, the talks begin at noon.",
             "Unlike SST, RIET describes prediction dominating perception under ambiguity.", "noon"),
            ("When does the permit expire?", "The permit does not expire on July 15.",
             "The permit expires on August 9.", "July 15"),
        )
        for query, distractor, evidence, forbidden in cases:
            with self.subTest(query=query), TemporaryDirectory() as folder:
                path = str(Path(folder) / "adversarial.sqlite3")
                idx = Index(path)
                memory = SessionMemory(path)
                try:
                    idx.add_source("file", "distractor.md", query, distractor)
                    unsupported = build_conversation_answer(query, idx, memory)
                    self.assertIn("not enough evidence", unsupported)
                    self.assertNotIn(forbidden, unsupported)
                    idx.add_source("file", "evidence.md", "Evidence", evidence)
                    self.assertEqual(search(idx, query)[0]["location"], "evidence.md")
                    with patch.object(ranker, "detect_intent", wraps=detect_intent) as classifier:
                        answer = build_conversation_answer(query, idx, memory)
                    classifier.assert_called_once_with(query)
                    self.assertIn(evidence, answer)
                    self.assertIn("evidence.md", answer)
                    self.assertNotIn(forbidden, answer)
                finally:
                    memory.close()
                    idx.close()

    def test_expiry_evidence_beats_renewal_context_in_rank_and_answer(self):
        query = "When does the workshop permit expire?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "dates.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                idx.add_source("file", "renewal.md", query,
                               "The workshop permit renewal deadline is June 30.")
                idx.add_source("file", "expiry.md", "Permit", "The permit expires on July 15.")
                self.assertEqual(search(idx, query, limit=1)[0]["location"], "expiry.md")
                answer = build_conversation_answer(query, idx, memory, limit=1)
                self.assertIn("July 15", answer)
                self.assertIn("expiry.md", answer)
                self.assertNotIn("June 30", answer)
            finally:
                memory.close()
                idx.close()

    def test_date_routes_require_evidence_for_the_requested_event(self):
        cases = (
            ("What day is the permit renewal due?", "The permit expires on July 15.",
             "Permit renewal is due by 30 June.", "30 June", "July 15"),
            ("Which date is the workshop application due?", "The workshop application opened on May 1.",
             "Workshop applications close on 14 June.", "14 June", "May 1"),
            ("When must I submit the workshop report?", "The workshop report was submitted on May 1.",
             "Submit the workshop report by 2026-06-14.", "2026-06-14", "May 1"),
            ("When does the workshop permit expire?", "The workshop permit renewal deadline is June 30.",
             "The workshop permit expires on 15 July.", "15 July", "June 30"),
        )
        for query, decoy, evidence, right_date, wrong_date in cases:
            with self.subTest(query=query), TemporaryDirectory() as folder:
                path = str(Path(folder) / "event.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    idx.add_source("file", "related.md", query, decoy)
                    self.assertIn("not enough evidence", build_conversation_answer(query, idx, memory))
                    idx.add_source("file", "direct.md", "Notice", evidence)
                    hits = search(idx, query, limit=1)
                    self.assertEqual(hits[0]["location"], "direct.md")
                    answer = build_conversation_answer(query, idx, memory, limit=1)
                    self.assertIn(right_date, answer)
                    self.assertIn("direct.md", answer)
                    self.assertNotIn(wrong_date, answer)
                finally:
                    memory.close()
                    idx.close()

    def test_dependency_evidence_matches_entities_and_direction(self):
        cases = (
            ('Does Atlas Index depend on Cedar Store?', 'Atlas Index depends on Cedar Store.'),
            ('Does the Atlas Index require the Cedar Store?', 'Cedar Store is required by Atlas Index.'),
            ('What does Atlas Index depend on?', 'Atlas Index depends on Cedar Store.'),
            ('What requires Cedar Store?', 'Atlas Index requires Cedar Store.'),
        )
        decoys = (
            'Cedar Store depends on Atlas Index.',
            'Atlas Index and Cedar Store appear in the system inventory.',
            'Atlas Indexer depends on Cedar Store Cache.',
            'Atlas Index might depend on Cedar Store.',
        )
        for query, evidence in cases:
            with self.subTest(query=query), TemporaryDirectory() as folder:
                path = str(Path(folder) / 'dependencies.sqlite3')
                idx, memory = Index(path), SessionMemory(path)
                try:
                    for number, content in enumerate(decoys):
                        idx.add_source('file', f'decoy-{number}.md', query, content)
                    answer = build_conversation_answer(query, idx, memory)
                    self.assertIn('not enough evidence', answer)
                    idx.add_source('file', 'architecture.md', 'Architecture', evidence)
                    idx.add_source('web', 'old-web', query, evidence)
                    self.assertEqual(search(idx, query, limit=1, source_types={'file'})[0]['location'],
                                     'architecture.md')
                    answer = build_conversation_answer(query, idx, memory, limit=1)
                    self.assertIn(evidence, answer)
                    self.assertIn('architecture.md', answer)
                    self.assertNotIn('old-web', answer)
                    self.assertNotIn('decoy-', answer)
                finally:
                    memory.close()
                    idx.close()

    def test_explicit_negative_answers_pair_but_does_not_name_a_dependency(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / 'negative.sqlite3')
            idx, memory = Index(path), SessionMemory(path)
            try:
                statement = 'Atlas Index does not depend on Cedar Store.'
                idx.add_source('file', 'boundary.md', 'Boundary', statement)
                answer = build_conversation_answer('Does Atlas Index depend on Cedar Store?', idx, memory)
                self.assertIn(statement, answer)
                self.assertIn('boundary.md', answer)
                answer = build_conversation_answer('What does Atlas Index depend on?', idx, memory)
                self.assertIn('not enough evidence', answer)
                self.assertNotIn('Cedar Store', answer)
            finally:
                memory.close()
                idx.close()

    def test_scoped_relationship_aggregation(self):
        query = "Does Atlas Index depend on Cedar Store?"
        first = ("first.md", "Atlas Index depends on Birch Router.")
        middle = ("middle.md", "Birch Router requires Elm Queue.")
        last = ("last.md", "Cedar Store is required by Elm Queue.")
        positive = ("positive.md", "Atlas Index depends on Cedar Store.")
        negative = ("negative.md", "Atlas Index does not depend on Cedar Store.")
        alias = ("alias.md", "Atlas Index is abbreviated as AX.")
        cases = (
            (query, (first, middle, last), "Inferred dependency chain", ("first.md", "middle.md", "last.md")),
            (query, (first, middle), "not enough evidence", ()),
            ("Does Atlas Index rely on Cedar Store?", (("rely.md", "Atlas Index relies on Cedar Store."),),
             "Atlas Index relies on Cedar Store.", ("rely.md",)),
            (query, (first, middle, last, negative), "A source denies", ("first.md", "middle.md", "last.md", "negative.md")),
            (query, (first, middle, last, ("disputed.md", "Birch Router does not require Elm Queue.")),
             "not enough evidence", ()),
            (query, (first, ("cycle.md", "Birch Router depends on Atlas Index.")), "not enough evidence", ()),
            (query, (positive, negative, ("copy.md", positive[1])), "Sources disagree", ("positive.md", "negative.md")),
            ("Does AX depend on Cedar Store?", (alias, first, middle, last), "Inferred dependency chain",
             ("alias.md", "first.md", "middle.md", "last.md")),
            ("Does AX depend on Cedar Store?", (alias, ("collision.md", "Other Index aka AX."), positive),
             "Sources disagree about what this alias refers to", ("alias.md", "collision.md")),
            ("What does Atlas Index depend on?", (positive, first, ("copy.md", positive[1])),
             "not an exhaustive list", ("positive.md", "first.md")),
        )
        for question, rows, expected, sources in cases:
            with self.subTest(question=question, expected=expected), TemporaryDirectory() as folder:
                path = str(Path(folder) / "aggregation.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    for name, text in rows:
                        idx.add_source("file", name, name, text)
                    idx.add_source("web", "outside.md", "Not in scope", positive[1])
                    answer = build_conversation_answer(question, idx, memory)
                    self.assertIn(expected, answer)
                    self.assertNotIn("outside.md", answer)
                    for source in sources:
                        self.assertIn(source, answer)
                    self.assertNotIn("copy.md", answer)
                    if len(sources) > 1 and "not an exhaustive list" not in expected:
                        limited = build_conversation_answer(question, idx, memory, limit=1)
                        self.assertIn("cannot be shown completely", limited)
                        self.assertNotIn("Sources:\n", limited)
                finally:
                    memory.close()
                    idx.close()


    def test_relationship_evidence_under_duplicate_pressure(self):
        query = "Does Atlas Index depend on Cedar Store?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "duplicate-pressure.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                for n in range(800):
                    idx.add_source("file", f"copy-{n}.md", "Export",
                                   "Atlas Index depends on Birch Router.")
                for n in range(120):
                    idx.add_source("file", f"noise-{n}.md", "Unrelated",
                                   f"Noise Router {n:03} requires Unrelated Store.")
                idx.add_source("file", "middle.md", "Middle", "Birch Router requires Elm Queue.")
                idx.add_source("file", "last.md", "Last", "Elm Queue requires Cedar Store.")
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("Inferred dependency chain", answer)
                for name in ("copy-0.md", "middle.md", "last.md"):
                    self.assertIn(name, answer)
                self.assertNotIn("copy-1.md", answer)
                idx.add_source("file", "disputed.md", "Disputed", "Birch Router does not require Elm Queue.")
                self.assertIn("not enough evidence", build_conversation_answer(query, idx, memory))
                idx.add_source("file", "supports.md", "Supports", "Atlas Index depends on Cedar Store.")
                for n in range(300):
                    idx.add_source("file", f"support-copy-{n}.md", "Export",
                                   "Atlas Index depends on Cedar Store.")
                idx.add_source("file", "denies.md", "Denies", "Atlas Index does not depend on Cedar Store.")
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("Sources disagree", answer)
                self.assertIn("supports.md", answer)
                self.assertIn("denies.md", answer)
                self.assertNotIn("copy-", answer)
            finally:
                memory.close()
                idx.close()

    def test_relationship_time_and_version_boundaries(self):
        query = "Does Atlas Index depend on Cedar Store?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "relationship-scope.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                rows = (
                    ("v1.md", "In version 1.2.3, Atlas Index depends on Cedar Store."),
                    ("v2.md", "In version 2.0, Atlas Index does not depend on Cedar Store."),
                    ("window.md", "From 2026-03-01 through 2026-03-31, Atlas Index depends on Birch Router."),
                    ("later.md", "On 2026-04-01, Birch Router requires Cedar Store."),
                    ("direct.md", "In version 1.2.3, on 2026-03-31, Atlas Index depends on Cedar Store."),
                )
                for name, text in rows:
                    idx.add_source("file", name, name, text)
                cases = (
                    ("In version v1.2.3, ", "v1.md", "v2.md"),
                    ("In version 2.0, ", "v2.md", "v1.md"),
                    ("As of 2026-03-31, in version 1.2.3, ", "direct.md", "v1.md"),
                    ("As of 2026-03-31, ", "not enough evidence", "later.md"),
                    ("As of 2026-04-01, ", "not enough evidence", "window.md"),
                    ("As of 2026-02-30, ", "Use an ISO date", "Sources:"),
                    ("", "not enough evidence", "v1.md"),
                )
                for prefix, expected, excluded in cases:
                    with self.subTest(prefix=prefix):
                        answer = build_conversation_answer(prefix + query, idx, memory)
                        self.assertIn(expected, answer)
                        self.assertNotIn(excluded, answer)
                idx.add_source("file", "same-day.md", "Same day",
                               "On 2026-03-31, Birch Router requires Cedar Store.")
                answer = build_conversation_answer("As of 2026-03-31, " + query, idx, memory)
                self.assertIn("Inferred dependency chain", answer)
                self.assertIn("window.md", answer)
                self.assertIn("same-day.md", answer)
                self.assertNotIn("later.md", answer)
                idx.add_source("file", "v1-denial.md", "Disagreement",
                               "In version 1.2.3, Atlas Index does not depend on Cedar Store.")
                answer = build_conversation_answer("In version 1.2.3, " + query, idx, memory)
                self.assertIn("Sources disagree", answer)
                self.assertIn("v1.md", answer)
                self.assertIn("v1-denial.md", answer)
                self.assertNotIn("v2.md", answer)
            finally:
                memory.close()
                idx.close()

    def test_inference_uses_complete_chain_that_fits_citation_budget(self):
        query = "Does Atlas Index depend on Cedar Store?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "proof-budget.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                rows = (
                    ("short-start.md", "Atlas Index depends on Birch Router."),
                    ("short-end.md", "Birch Router requires Cedar Store."),
                    ("complete.md", "Atlas Index depends on Elm Router. Elm Router requires Oak Queue. Oak Queue requires Cedar Store."),
                )
                for name, text in rows:
                    idx.add_source("file", name, name, text)
                answer = build_conversation_answer(query, idx, memory, limit=1)
                self.assertIn("Inferred dependency chain", answer)
                self.assertIn("complete.md", answer)
                self.assertIn("Atlas Index depends on Elm Router.", answer)
                self.assertIn("Elm Router requires Oak Queue.", answer)
                self.assertIn("Oak Queue requires Cedar Store.", answer)
                self.assertNotIn("short-start.md", answer)
                # With more room, the shorter, two-link proof still wins.
                answer = build_conversation_answer(query, idx, memory, limit=2)
                self.assertIn("short-start.md", answer)
                self.assertIn("short-end.md", answer)
                self.assertNotIn("complete.md", answer)
            finally:
                memory.close()
                idx.close()

    def test_ambiguous_intermediate_alias_cannot_bridge_two_claims(self):
        query = "Does Atlas Index depend on Cedar Store?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "ambiguous-bridge.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                rows = (
                    ("first.md", "Atlas Index depends on BX."),
                    ("last.md", "BX requires Cedar Store."),
                    ("alias-one.md", "Birch Router aka BX."),
                    ("alias-two.md", "Birch Proxy aka BX."),
                )
                for name, text in rows:
                    idx.add_source("file", name, name, text)
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("not enough evidence", answer)
                self.assertNotIn("Inferred dependency chain", answer)
            finally:
                memory.close()
                idx.close()

    def test_dependency_lists_keep_undisputed_links_and_report_disputes(self):
        rows = (
            ("support.md", "Atlas Index depends on Birch Router."),
            ("deny.md", "Atlas Index does not depend on Birch Router."),
            ("independent.md", "Atlas Index requires Cedar Store. Elm Router requires Birch Router."),
            ("support-copy.md", "Atlas Index depends on Birch Router."),
        )
        for query, independent in (
            ("What does Atlas Index depend on?", "Atlas Index requires Cedar Store."),
            ("What requires Birch Router?", "Elm Router requires Birch Router."),
        ):
            with self.subTest(query=query), TemporaryDirectory() as folder:
                path = str(Path(folder) / "mixed-claims.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    for name, text in rows:
                        idx.add_source("file", name, name, text)
                    answer = build_conversation_answer(query, idx, memory, limit=3)
                    self.assertIn("Sources disagree", answer)
                    for statement in (rows[0][1], rows[1][1], independent):
                        self.assertIn(statement, answer)
                    self.assertNotIn("support-copy.md", answer)
                    limited = build_conversation_answer(query, idx, memory, limit=1)
                    self.assertIn(independent, limited)
                    self.assertIn("disputed", limited)
                    self.assertNotIn("support.md", limited)
                    self.assertNotIn("deny.md", limited)
                    self.assertNotIn(rows[0][1], limited)
                finally:
                    memory.close()
                    idx.close()

    def test_dependency_list_dispute_is_not_presented_as_complete(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "dispute-only.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                idx.add_source("file", "support.md", "Support", "Atlas Index depends on Birch Router.")
                idx.add_source("file", "deny.md", "Denial", "Atlas Index does not depend on Birch Router.")
                query = "What does Atlas Index depend on?"
                limited = build_conversation_answer(query, idx, memory, limit=1)
                self.assertIn("cannot be shown completely", limited)
                self.assertNotIn("Sources:", limited)
                full = build_conversation_answer(query, idx, memory, limit=2)
                self.assertIn("Sources disagree", full)
                self.assertIn("support.md", full)
                self.assertIn("deny.md", full)
            finally:
                memory.close()
                idx.close()

    def test_deadline_confidence_and_evidence_quality(self):
        query = "When does the workshop permit expire?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "confidence.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                idx.add_source("file", "renewal.md", query,
                               "The workshop permit renewal deadline is May 1.")
                self.assertIn("Evidence confidence: Insufficient", build_conversation_answer(query, idx, memory))
                idx.add_source("file", "draft.md", "Draft",
                               "The workshop permit may expire on 2026-07-14.")
                tentative = build_conversation_answer(query, idx, memory)
                self.assertIn("Evidence confidence: Tentative", tentative)
                self.assertIn("may expire", tentative)
                firm = "The workshop permit expires on 2026-07-15."
                idx.add_source("file", "issued.md", "Issued", firm)
                for number in range(12):
                    idx.add_source("file", f"copy-{number}.md", "Copy", firm)
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("Evidence confidence: Direct support", answer)
                self.assertIn("2026-07-15", answer)
                self.assertNotIn("2026-07-14", answer)
                hits = {item["location"]: item["evidence_quality"] for item in search(idx, query)}
                self.assertEqual(hits["issued.md"], 3)
                self.assertEqual(hits["draft.md"], 1)
                self.assertEqual(hits["renewal.md"], 1)
                idx.add_source("file", "different.md", "Different",
                               "The workshop permit expires on 2026-07-16.")
                answer = build_conversation_answer(query, idx, memory)
                for expected in ("Evidence confidence: Conflicting", "issued.md", "different.md",
                                 "2026-07-15", "2026-07-16"):
                    self.assertIn(expected, answer)
                self.assertNotIn("copy-", answer)
                limited = build_conversation_answer(query, idx, memory, limit=1)
                self.assertIn("Evidence confidence: Conflicting", limited)
                self.assertNotIn("Sources:", limited)
            finally:
                memory.close()
                idx.close()

    def test_deadline_conflicts_across_date_formats(self):
        query = "When does the workshop permit expire?"
        cases = (
            ("2026-07-15", "16 July 2026", True),
            ("2026-07-15", "July 15, 2026", False),
            ("July 15", "16 July", True),
            ("July 15", "16 July 2026", False),
            ("2026-07-15", "2027-07-15", False),
        )
        for left, right, conflict in cases:
            with self.subTest(left=left, right=right), TemporaryDirectory() as folder:
                path = str(Path(folder) / "date-formats.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    idx.add_source("file", "left.md", "Expiry", f"The workshop permit expires on {left}.")
                    idx.add_source("file", "right.md", "Expiry", f"The workshop permit expires on {right}.")
                    answer = build_conversation_answer(query, idx, memory)
                    self.assertEqual("Evidence confidence: Conflicting" in answer, conflict)
                    if conflict:
                        self.assertIn(left, answer)
                        self.assertIn(right, answer)
                        self.assertIn("left.md", answer)
                        self.assertIn("right.md", answer)
                finally:
                    memory.close()
                    idx.close()

    def test_later_deadline_claims_can_conflict_without_first_match(self):
        query = "When does the workshop permit expire?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "later-conflict.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                rows = (
                    ("distracting-first.md", "The workshop permit is valid until 2026-07-14."),
                    ("left.md", "The workshop permit expires on 2026-07-15."),
                    ("right.md", "The workshop permit expires on 2026-07-16."),
                )
                for name, text in rows:
                    idx.add_source("file", name, query if name == rows[0][0] else "Notice", text)
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("Evidence confidence: Conflicting", answer)
                self.assertIn("left.md", answer)
                self.assertIn("right.md", answer)
                self.assertNotIn("distracting-first.md", answer)
            finally:
                memory.close()
                idx.close()

    def test_impossible_date_is_not_direct_evidence(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "invalid-date.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                query = "When does the workshop permit expire?"
                idx.add_source("file", "bad.md", query, "The workshop permit expires on February 30, 2026.")
                answer = build_conversation_answer(query, idx, memory)
                self.assertIn("Evidence confidence: Insufficient", answer)
                self.assertNotIn("February 30", answer)
            finally:
                memory.close()
                idx.close()

    def test_deadline_paraphrases_preserve_claim_identity(self):
        expiry = "When does the workshop permit expire?"
        renewal = "When is the workshop permit renewal due?"
        submission = "When must I submit the workshop report?"
        cases = (
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The expiration date for the workshop permit is 16 July 2026.", True),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The workshop permit's expiry date is 2026-07-15.", False),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The workshop permit's expiry date is 2026-07-16.", True),
            (renewal, "Workshop permit renewal is due by June 30.",
             "The renewal deadline for the workshop permit is July 1.", True),
            (submission, "Submit the workshop report by 2026-06-14.",
             "The submission deadline for the workshop report is 2026-06-15.", True),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The expiration date for the online workshop permit is 16 July 2026.", False),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The expiration date for the workshop permit is 16 July 2027.", False),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The workshop permit expires on 16 July 2026 for returning applicants.", False),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The tentative expiration date for the workshop permit is 16 July 2026.", False),
            (expiry, "The workshop permit expires on July 15, 2026.",
             "The renewal deadline for the workshop permit is 16 July 2026.", False),
        )
        for query, left, right, conflict in cases:
            with self.subTest(left=left, right=right), TemporaryDirectory() as folder:
                path = str(Path(folder) / "paraphrases.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    idx.add_source("file", "left.md", "Notice", left)
                    idx.add_source("file", "right.md", "Notice", right)
                    answer = build_conversation_answer(query, idx, memory)
                    self.assertEqual("Evidence confidence: Conflicting" in answer, conflict)
                    if conflict:
                        for item in (left, right, "left.md", "right.md"):
                            self.assertIn(item, answer)
                        limited = build_conversation_answer(query, idx, memory, limit=1)
                        self.assertIn("Evidence confidence: Conflicting", limited)
                        self.assertNotIn("Sources:", limited)
                finally:
                    memory.close()
                    idx.close()

    def test_dependency_transition_dates_across_paraphrases(self):
        cases = (
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Cedar Store became a dependency of Atlas Index on 2026-06-15.", True),
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Cedar Store became required by Atlas Index on 2026-06-14.", False),
            ("stop requiring", "Atlas Index stopped requiring Cedar Store on 14 June 2026.",
             "Cedar Store ceased to be required by Atlas Index on June 15, 2026.", True),
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Atlas Index stopped requiring Cedar Store on June 15, 2026.", False),
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Atlas Index became a dependency of Cedar Store on 2026-06-15.", False),
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Cedar Store became required by Atlas Index on February 30, 2026.", False),
            ("start depending on", "Atlas Index began relying on Cedar Store on 14 June 2026.",
             "Cedar Store became required by Atlas Index on June 15.", False),
        )
        for verb, left, right, conflict in cases:
            with self.subTest(right=right), TemporaryDirectory() as folder:
                path = str(Path(folder) / "transition.sqlite3")
                idx, memory = Index(path), SessionMemory(path)
                try:
                    idx.add_source("file", "left.md", "Record", "In version 1.2, " + left)
                    idx.add_source("file", "right.md", "Record", "In version 1.2, " + right)
                    idx.add_source("file", "other-release.md", "Record",
                                   "In version 2.0, Atlas Index began requiring Cedar Store on 2026-06-19.")
                    query = f"In version 1.2, when did Atlas Index {verb} Cedar Store?"
                    self.assertEqual(search(idx, query, limit=1)[0]["evidence_quality"], 3)
                    answer = build_conversation_answer(query, idx, memory)
                    self.assertIn(left, answer)
                    self.assertNotIn("other-release.md", answer)
                    self.assertEqual("Evidence confidence: Conflicting" in answer, conflict)
                    if conflict:
                        self.assertIn(right, answer)
                        self.assertIn("right.md", answer)
                        limited = build_conversation_answer(query, idx, memory, limit=1)
                        self.assertIn("Evidence confidence: Conflicting", limited)
                        self.assertNotIn("Sources:", limited)
                finally:
                    memory.close()
                    idx.close()

    def test_dated_dependency_polarity_conflict_across_wording(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "dated-state.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                idx.add_source("file", "yes.md", "Record",
                               "From June 1, 2026 through June 15, 2026, Atlas Index relies on Cedar Store.")
                idx.add_source("file", "no.md", "Record",
                               "On June 15, 2026, Cedar Store is not a dependency of Atlas Index.")
                answer = build_conversation_answer(
                    "As of 15 June 2026, does Atlas Index depend on Cedar Store?", idx, memory)
                self.assertIn("Evidence confidence: Conflicting", answer)
                self.assertIn("yes.md", answer)
                self.assertIn("no.md", answer)
                prior = build_conversation_answer(
                    "As of 2026-06-14, does Atlas Index depend on Cedar Store?", idx, memory)
                self.assertIn("Evidence confidence: Direct support", prior)
                self.assertNotIn("no.md", prior)
            finally:
                memory.close()
                idx.close()

    def test_versioned_dependency_paraphrases_and_citation_budget(self):
        query = "Is Cedar Store required by Atlas Index for release v1.2?"
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "version-polarity.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                rows = (
                    ("positive.md", "For release 1.2, Atlas Index is dependent on Cedar Store."),
                    ("denial.md", "Cedar Store is no longer required by Atlas Index in version v1.2."),
                    ("later.md", "Atlas Index is independent of Cedar Store in version 1.2.0."),
                    ("reversed.md", "For version 1.2, Cedar Store requires Atlas Index."),
                    ("unscoped.md", "Atlas Index requires Cedar Store."),
                    ("invalid.md", "For release 1.2, Atlas Index requires Cedar Store in version 1.2."),
                )
                for name, text in reversed(rows):
                    idx.add_source("file", name, name, text)
                hits = search(idx, query, limit=2)
                self.assertEqual({doc["location"] for doc in hits}, {"positive.md", "denial.md"})
                self.assertTrue(all(doc["evidence_quality"] == 3 for doc in hits))
                answer = build_conversation_answer(query, idx, memory, limit=2)
                self.assertIn("Evidence confidence: Conflicting", answer)
                for name, text in rows[:2]:
                    self.assertIn(name, answer)
                    self.assertIn(text, answer)
                for name, _ in rows[2:]:
                    self.assertNotIn(name, answer)
                limited = build_conversation_answer(query, idx, memory, limit=1)
                self.assertIn("Evidence confidence: Conflicting", limited)
                self.assertNotIn("Sources:", limited)
                later = build_conversation_answer("Does Atlas Index require Cedar Store in version 1.2.0?", idx, memory)
                self.assertIn("Evidence confidence: Direct support", later)
                self.assertIn("later.md", later)
                self.assertNotIn("positive.md", later)
            finally:
                memory.close()
                idx.close()

    def test_version_suffix_preserves_date_and_does_not_guess_latest(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "version-day.sqlite3")
            idx, memory = Index(path), SessionMemory(path)
            try:
                idx.add_source("file", "same.md", "Record",
                               "On June 15, 2026, Atlas Index requires Cedar Store for release v1.2.")
                idx.add_source("file", "other-day.md", "Record",
                               "On 2026-06-16, Atlas Index no longer requires Cedar Store in version 1.2.")
                idx.add_source("file", "unscoped.md", "Record", "Atlas Index requires Cedar Store.")
                answer = build_conversation_answer(
                    "As of 15 June 2026, does Atlas Index require Cedar Store in version 1.2?", idx, memory)
                self.assertIn("Evidence confidence: Direct support", answer)
                self.assertIn("same.md", answer)
                self.assertNotIn("other-day.md", answer)
                answer = build_conversation_answer(
                    "As of 2026-06-16, does Atlas Index require Cedar Store in version 1.2?", idx, memory)
                self.assertIn("no longer requires", answer)
                self.assertNotIn("same.md", answer)
                for label in ("latest", "1.2-beta", "1.2.3.4"):
                    with self.subTest(label=label):
                        answer = build_conversation_answer(
                            f"Does Atlas Index require Cedar Store in version {label}?", idx, memory)
                        self.assertIn("exact numeric release", answer)
                        self.assertNotIn("Sources:", answer)
            finally:
                memory.close()
                idx.close()
