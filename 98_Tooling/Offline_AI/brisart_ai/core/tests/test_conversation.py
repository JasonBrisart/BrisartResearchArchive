"""
File: brisart_ai/core/tests/test_conversation.py

Purpose
-------
Exercise local-source scope and cited answers.

Protected scenarios: TestBuildConversationAnswer verifies answers from indexed file
source; TestBuildConversationAnswer verifies paraphrased question returns exact cited
excerpt; TestBuildConversationAnswer verifies empty index returns no information
message; TestBuildConversationAnswer verifies local files toggle off excludes file
sources; TestBuildConversationAnswer verifies notes toggle off excludes note sources.

Protected scenarios: TestBuildConversationAnswer verifies records question and answer to
memory; TestBuildConversationAnswer verifies historical web sources are never used as
answer evidence; TestBuildConversationAnswer verifies disabling both local sources does
not search everything.

Communication / relationships
-----------------------------
Uses temporary SQLite index and conversation memory.

Direct project imports: brisart_ai.core.conversation, brisart_ai.core.session_memory,
brisart_ai.core.settings, brisart_ai.knowledge.index.

The cases use self.assertIn, self.assertTrue, self.assertEqual to check returned values,
persisted state or raised errors. The suite is run through scripts/run_tests.py so
Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Disabled sources, historical web rows, word variants and missing evidence.

Regression coverage includes
TestBuildConversationAnswer.test_empty_index_returns_no_information_message,
TestBuildConversationAnswer.test_local_files_toggle_off_excludes_file_sources,
TestBuildConversationAnswer.test_notes_toggle_off_excludes_note_sources,
TestBuildConversationAnswer.test_records_question_and_answer_to_memory,
TestBuildConversationAnswer.test_historical_web_sources_are_never_used_as_answer_evidence,
TestBuildConversationAnswer.test_disabling_both_local_sources_does_not_search_everything.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_conversation.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/core/tests/test_conversation.py -k
test_answers_from_indexed_file_source.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings
from brisart_ai.knowledge.index import Index


class TestBuildConversationAnswer(unittest.TestCase):
    def _make(self, tmpdir):
        db_path = str(Path(tmpdir) / "test.sqlite")
        index = Index(db_path)
        memory = SessionMemory(db_path)
        settings = ResearchSettings(path=Path(tmpdir) / "settings.json")
        return index, memory, settings

    def test_answers_from_indexed_file_source(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            index.add_source(source_type="file", location="/docs/microsoft-history.txt",
                title="History of Microsoft",
                text="Microsoft was founded by Bill Gates and Paul Allen in 1975 in Albuquerque, New Mexico.",
                extension="txt", size_bytes=100)
            answer = build_conversation_answer("who founded microsoft?", index, memory, settings=settings)
            self.assertIn("Sources:", answer)
            self.assertTrue("Gates" in answer or "Allen" in answer)
            index.close(); memory.close()

    def test_paraphrased_question_returns_exact_cited_excerpt(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            try:
                index.add_source("file", "/permit.txt", "Permit rules", "Permit expiry: June 30")
                answer = build_conversation_answer("When does the permit expire?", index, memory, settings=settings)
                self.assertIn("[1] Permit expiry: June 30", answer)
                self.assertIn("/permit.txt", answer)
            finally:
                index.close()
                memory.close()

    def test_empty_index_returns_no_information_message(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            answer = build_conversation_answer("what is the meaning of life?", index, memory, settings=settings)
            self.assertIn("don't have indexed local information", answer)
            index.close(); memory.close()

    def test_local_files_toggle_off_excludes_file_sources(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            settings.set("search_local_files", False)
            index.add_source(source_type="file", location="/x.txt", title="X",
                text="unique searchable content about zebras", extension="txt", size_bytes=10)
            answer = build_conversation_answer("zebras", index, memory, settings=settings)
            self.assertIn("don't have indexed local information", answer)
            index.close(); memory.close()

    def test_notes_toggle_off_excludes_note_sources(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            settings.set("search_notes", False)
            index.add_source(source_type="note", location="note:1", title="N",
                text="unique searchable content about narwhals", extension="")
            answer = build_conversation_answer("narwhals", index, memory, settings=settings)
            self.assertIn("don't have indexed local information", answer)
            index.close(); memory.close()

    def test_records_question_and_answer_to_memory(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            build_conversation_answer("hello there", index, memory, settings=settings)
            topics = memory.recent_topics(limit=5)
            self.assertTrue(len(topics) >= 1)
            index.close(); memory.close()



    def test_historical_web_sources_are_never_used_as_answer_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            index.add_source(source_type="web", location="https://example.com/old",
                title="Old web result", text="unique searchable content about pangolins",
                extension="html")
            answer = build_conversation_answer("pangolins", index, memory, settings=settings)
            self.assertIn("don't have indexed local information", answer)
            self.assertEqual(index.source_count("web"), 1)
            index.close(); memory.close()

    def test_disabling_both_local_sources_does_not_search_everything(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            index.add_source(source_type="file", location="/x.txt", title="X",
                text="unique searchable content about zebras", extension="txt")
            settings.set("search_local_files", False)
            settings.set("search_notes", False)
            answer = build_conversation_answer("zebras", index, memory, settings=settings)
            self.assertIn("don't have indexed local information", answer)
            index.close(); memory.close()

if __name__ == "__main__":
    unittest.main()

