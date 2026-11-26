"""
File: brisart_ai/ui/tests/test_source_management.py

Purpose
-------
Exercise source-list filtering and picker-registry coverage.

Protected scenarios: TestSourceManagement verifies search matches title type and
location; TestSourceManagement verifies supported file registry includes common formats.

Communication / relationships
-----------------------------
Uses representative metadata rows and supported extensions.

Direct project imports: brisart_ai.io.readers, brisart_ai.knowledge.index.

The cases use self.assertEqual, self.assertIn to check returned values, persisted state
or raised errors. The suite is run through scripts/run_tests.py so Native API discovery
happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Case, multiword filters and no results.

Regression coverage includes
TestSourceManagement.test_search_matches_title_type_and_location,
TestSourceManagement.test_supported_file_registry_includes_common_formats.

Known limitations
-----------------
Headless tests do not validate live Tk or Windows Explorer interactions.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/ui/tests/test_source_management.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/ui/tests/test_source_management.py -k
test_supported_file_registry_includes_common_formats.
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
