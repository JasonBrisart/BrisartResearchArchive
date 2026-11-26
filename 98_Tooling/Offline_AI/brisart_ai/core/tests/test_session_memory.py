"""
File: brisart_ai/core/tests/test_session_memory.py

Purpose
-------
Exercise persisted topic ordering and compaction.

Protected scenarios: TestSessionMemory verifies add and recent topics; TestSessionMemory
verifies both added topics are present; TestSessionMemory verifies same timestamp
returns lainsert first; TestSessionMemory verifies empty content is dropped;
TestSessionMemory verifies content compressed to tokens.

Protected scenarios: TestSessionMemory verifies duplicate topics deduplicated;
TestSessionMemory verifies limit respected.

Communication / relationships
-----------------------------
Uses a temporary SQLite database.

Direct project imports: brisart_ai.core.session_memory.

The cases use self.assertTrue, self.assertIn, self.assertEqual, self.assertLess,
self.assertLessEqual to check returned values, persisted state or raised errors. The
suite is run through scripts/run_tests.py so Native API discovery happens before
collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Empty input, duplicate topics and identical timestamps.

Regression coverage includes TestSessionMemory.test_both_added_topics_are_present,
TestSessionMemory.test_same_timestamp_returns_latest_insert_first,
TestSessionMemory.test_empty_content_is_dropped,
TestSessionMemory.test_content_compressed_to_tokens,
TestSessionMemory.test_duplicate_topics_deduplicated,
TestSessionMemory.test_limit_respected.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/core/tests/test_session_memory.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/core/tests/test_session_memory.py -k
test_add_and_recent_topics.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.session_memory import SessionMemory


class TestSessionMemory(unittest.TestCase):
    def _make(self, tmpdir):
        return SessionMemory(str(Path(tmpdir) / "mem.sqlite3"))

    def test_add_and_recent_topics(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "who invented microsoft")
            topics = mem.recent_topics(limit=5)
            self.assertTrue(len(topics) >= 1)
            mem.close()

    def test_both_added_topics_are_present(self):
        # now_ts() has 1-second resolution, so two adds in the same test
        # run don't reliably produce distinguishable ORDER BY timestamps --
        # this checks both topics survive, not strict insertion order.
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "first question about cats")
            mem.add("user", "second question about dogs")
            topics = mem.recent_topics(limit=5)
            joined = " ".join(topics)
            self.assertIn("cats", joined)
            self.assertIn("dogs", joined)
            mem.close()

    def test_same_timestamp_returns_latest_insert_first(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            try:
                with patch("brisart_ai.core.session_memory.now_ts", return_value=1):
                    mem.add("user", "earlier question")
                    mem.add("user", "next question")
                self.assertEqual(mem.recent_topics(1), ["next question"])
            finally:
                mem.close()

    def test_empty_content_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "   ")
            self.assertEqual(mem.recent_topics(limit=5), [])
            mem.close()

    def test_content_compressed_to_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "This is a very long sentence with many stop words like the and of in a row")
            topics = mem.recent_topics(limit=5)
            self.assertEqual(len(topics), 1)
            # Compressed topic should be shorter than the original sentence.
            self.assertLess(len(topics[0]), len("This is a very long sentence with many stop words like the and of in a row"))
            mem.close()

    def test_duplicate_topics_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "cats")
            mem.add("user", "cats")
            topics = mem.recent_topics(limit=5)
            self.assertEqual(len(topics), len(set(topics)))
            mem.close()

    def test_limit_respected(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            for i in range(10):
                mem.add("user", f"unique topic number {i}")
            topics = mem.recent_topics(limit=3)
            self.assertLessEqual(len(topics), 3)
            mem.close()


if __name__ == "__main__":
    unittest.main()

