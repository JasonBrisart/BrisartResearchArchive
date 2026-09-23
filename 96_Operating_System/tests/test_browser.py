"""
tests/test_browser.py

Purpose
-------
Unit tests for `brisartos/apps/browser.py` (`TextHTMLParser`,
`normalize_url`, `fetch_page`). This is BrisartOS's one built-in
application that talks to the network, so per the project's own
dependency-free, offline-first philosophy (`docs/DEPENDENCY_POLICY.md`),
these tests never make a real network call: `fetch_page()` is exercised
against a mocked `urlopen`, using only `unittest.mock` from the standard
library, so the whole suite stays runnable in an air-gapped environment
with zero network access and zero external test dependencies.

Communication relationships
----------------------------
- `open_url()` (the CLI entry point used by `main()`) calls `fetch_page()`
  then prints `page["text"]`; this file tests `fetch_page()`'s return
  value directly rather than capturing `open_url()`'s console output,
  since the interesting behavior (URL normalization, size limits, HTML
  text extraction) all lives in `fetch_page()` and `TextHTMLParser`.
- `TextHTMLParser` is a `html.parser.HTMLParser` subclass with no
  BrisartOS-specific dependencies of its own; it is tested here purely
  against literal HTML strings, independent of any real network fetch.

Settings / parameters
----------------------
- `MAX_PAGE_BYTES` (1,000,000 by default) bounds how much of a response
  body `fetch_page()` will read via `response.read(MAX_PAGE_BYTES + 1)`;
  exceeding it must raise `ValueError` rather than silently truncating
  (which could otherwise hand a module or user a corrupted/incomplete
  page with no indication anything was cut off).
- `normalize_url(value)` prefixes bare host/path strings with `"https://"`
  when `urlparse` finds no scheme, but leaves an already-schemed URL (even
  `http://`) untouched.
- `TextHTMLParser` skips the text content of `<script>`, `<style>`, and
  `<noscript>` elements entirely (tracked via a `skip_depth` counter so
  nested skip tags do not prematurely re-enable text capture), and treats
  `<p>`, `<div>`, `<br>`, `<h1>`-`<h3>`, and `<li>` as line-break points.

Edge-case behavior
-------------------
- `normalize_url("")` (or a value that is only whitespace) must raise
  `ValueError("URL is required")` rather than silently normalizing to
  `"https://"`.
- `TextHTMLParser.text()` must collapse internal runs of whitespace within
  a single text node (`" ".join(data.split())`) and must drop entirely
  empty lines produced by adjacent block-tag boundaries, so the final
  output has no stray blank lines or doubled spaces.
- A nested `<script><style>...</style></script>` must still be fully
  skipped even though `skip_depth` increments twice, because the depth
  counter -- not a boolean flag -- correctly re-enables capture only once
  both closing tags have been seen.
- `fetch_page()` must decode the response body using the charset reported
  by `response.headers.get_content_charset()`, falling back to `"utf-8"`
  when the mocked response declares none.
"""
import unittest
from unittest.mock import MagicMock, patch

from _support import add_repo_root_to_syspath

add_repo_root_to_syspath()

from brisartos.apps import browser  # noqa: E402


class NormalizeUrlTests(unittest.TestCase):
    def test_bare_host_gets_https_prefix(self):
        self.assertEqual(browser.normalize_url("example.com"), "https://example.com")

    def test_already_schemed_https_url_is_unchanged(self):
        self.assertEqual(
            browser.normalize_url("https://example.com/page"),
            "https://example.com/page",
        )

    def test_already_schemed_http_url_is_left_as_http(self):
        self.assertEqual(
            browser.normalize_url("http://example.com/page"),
            "http://example.com/page",
        )

    def test_surrounding_whitespace_is_stripped(self):
        self.assertEqual(
            browser.normalize_url("  example.com  "), "https://example.com"
        )

    def test_empty_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            browser.normalize_url("")

    def test_whitespace_only_string_raises_value_error(self):
        with self.assertRaises(ValueError):
            browser.normalize_url("   ")


class TextHTMLParserTests(unittest.TestCase):
    def _extract(self, html):
        parser = browser.TextHTMLParser()
        parser.feed(html)
        return parser.text()

    def test_plain_paragraph_text_is_extracted(self):
        result = self._extract("<p>Hello world</p>")
        self.assertEqual(result, "Hello world")

    def test_script_content_is_skipped(self):
        html = "<p>Before</p><script>alert('x');</script><p>After</p>"
        result = self._extract(html)
        self.assertNotIn("alert", result)
        self.assertIn("Before", result)
        self.assertIn("After", result)

    def test_style_content_is_skipped(self):
        html = "<style>body { color: red; }</style><p>Visible</p>"
        result = self._extract(html)
        self.assertNotIn("color", result)
        self.assertIn("Visible", result)

    def test_nested_skip_tags_still_fully_skipped(self):
        html = "<script><style>should not appear</style></script><p>Visible</p>"
        result = self._extract(html)
        self.assertNotIn("should not appear", result)
        self.assertIn("Visible", result)

    def test_internal_whitespace_is_collapsed(self):
        result = self._extract("<p>Hello    \n\n   world</p>")
        self.assertEqual(result, "Hello world")

    def test_block_tags_produce_line_breaks(self):
        html = "<div>First</div><div>Second</div>"
        result = self._extract(html)
        self.assertEqual(result, "First\nSecond")

    def test_list_items_produce_separate_lines(self):
        html = "<li>one</li><li>two</li>"
        result = self._extract(html)
        self.assertEqual(result.splitlines(), ["one", "two"])

    def test_empty_document_yields_empty_text(self):
        self.assertEqual(self._extract(""), "")


class FetchPageMockedNetworkTests(unittest.TestCase):
    """
    All tests in this class replace urllib.request.urlopen with a mock so
    no real network connection is ever attempted, keeping this suite
    consistent with BrisartOS's offline-first, dependency-free policy.
    """

    def _make_fake_response(self, body_bytes, charset=None, final_url="https://example.com"):
        response = MagicMock()
        response.read.return_value = body_bytes
        response.headers.get_content_charset.return_value = charset
        response.geturl.return_value = final_url
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        return response

    def test_fetch_page_returns_url_source_and_extracted_text(self):
        body = b"<html><body><p>Hi there</p></body></html>"
        fake_response = self._make_fake_response(body, charset="utf-8")
        with patch("brisartos.apps.browser.urlopen", return_value=fake_response):
            page = browser.fetch_page("example.com")
        self.assertEqual(page["url"], "https://example.com")
        self.assertEqual(page["source"], body.decode("utf-8"))
        self.assertEqual(page["text"], "Hi there")

    def test_fetch_page_defaults_to_utf8_when_no_charset_declared(self):
        body = "<p>caf\u00e9</p>".encode("utf-8")
        fake_response = self._make_fake_response(body, charset=None)
        with patch("brisartos.apps.browser.urlopen", return_value=fake_response):
            page = browser.fetch_page("example.com")
        self.assertIn("caf\u00e9", page["text"])

    def test_fetch_page_raises_value_error_when_body_exceeds_max_bytes(self):
        oversized_body = b"x" * (browser.MAX_PAGE_BYTES + 1)
        fake_response = self._make_fake_response(oversized_body)
        with patch("brisartos.apps.browser.urlopen", return_value=fake_response):
            with self.assertRaises(ValueError):
                browser.fetch_page("example.com")

    def test_fetch_page_normalizes_url_before_requesting(self):
        body = b"<p>ok</p>"
        fake_response = self._make_fake_response(body)
        with patch(
            "brisartos.apps.browser.urlopen", return_value=fake_response
        ) as mock_urlopen:
            browser.fetch_page("example.com/path")
        request_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(request_arg.full_url, "https://example.com/path")

    def test_fetch_page_sets_user_agent_header(self):
        body = b"<p>ok</p>"
        fake_response = self._make_fake_response(body)
        with patch(
            "brisartos.apps.browser.urlopen", return_value=fake_response
        ) as mock_urlopen:
            browser.fetch_page("example.com")
        request_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request_arg.get_header("User-agent"), browser.USER_AGENT
        )


if __name__ == "__main__":
    unittest.main()
