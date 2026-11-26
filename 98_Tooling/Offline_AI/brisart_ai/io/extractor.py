r"""
File: brisart_ai/io/extractor.py

Purpose
-------
Convert local HTML and CSV to searchable plain text.

This module converts local markup and delimited data into a textual representation
suitable for indexing. HTML URL handling is for reference interpretation, not network
fetching.

Public operations: HTMLTextExtractor.handle_starttag (self, tag, attrs);
HTMLTextExtractor.handle_startendtag (self, tag, attrs); HTMLTextExtractor.handle_endtag
(self, tag); HTMLTextExtractor.handle_data (self, data).

Public operations: HTMLTextExtractor.result (self); html_to_text (source, base_url='') -
Convert HTML into a title, readable text, and discovered links; csv_to_text (source) -
Convert CSV text into searchable pipe-separated text.

Internal helpers include HTMLTextExtractor.__init__,
HTMLTextExtractor._is_reference_marker.

Communication / relationships
-----------------------------
readers.py chooses the extractor; HTML parsing and URL joining use external Native APIs.

The external markup parser and URL joiner provide primitive operations. This module
decides what content is useful to retain as evidence.

Direct project imports: brisart_markup, brisart_url, brisart_ai.util.

Direct importing modules include brisart_ai/io/readers.py,
brisart_ai/io/tests/test_extractor.py.

Concrete calls within this file include self._is_reference_marker, self.handle_starttag,
self.text_parts.append, self.title_parts.append, self.links.append.

Settings / parameters
---------------------
Callers supply HTML or CSV text; HTML may have a base URL.

Call signatures: HTMLTextExtractor.handle_starttag(self, tag, attrs);
HTMLTextExtractor.handle_startendtag(self, tag, attrs);
HTMLTextExtractor.handle_endtag(self, tag); HTMLTextExtractor.handle_data(self, data);
HTMLTextExtractor.result(self).

Call signatures: html_to_text(source, base_url=''); csv_to_text(source).

Edge cases
----------
HTML reference targets can be formatted without requesting them.

Markup order, tables and whitespace are simplified; parsing is not a browser renderer
and embedded scripts are not executed.

Explicit exception branches or raised errors in this file include Exception, (csv.Error,
UnicodeError).

Known limitations
-----------------
HTML is not rendered as a browser page; scripts are not executed.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
csv_to_text("material,count\nsteel,4")

Other callable entry points in this module include HTMLTextExtractor.handle_startendtag,
HTMLTextExtractor.handle_endtag, HTMLTextExtractor.handle_data,
HTMLTextExtractor.result, html_to_text, csv_to_text.
"""

from __future__ import annotations

import csv
import io
import re
from typing import List, Optional, Tuple

from brisart_markup import BrisartMarkupParser, brisart_unescape
from brisart_url import brisart_urljoin
from brisart_ai.util import normalize_url


class HTMLTextExtractor(BrisartMarkupParser):
    """Extract readable text, page titles, and links from HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}
    BLOCK_TAGS = {
        "p", "div", "section", "article", "aside", "header", "footer",
        "main", "nav", "br", "li", "ul", "ol", "table", "tr", "td",
        "th", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
    }
    REFERENCE_MARKER_TAGS = {"sup"}
    REFERENCE_MARKER_CLASSES = {"reference", "cite-bracket", "citation"}

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._skip_depth = 0
        self._reference_skip_depth = 0
        self._in_title = False

    def _is_reference_marker(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> bool:
        if tag not in self.REFERENCE_MARKER_TAGS:
            return False
        for name, value in attrs:
            if name.casefold() != "class" or not value:
                continue
            classes = {token.casefold() for token in value.split()}
            if classes & self.REFERENCE_MARKER_CLASSES:
                return True
        return False

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if self._is_reference_marker(tag, attrs):
            self._reference_skip_depth += 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                absolute = brisart_urljoin(self.base_url, href)
                link = normalize_url(absolute)
                if link.startswith(("http://", "https://")):
                    self.links.append(link)
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.REFERENCE_MARKER_TAGS and self._reference_skip_depth:
            self._reference_skip_depth -= 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._reference_skip_depth:
            return
        cleaned = brisart_unescape(data)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned).strip()
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned + " ")

    def result(self) -> Tuple[str, str, List[str]]:
        title = " ".join(self.title_parts).strip()
        text = "".join(self.text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        unique_links: List[str] = []
        seen = set()
        for link in self.links:
            if link and link not in seen:
                seen.add(link)
                unique_links.append(link)
        return title, text, unique_links


def html_to_text(source: str, base_url: str = "") -> Tuple[str, str, List[str]]:
    """Convert HTML into a title, readable text, and discovered links."""
    parser = HTMLTextExtractor(base_url=base_url)
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        pass
    return parser.result()


def csv_to_text(source: str) -> str:
    """Convert CSV text into searchable pipe-separated text."""
    output: List[str] = []
    try:
        reader = csv.reader(io.StringIO(source))
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if any(cleaned):
                output.append(" | ".join(cleaned))
        return "\n".join(output)
    except (csv.Error, UnicodeError):
        pass
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line:
            output.append(line.replace(",", " | "))
    return "\n".join(output)
