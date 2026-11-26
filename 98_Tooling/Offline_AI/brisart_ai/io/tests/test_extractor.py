"""
File: brisart_ai/io/tests/test_extractor.py

Purpose
-------
Exercise HTML and CSV text extraction.

Protected scenarios: TestHtmlToText verifies extracts title text and links;
TestHtmlToText verifies script content excluded from text; TestHtmlToText verifies style
content excluded from text; TestHtmlToText verifies reference citation marker is
stripped; TestHtmlToText verifies ordinary superscript not stripped.

Protected scenarios: TestHtmlToText verifies links are deduplicated; TestHtmlToText
verifies non http links excluded; TestHtmlToText verifies malformed html does not raise;
TestHtmlToText verifies block tags separated by newlines; TestCsvToText verifies basic
csv conversion.

Protected scenarios: TestCsvToText verifies empty rows skipped; TestCsvToText verifies
single column; TestCsvToText verifies empty input.

Communication / relationships
-----------------------------
Uses inline markup and CSV fixtures.

Direct project imports: brisart_ai.io.extractor.

The cases use self.assertEqual, self.assertIn, self.assertNotIn to check returned
values, persisted state or raised errors. The suite is run through scripts/run_tests.py
so Native API discovery happens before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Skipped HTML content, headings, links and empty input.

Explicit exception branches or raised errors in this file include Exception.

Regression coverage includes TestHtmlToText.test_malformed_html_does_not_raise,
TestHtmlToText.test_block_tags_separated_by_newlines,
TestCsvToText.test_basic_csv_conversion, TestCsvToText.test_empty_rows_skipped,
TestCsvToText.test_single_column, TestCsvToText.test_empty_input.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/io/tests/test_extractor.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/io/tests/test_extractor.py -k
test_script_content_excluded_from_text.
"""

import unittest
from brisart_ai.io.extractor import HTMLTextExtractor, csv_to_text, html_to_text


class TestHtmlToText(unittest.TestCase):
    def test_extracts_title_text_and_links(self):
        html = '''
        <html><head><title>Test Page &amp; More</title></head>
        <body>
        <p>Hello <b>World</b>. This is a <a href="/relative/link">link</a>.</p>
        </body></html>
        '''
        title, text, links = html_to_text(html, base_url="https://example.com/page")
        self.assertEqual(title, "Test Page & More")
        self.assertIn("Hello", text)
        self.assertIn("World", text)
        self.assertEqual(links, ["https://example.com/relative/link"])

    def test_script_content_excluded_from_text(self):
        html = "<script>var x = 1;</script><p>Visible text</p>"
        _title, text, _links = html_to_text(html)
        self.assertNotIn("var x", text)
        self.assertIn("Visible text", text)

    def test_style_content_excluded_from_text(self):
        html = "<style>.a { color: red; }</style><p>Visible</p>"
        _title, text, _links = html_to_text(html)
        self.assertNotIn("color: red", text)
        self.assertIn("Visible", text)

    def test_reference_citation_marker_is_stripped(self):
        # MediaWiki-style footnote marker should not leak into extracted text.
        html = '<p>Citation<sup class="reference">[3]</sup> here.</p>'
        _title, text, _links = html_to_text(html)
        self.assertNotIn("[3]", text)
        self.assertIn("Citation", text)
        self.assertIn("here", text)

    def test_ordinary_superscript_not_stripped(self):
        html = "<p>10<sup>2</sup> meters</p>"
        _title, text, _links = html_to_text(html)
        self.assertIn("2", text)

    def test_links_are_deduplicated(self):
        html = '<a href="/x">one</a><a href="/x">two</a>'
        _title, _text, links = html_to_text(html, base_url="https://example.com/")
        self.assertEqual(links, ["https://example.com/x"])

    def test_non_http_links_excluded(self):
        html = '<a href="javascript:void(0)">bad</a><a href="/good">good</a>'
        _title, _text, links = html_to_text(html, base_url="https://example.com/")
        self.assertEqual(links, ["https://example.com/good"])

    def test_malformed_html_does_not_raise(self):
        html = "<p>unterminated <b>bold text"
        try:
            html_to_text(html)
        except Exception as exc:
            self.fail(f"html_to_text raised unexpectedly: {exc}")

    def test_block_tags_separated_by_newlines(self):
        html = "<p>First</p><p>Second</p>"
        _title, text, _links = html_to_text(html)
        self.assertIn("First", text)
        self.assertIn("Second", text)


class TestCsvToText(unittest.TestCase):
    def test_basic_csv_conversion(self):
        result = csv_to_text("a,b,c\n1,2,3\n")
        self.assertEqual(result, "a | b | c\n1 | 2 | 3")

    def test_empty_rows_skipped(self):
        result = csv_to_text("a,b\n\n1,2\n")
        self.assertEqual(result, "a | b\n1 | 2")

    def test_single_column(self):
        result = csv_to_text("only\nvalue\n")
        self.assertEqual(result, "only\nvalue")

    def test_empty_input(self):
        self.assertEqual(csv_to_text(""), "")


if __name__ == "__main__":
    unittest.main()
