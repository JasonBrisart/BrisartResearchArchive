"""
File: brisart_ai/io/tests/test_binary_readers.py

Purpose
-------
Regress bounded XML, DTD rejection, numeric slide ordering and bounded PDF reads.

Exercise document-container and simple PDF extraction.

Protected scenarios: TestReadDocx verifies extracts text from document xml; TestReadDocx
verifies corrupt docx returns empty string; TestReadPptx verifies extracts slide and
notes text; TestReadXlsx verifies extracts shared strings and worksheet; TestReadOdt
verifies extracts content xml text.

Protected scenarios: TestReadOdt verifies missing content xml returns empty;
TestReadPdfBestEffort verifies extracts literal parenthesized text;
TestReadPdfBestEffort verifies extracts text from real deflate compressed stream;
TestReadPdfBestEffort verifies undecompressable stream is skipped not raised;
TestReadPdfBestEffort verifies nonexistent file returns empty string.

Communication / relationships
-----------------------------
Uses small local document fixtures.

Direct project imports: brisart_ai.io.binary_readers.

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
Missing document content and compressed text streams.

Explicit exception branches or raised errors in this file include Exception.

Regression coverage includes TestReadOdt.test_extracts_content_xml_text,
TestReadOdt.test_missing_content_xml_returns_empty,
TestReadPdfBestEffort.test_extracts_literal_parenthesized_text,
TestReadPdfBestEffort.test_extracts_text_from_real_deflate_compressed_stream,
TestReadPdfBestEffort.test_undecompressable_stream_is_skipped_not_raised,
TestReadPdfBestEffort.test_nonexistent_file_returns_empty_string.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/io/tests/test_binary_readers.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/io/tests/test_binary_readers.py -k
test_corrupt_docx_returns_empty_string.
"""

import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

from brisart_ai.io import binary_readers
from brisart_ai.io.binary_readers import read_docx, read_odt, read_pdf_best_effort, read_pptx, read_xlsx


class TestReadDocx(unittest.TestCase):
    def test_extracts_text_from_document_xml(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.docx"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("word/document.xml",
                    '<?xml version="1.0"?><w:document xmlns:w="ns"><w:body>'
                    '<w:p><w:r><w:t>Hello Document</w:t></w:r></w:p></w:body></w:document>')
            self.assertIn("Hello Document", read_docx(path))

    def test_corrupt_docx_returns_empty_string(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad.docx"
            path.write_bytes(b"not a zip file")
            self.assertEqual(read_docx(path), "")


class TestReadPptx(unittest.TestCase):
    def test_extracts_slide_and_notes_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.pptx"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("ppt/slides/slide1.xml",
                    '<?xml version="1.0"?><p:sld xmlns:p="ns1" xmlns:a="ns2"><a:t>Slide Title</a:t></p:sld>')
                z.writestr("ppt/notesSlides/notesSlide1.xml",
                    '<?xml version="1.0"?><p:notes xmlns:p="ns1" xmlns:a="ns2"><a:t>Speaker note</a:t></p:notes>')
            text = read_pptx(path)
            self.assertIn("Slide Title", text)
            self.assertIn("Speaker note", text)


class TestReadXlsx(unittest.TestCase):
    def test_extracts_shared_strings_and_worksheet(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.xlsx"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("xl/sharedStrings.xml",
                    '<?xml version="1.0"?><sst xmlns="ns"><si><t>Header</t></si></sst>')
                z.writestr("xl/worksheets/sheet1.xml",
                    '<?xml version="1.0"?><worksheet xmlns="ns"><sheetData>'
                    '<row><c><v>123</v></c></row></sheetData></worksheet>')
            text = read_xlsx(path)
            self.assertIn("Header", text)


class TestReadOdt(unittest.TestCase):
    def test_extracts_content_xml_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.odt"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("content.xml",
                    '<?xml version="1.0"?><office:document xmlns:text="ns" xmlns:office="ns2">'
                    '<text:p>ODT paragraph</text:p></office:document>')
            self.assertIn("ODT paragraph", read_odt(path))

    def test_missing_content_xml_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "empty.odt"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("other.xml", "<x/>")
            self.assertEqual(read_odt(path), "")


class TestReadPdfBestEffort(unittest.TestCase):
    def test_extracts_literal_parenthesized_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.pdf"
            path.write_bytes(b"%PDF-1.4\n(Hello PDF World) Tj\n%%EOF")
            text = read_pdf_best_effort(path)
            self.assertIn("Hello PDF World", text)

    def test_extracts_text_from_real_deflate_compressed_stream(self):
        content_stream = b"(Hello from a PDF) Tj (Second sentence here) Tj"
        compressed = zlib.compress(content_stream)
        fake_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Length " + str(len(compressed)).encode() + b" /Filter /FlateDecode >>\n"
            b"stream\n" + compressed + b"\nendstream\nendobj\n%%EOF"
        )
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "compressed.pdf"
            path.write_bytes(fake_pdf)
            text = read_pdf_best_effort(path)
            self.assertIn("Hello from a PDF", text)
            self.assertIn("Second sentence here", text)

    def test_undecompressable_stream_is_skipped_not_raised(self):
        fake_pdf = b"%PDF-1.4\nstream\nnot valid deflate data at all\nendstream\n%%EOF"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "bad_stream.pdf"
            path.write_bytes(fake_pdf)
            try:
                read_pdf_best_effort(path)
            except Exception as exc:
                self.fail(f"read_pdf_best_effort raised unexpectedly: {exc}")

    def test_nonexistent_file_returns_empty_string(self):
        result = read_pdf_best_effort(Path("/nonexistent/path/file.pdf"))
        self.assertEqual(result, "")



class TestImportBoundaries(unittest.TestCase):
    def test_dtd_is_rejected_even_in_utf16_xml(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "notes.odt"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("content.xml", '<!DOCTYPE content><content>Text</content>'.encode("utf-16"))
            self.assertEqual(read_odt(path), "")

    def test_each_package_budget_is_enforced_before_opening_members(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "large.docx"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", "<p>First</p>")
                archive.writestr("word/header1.xml", "<p>Later</p>")
            for name, limit in (("_MAX_XML_MEMBER_BYTES", 8), ("_MAX_XML_TOTAL_BYTES", 20),
                                ("_MAX_XML_MEMBERS", 1)):
                with self.subTest(budget=name), patch.object(binary_readers, name, limit):
                    with patch.object(zipfile.ZipFile, "open", side_effect=AssertionError("member opened")):
                        self.assertEqual(read_docx(path), "")
            self.assertEqual(read_docx(path), "First\nLater")

    def test_slides_follow_numeric_part_order(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "order.pptx"
            with zipfile.ZipFile(path, "w") as archive:
                for number in (10, 2, 1):
                    archive.writestr(f"ppt/slides/slide{number}.xml", f"<t>Slide {number}</t>")
            self.assertEqual(read_pptx(path), "Slide 1\nSlide 2\nSlide 10")

    def test_pdf_reads_only_the_requested_byte_budget(self):
        path = MagicMock(spec=Path)
        stream = path.open.return_value.__enter__.return_value
        stream.read.return_value = b"(Text)"
        self.assertEqual(read_pdf_best_effort(path, max_bytes=6), "Text")
        stream.read.assert_called_once_with(6)
        path.read_bytes.assert_not_called()

if __name__ == "__main__":
    unittest.main()

