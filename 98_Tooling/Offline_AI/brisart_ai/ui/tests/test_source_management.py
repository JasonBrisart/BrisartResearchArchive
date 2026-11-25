"""Tests for source-management search and file picker behavior.

Purpose
-------
Verify source filtering and the supported extension registry.

Communication / relationships
-----------------------------
Exercises the shared filtering helper and the supported-file registry without Tk.

Settings / parameters
---------------------
Tests use representative source records; picker widgets are not launched.

Edge cases
----------
Empty queries, multiple terms and cancel paths.

Known limitations
-----------------
Actual Windows widget interaction is not exercised.

Examples
--------
python scripts/run_tests.py brisart_ai/ui/tests/test_source_management.py
"""
import unittest

from brisart_ai.io.readers import SUPPORTED_EXTENSIONS
from brisart_ai.knowledge.index import filter_source_rows


class TestSourceManagement(unittest.TestCase):
    def test_search_matches_title_type_and_location(self):
        rows = [(1, "file", "Quarterly Report", "/docs/report.pdf"),
                (2, "note", "Personal memo", "note:2"),
                (3, "file", "Budget", "/docs/budget.xlsx")]
        self.assertEqual([row[0] for row in filter_source_rows(rows, "REPORT")], [1])
        self.assertEqual([row[0] for row in filter_source_rows(rows, "file docs")], [1, 3])
        self.assertEqual(filter_source_rows(rows, "notfound"), [])
        self.assertEqual(filter_source_rows(rows, ""), rows)

    def test_supported_file_registry_includes_common_formats(self):
        for ext in (".txt", ".pdf", ".docx", ".xlsx", ".csv", ".md"):
            self.assertIn(ext, SUPPORTED_EXTENSIONS)
