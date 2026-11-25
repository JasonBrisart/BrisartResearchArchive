r"""
File: brisart_ai/knowledge/tests/test_ingest.py

Purpose
-------
Exercise supported files entering the local index.

Protected scenarios: TestIngestPaths verifies ingests supported files in folder;
TestIngestPaths verifies skips empty files; TestIngestPaths verifies unsupported
extension not ingested; TestIngestPaths verifies single file path; TestIngestPaths
verifies returns zero for nonexistent path.

Communication / relationships
-----------------------------
Uses temporary input files and index.

Direct project imports: brisart_ai.knowledge.index, brisart_ai.knowledge.ingest.

The cases use self.assertEqual to check returned values, persisted state or raised
errors. The suite is run through scripts/run_tests.py so Native API discovery happens
before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Invalid, duplicate or empty import inputs.

Regression coverage includes TestIngestPaths.test_ingests_supported_files_in_folder,
TestIngestPaths.test_skips_empty_files,
TestIngestPaths.test_unsupported_extension_not_ingested,
TestIngestPaths.test_single_file_path,
TestIngestPaths.test_returns_zero_for_nonexistent_path.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

Examples
--------
python scripts/run_tests.py brisart_ai/knowledge/tests/test_ingest.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/knowledge/tests/test_ingest.py -k
test_skips_empty_files.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ingest import ingest_paths


class TestIngestPaths(unittest.TestCase):
    def test_ingests_supported_files_in_folder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.txt").write_text("hello world")
            (root / "b.md").write_text("markdown content")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 2)
            idx.close()

    def test_skips_empty_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "empty.txt").write_text("   ")
            (root / "real.txt").write_text("actual content here")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 1)
            idx.close()

    def test_unsupported_extension_not_ingested(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "image.png").write_bytes(b"\x89PNG")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(root)], idx)
            self.assertEqual(count, 0)
            idx.close()

    def test_single_file_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "single.txt"
            f.write_text("single file content")
            idx = Index(str(root / "idx.sqlite"))
            count = ingest_paths([str(f)], idx)
            self.assertEqual(count, 1)
            idx.close()

    def test_returns_zero_for_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as d:
            idx = Index(str(Path(d) / "idx.sqlite"))
            count = ingest_paths(["/nonexistent/path"], idx)
            self.assertEqual(count, 0)
            idx.close()


if __name__ == "__main__":
    unittest.main()
