"""
File: brisart_ai/io/tests/test_readers.py

Purpose
-------
Exercise local filename support, discovery and read dispatch.

Protected scenarios: TestIsSupported verifies known text extension; TestIsSupported
verifies known binary extension; TestIsSupported verifies unsupported extension;
TestIsSupported verifies extensionless wellknown names; TestIsSupported verifies case
insensitive extension match.

Protected scenarios: TestIterSupportedFiles verifies yields single supported file;
TestIterSupportedFiles verifies skips unsupported single file; TestIterSupportedFiles
verifies walks folder recursively; TestIterSupportedFiles verifies deduplicates same
file reached twice; TestIterSupportedFiles verifies nonexistent path does not raise.

Protected scenarios: TestReadFile verifies reads bom encoded unicode without leaking
marker; TestReadFile verifies reads plain text file; TestReadFile verifies reads csv as
pipe separated; TestReadFile verifies reads tsv as pipe separated; TestReadFile verifies
reads html as extracted text.

Protected scenarios: TestReadFile verifies reads valid json pretty printed; TestReadFile
verifies reads invalid json as raw text; TestReadFile verifies reads jsonl line by line;
TestReadFile verifies reads rtf stripped.

Communication / relationships
-----------------------------
Uses temporary files and directories.

Direct project imports: brisart_ai.io.readers.

The cases use self.assertTrue, self.assertFalse, self.assertEqual, self.assertIn to
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
BOM-encoded text, unsupported inputs and nested folders.

Explicit exception branches or raised errors in this file include Exception.

Regression coverage includes TestReadFile.test_reads_tsv_as_pipe_separated,
TestReadFile.test_reads_html_as_extracted_text,
TestReadFile.test_reads_valid_json_pretty_printed,
TestReadFile.test_reads_invalid_json_as_raw_text,
TestReadFile.test_reads_jsonl_line_by_line, TestReadFile.test_reads_rtf_stripped.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/io/tests/test_readers.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/io/tests/test_readers.py -k
test_known_binary_extension.
"""

import tempfile
import unittest
from pathlib import Path
from brisart_ai.io.readers import is_supported, iter_supported_files, read_file


class TestIsSupported(unittest.TestCase):
    def test_known_text_extension(self):
        self.assertTrue(is_supported(Path("notes.txt")))
        self.assertTrue(is_supported(Path("script.py")))
        self.assertTrue(is_supported(Path("data.json")))

    def test_known_binary_extension(self):
        self.assertTrue(is_supported(Path("doc.docx")))
        self.assertTrue(is_supported(Path("report.pdf")))

    def test_unsupported_extension(self):
        self.assertFalse(is_supported(Path("image.png")))
        self.assertFalse(is_supported(Path("archive.zip")))

    def test_extensionless_wellknown_names(self):
        self.assertTrue(is_supported(Path("README")))
        self.assertTrue(is_supported(Path("Dockerfile")))
        self.assertTrue(is_supported(Path("LICENSE")))

    def test_case_insensitive_extension_match(self):
        self.assertTrue(is_supported(Path("FILE.TXT")))


class TestIterSupportedFiles(unittest.TestCase):
    def test_yields_single_supported_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.txt"
            f.write_text("hello")
            found = list(iter_supported_files([str(f)]))
            self.assertEqual(len(found), 1)

    def test_skips_unsupported_single_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.png"
            f.write_bytes(b"\x89PNG")
            found = list(iter_supported_files([str(f)]))
            self.assertEqual(found, [])

    def test_walks_folder_recursively(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sub").mkdir()
            (root / "a.txt").write_text("1")
            (root / "sub" / "b.md").write_text("2")
            (root / "c.png").write_bytes(b"\x89PNG")
            found = sorted(p.name for p in iter_supported_files([str(root)]))
            self.assertEqual(found, ["a.txt", "b.md"])

    def test_deduplicates_same_file_reached_twice(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            f = root / "a.txt"
            f.write_text("1")
            found = list(iter_supported_files([str(root), str(f)]))
            self.assertEqual(len(found), 1)

    def test_nonexistent_path_does_not_raise(self):
        try:
            list(iter_supported_files(["/nonexistent/path/xyz"]))
        except Exception as exc:
            self.fail(f"iter_supported_files raised unexpectedly: {exc}")


class TestReadFile(unittest.TestCase):
    def test_reads_bom_encoded_unicode_without_leaking_marker(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "notes.txt"
            for encoding in ("utf-16", "utf-8-sig"):
                path.write_bytes("Text from a lab notebook".encode(encoding))
                self.assertEqual(read_file(path), "Text from a lab notebook")

    def test_reads_plain_text_file(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.txt"
            f.write_text("Hello, world!")
            self.assertEqual(read_file(f), "Hello, world!")

    def test_reads_csv_as_pipe_separated(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.csv"
            f.write_text("a,b\n1,2\n")
            self.assertEqual(read_file(f), "a | b\n1 | 2")

    def test_reads_tsv_as_pipe_separated(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.tsv"
            f.write_text("a\tb\n1\t2\n")
            self.assertIn("|", read_file(f))

    def test_reads_html_as_extracted_text(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.html"
            f.write_text("<p>Hello HTML</p>")
            self.assertIn("Hello HTML", read_file(f))

    def test_reads_valid_json_pretty_printed(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.json"
            f.write_text('{"b":1,"a":2}')
            result = read_file(f)
            self.assertIn('"a"', result)
            self.assertIn("\n", result)  # pretty-printed with indent

    def test_reads_invalid_json_as_raw_text(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.json"
            f.write_text("{not valid json")
            self.assertEqual(read_file(f), "{not valid json")

    def test_reads_jsonl_line_by_line(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.jsonl"
            f.write_text('{"x":1}\n{"y":2}\n')
            result = read_file(f)
            self.assertIn('"x"', result)
            self.assertIn('"y"', result)

    def test_reads_rtf_stripped(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "a.rtf"
            f.write_text(r"{\rtf1\ansi Hello RTF text}")
            result = read_file(f)
            self.assertIn("Hello RTF text", result)


if __name__ == "__main__":
    unittest.main()
