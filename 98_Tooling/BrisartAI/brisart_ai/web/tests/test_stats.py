"""
File: brisart_ai/web/tests/test_stats.py

Purpose
-------
Tests for brisart_ai/web/stats.py -- CrawlStats.

Communication / relationships
-----------------------------
Direct module imports: io, unittest, contextlib, brisart_ai.web.stats.

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

import io
import unittest
from contextlib import redirect_stdout
from brisart_ai.web.stats import CrawlStats


class TestCrawlStats(unittest.TestCase):
    def test_defaults_are_zero(self):
        s = CrawlStats()
        self.assertEqual(s.requested, 0)
        self.assertEqual(s.indexed, 0)
        self.assertEqual(s.skipped_duplicates, 0)
        self.assertEqual(s.skipped_empty, 0)
        self.assertEqual(s.errors, 0)

    def test_fields_can_be_incremented(self):
        s = CrawlStats()
        s.requested += 5
        s.indexed += 3
        self.assertEqual(s.requested, 5)
        self.assertEqual(s.indexed, 3)

    def test_print_summary_includes_all_counters(self):
        s = CrawlStats(requested=10, indexed=7, skipped_duplicates=1, skipped_empty=1, errors=1)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            s.print_summary()
        output = buffer.getvalue()
        self.assertIn("Requested: 10", output)
        self.assertIn("Indexed: 7", output)
        self.assertIn("Duplicates: 1", output)
        self.assertIn("Empty pages: 1", output)
        self.assertIn("Errors: 1", output)


if __name__ == "__main__":
    unittest.main()

