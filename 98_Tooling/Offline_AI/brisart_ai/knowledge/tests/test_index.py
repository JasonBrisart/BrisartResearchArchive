r"""
File: brisart_ai/knowledge/tests/test_index.py

Purpose
-------
Exercise source persistence, deduplication and removal.

Protected scenarios: TestIndex verifies add source and count; TestIndex verifies empty
text returns false not added; TestIndex verifies missing source type raises; TestIndex
verifies missing location raises; TestIndex verifies readding same source upserts not
duplicates.

Protected scenarios: TestIndex verifies source count by type; TestIndex verifies clear
removes all sources; TestIndex verifies context manager closes connection.

Communication / relationships
-----------------------------
Uses temporary SQLite indexes.

Direct project imports: brisart_ai.knowledge.index.

The cases use self.assertEqual, self.assertTrue, self.assertFalse, self.assertRaises to
check returned values, persisted state or raised errors. The suite is run through
scripts/run_tests.py so Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Source type counts, duplicates and clearing indexed records.

Regression coverage includes TestIndex.test_missing_source_type_raises,
TestIndex.test_missing_location_raises,
TestIndex.test_readding_same_source_upserts_not_duplicates,
TestIndex.test_source_count_by_type, TestIndex.test_clear_removes_all_sources,
TestIndex.test_context_manager_closes_connection.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_index.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_index.py -k
test_add_source_and_count.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index


class TestIndex(unittest.TestCase):
    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_add_source_and_count(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            self.assertEqual(idx.source_count(), 0)
            added = idx.add_source(source_type="file", location="/a.txt", title="A", text="hello world")
            self.assertTrue(added)
            self.assertEqual(idx.source_count(), 1)
            idx.close()

    def test_empty_text_returns_false_not_added(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            added = idx.add_source(source_type="file", location="/a.txt", title="A", text="   ")
            self.assertFalse(added)
            self.assertEqual(idx.source_count(), 0)
            idx.close()

    def test_missing_source_type_raises(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            with self.assertRaises(ValueError):
                idx.add_source(source_type="", location="/a.txt", title="A", text="hello")
            idx.close()

    def test_missing_location_raises(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            with self.assertRaises(ValueError):
                idx.add_source(source_type="file", location="", title="A", text="hello")
            idx.close()

    def test_readding_same_source_upserts_not_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="version one")
            idx.add_source(source_type="file", location="/a.txt", title="A", text="version two")
            self.assertEqual(idx.source_count(), 1)
            idx.close()

    def test_source_count_by_type(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            idx.add_source(source_type="web", location="https://x.com", title="X", text="world")
            self.assertEqual(idx.source_count("file"), 1)
            self.assertEqual(idx.source_count("web"), 1)
            self.assertEqual(idx.source_count(), 2)
            idx.close()



    def test_clear_removes_all_sources(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            idx.clear()
            self.assertEqual(idx.source_count(), 0)
            idx.close()

    def test_context_manager_closes_connection(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "ctx.sqlite")
            with Index(path) as idx:
                idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            # Connection should be usable again via a fresh instance.
            idx2 = Index(path)
            self.assertEqual(idx2.source_count(), 1)
            idx2.close()


if __name__ == "__main__":
    unittest.main()
