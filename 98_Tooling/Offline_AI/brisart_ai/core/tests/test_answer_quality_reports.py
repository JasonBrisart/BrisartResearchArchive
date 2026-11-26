"""Purpose
-------
Replay two reported BrisartAI answer-quality failures against a temporary index.

This regression test module defines `TestReportedQuestionQuality`, `TestAnswerVariants`. Its
scope is deliberately limited to the responsibilities visible in this file rather than
duplicating the application-wide workflow. Its fixtures and assertions describe observable
behavior without changing the installed application.

Communication / relationships
-----------------------------
Uses the same conversation, ranking and citation path as desktop queries.

The direct in-project imports visible in this module are `brisart_ai.core.conversation`,
`brisart_ai.core.session_memory`, `brisart_ai.knowledge.index`. Test methods `setUp`, `ask`,
`test_tfl_mention_only_does_not_pass_for_explanation`,
`test_tfl_supported_answer_cites_mechanism_and_feedback`,
`test_framework_co_mentions_do_not_pass_for_comparison`; this identifies where behavior is
invoked without implying a separate hidden dependency. The test runner supplies the test
lifecycle and any temporary fixtures.

Settings / parameters
---------------------
Fixture paths are relative labels. No user index, settings or network needed.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Name-only matches, a missing comparison side, and supporting evidence buried
among unrelated hits. Citation references must resolve to indexed evidence.

The behaviors documented above must be read together with the actual branches in
test_answer_quality_reports.py; assertions should reject regressions rather than merely
checking file layout. Error handling, input validation, and early returns remain the
responsibility of the concrete functions in this module. No additional fallback is created by
this documentation.

Known limitations
-----------------
Small curated excerpts, not a reconstruction of the user's full archive.
This is a release gate: failing checks are not marked as expected failures.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_answer_quality_reports.py -q

For a concrete entry point, inspect `TestReportedQuestionQuality`, `TestAnswerVariants`; run
this module through the existing project test runner with its actual test path. The example
above is illustrative of this file's present interface; do not treat it as an instruction to
create additional state or call private functions directly.
"""

import re
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.knowledge.index import Index

TFL_QUESTION = "how does tfl work?"
COMPARISON_QUESTION = "how does riet compare to sst?"
TFL_NOISE = {
    "HOW_TO_TEACH_TFL.md": "# How to Teach TFL\nName it (TFL language).",
    "test_tfl.py": "File: tests/test_tfl.py\nProve that TFL's trial generation, stimulus library, feedback wording, and imports work.",
    "Temporal Feedback Loop - Exploratory Edition - v1.md": "TFL proposes that they are three surface expressions of one recursive mechanism.",
}
COMPARISON_NOISE = {
    "INTERACTIONS.md": "The current ARPE specification does not formally declare directed dependencies on PFT, TFL, SST, IRE, VRIF, RIET, or PCT.",
    "exports/PROJECT_CONTEXT.md": "Introduced system-level integration with PFT, SST, IRE, TCRF, VRIF, and RIET.",
    "old/PROJECT_CONTEXT.md": 'FRAMEWORK_DISPLAY_ORDER = ["TFL", "SST", "IRE", "PFT", "PCT", "RIET"]',
}
# Curated test paraphrases of the framework/integration notes, not verbatim sources.
TFL_MECHANISM = (
    "TFL proposes that current sensory input and retrieved memory inform a predictive simulation. "
    "The integrated state is carried forward as a prior for the next cycle. "
    "Affective intensity gates whether the simulation persists across cycles."
)
RIET_ROLE = "RIET describes a boundary condition in which prediction can dominate perception under ambiguity."
SST_ROLE = "SST describes identity stabilization and evaluates potential outcomes against identity constraints."
INSUFFICIENT = r"(?i)(may not answer|none .*directly answers|not enough|don't have|insufficient|can't (?:answer|compare)|cannot (?:answer|compare)|could not (?:answer|compare)|only found)"


class TestReportedQuestionQuality(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        db = str(Path(temp.name) / "answers.sqlite3")
        self.index = Index(db)
        self.addCleanup(self.index.close)
        self.memory = SessionMemory(db)
        self.addCleanup(self.memory.close)

    def ask(self, query, files):
        for path, text in files.items():
            self.index.add_source("file", path, Path(path).name, text)
        return build_conversation_answer(query, self.index, self.memory)

    def test_tfl_mention_only_does_not_pass_for_explanation(self):
        answer = self.ask(TFL_QUESTION, TFL_NOISE)
        self.assertRegex(answer, INSUFFICIENT)

    def test_tfl_supported_answer_cites_mechanism_and_feedback(self):
        answer = self.ask(TFL_QUESTION, {**TFL_NOISE, "TFL mechanism.md": TFL_MECHANISM})
        body, _, sources = answer.partition("\nSources:")
        self.assertRegex(sources, r"(?m)^\[\d+\].*:: TFL mechanism\.md$")
        for clause in (r"sensory (?:input|evidence)", r"retrieved memory", r"predictive simulation", r"next cycle"):
            with self.subTest(clause=clause):
                self.assertRegex(body.lower(), clause)

    def test_framework_co_mentions_do_not_pass_for_comparison(self):
        answer = self.ask(COMPARISON_QUESTION, COMPARISON_NOISE)
        self.assertRegex(answer, INSUFFICIENT)

    def test_comparison_names_missing_evidence_for_one_side(self):
        answer = self.ask(COMPARISON_QUESTION, {**COMPARISON_NOISE, "RIET role.md": RIET_ROLE})
        body = answer.partition("\nSources:")[0]
        self.assertRegex(body, INSUFFICIENT)
        self.assertRegex(body, r"(?i)\bSST\b")

    def test_comparison_supports_both_roles_from_separate_sources(self):
        answer = self.ask(COMPARISON_QUESTION, {
            **COMPARISON_NOISE, "RIET role.md": RIET_ROLE, "SST role.md": SST_ROLE,
        })
        body, _, sources = answer.partition("\nSources:")
        for path, concept in (("RIET role.md", "boundary condition"), ("SST role.md", "identity stabilization")):
            with self.subTest(source=path):
                entry = re.search(r"(?m)^\[(\d+)\].*:: " + re.escape(path) + r"$", sources)
                self.assertIsNotNone(entry, answer)
                excerpt = re.search(r"(?im)^\[" + entry[1] + r"\].*" + concept, body)
                self.assertIsNotNone(excerpt, answer)

    def test_control_citations_map_to_the_right_indexed_source(self):
        text = "The workshop permit fee is $37."
        answer = self.ask("what is the workshop permit fee?", {"permit.md": text})
        body, _, sources = answer.partition("\nSources:")
        reference = re.search(r"(?m)^\[(\d+)\].*\$37", body)
        self.assertIsNotNone(reference, answer)
        self.assertRegex(sources, r"(?m)^\[" + reference[1] + r"\].*:: permit\.md$")


class TestAnswerVariants(unittest.TestCase):
    """Independent prompts and corpus perturbations through the public query path."""

    def replay(self, query, files):
        with TemporaryDirectory() as folder:
            path = str(Path(folder) / "variants.sqlite3")
            index, memory = Index(path), SessionMemory(path)
            try:
                for name, text in files:
                    index.add_source("file", name, Path(name).name, text)
                return build_conversation_answer(query, index, memory)
            finally:
                memory.close()
                index.close()

    def test_mechanism_paraphrases_and_index_order(self):
        useful = ("TFL-primary.md", TFL_MECHANISM)
        for query in ("how does TFL work?", "How does TFL operate?", "Explain how TFL works.",
                      "How does TFL function?", "How does the TFL work?"):
            for reverse in (False, True):
                with self.subTest(query=query, reverse=reverse):
                    files = [*TFL_NOISE.items(), useful]
                    answer = self.replay(query, files[::-1] if reverse else files)
                    self.assertIn("next cycle", answer)
                    self.assertIn("TFL-primary.md", answer)
                    self.assertNotIn("HOW_TO_TEACH_TFL.md", answer)

    def test_comparison_phrasings_with_and_without_roles(self):
        for query in ("RIET vs SST", "compare SST and RIET", "RIET versus SST", COMPARISON_QUESTION):
            for evidence in ("both", "riet", "sst", "neither"):
                with self.subTest(query=query, evidence=evidence):
                    files = list(COMPARISON_NOISE.items())
                    if evidence in ("both", "riet"):
                        files.append(("riet-role.md", RIET_ROLE))
                    if evidence in ("both", "sst"):
                        files.append(("sst-role.md", SST_ROLE))
                    answer = self.replay(query, files)
                    self.assertNotIn("FRAMEWORK_DISPLAY_ORDER", answer)
                    self.assertNotIn("PROJECT_CONTEXT.md", answer)
                    if evidence == "both":
                        self.assertIn("boundary condition", answer)
                        self.assertIn("identity stabilization", answer)
                    else:
                        self.assertRegex(answer, INSUFFICIENT)
                        if evidence in ("riet", "sst"):
                            missing = {"riet": "SST", "sst": "RIET"}[evidence]
                            self.assertIn(f"Missing support for: {missing}", answer)

    def test_does_not_take_a_continuation_across_paragraphs(self):
        text = "A valve controls water flow.\n\nIt controls the air pressure in an unrelated device."
        answer = self.replay("how does a valve work?", [("valve.md", text)])
        self.assertIn("water flow", answer)
        self.assertNotIn("air pressure", answer)

    def test_non_framework_comparison_uses_direct_evidence(self):
        answer = self.replay("compare trains versus ferries", [
            ("schedule.md", "Ferries and trains are listed in the timetable."),
            ("routes.md", "Unlike trains, ferries serve island routes directly."),
        ])
        self.assertIn("island routes", answer)
        self.assertNotIn("schedule.md", answer)

    def test_expiry_does_not_infer_date_from_renewal(self):
        query = "When does the workshop permit expire?"
        renewal = ("renewal.md", "The workshop permit renewal deadline is June 30.")
        answer = self.replay(query, [renewal])
        self.assertRegex(answer, INSUFFICIENT)
        self.assertNotIn("June 30", answer)
        answer = self.replay(query, [renewal, ("expiry.md", "The workshop permit expires on July 15.")])
        self.assertIn("July 15", answer)
        self.assertIn("expiry.md", answer)
        self.assertNotIn("June 30", answer)
