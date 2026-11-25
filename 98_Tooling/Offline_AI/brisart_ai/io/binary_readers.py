r"""
File: brisart_ai/io/binary_readers.py

Purpose
-------
Extract searchable text from common document containers and simple PDFs.

This module owns container-specific text extraction, not general file discovery or
relevance scoring. It reads supported document packages and PDF text streams without
calling external web services.

Public operations: read_docx (path); read_pptx (path); read_xlsx (path); read_odt
(path).

Public operations: read_pdf_best_effort (path, max_bytes=10000000).

Internal helpers include _xml_text.

Communication / relationships
-----------------------------
readers.py dispatches formats here; ZIP/XML parsing uses the standard library and PDF
inflation uses a Native API.

ZIP/XML handling is performed in the reader, while compressed PDF content uses the
external Brisart inflate helper. Failures are handled at the format boundary rather than
changing the index schema.

Direct project imports: brisart_inflate.

Direct importing modules include brisart_ai/io/readers.py,
brisart_ai/io/tests/test_binary_readers.py.

Settings / parameters
---------------------
The requested reader selects the container layout.

Call signatures: read_docx(path); read_pptx(path); read_xlsx(path); read_odt(path);
read_pdf_best_effort(path, max_bytes=10000000).

Edge cases
----------
Missing or invalid document parts can yield no text.

Extracted text can omit layout, images, scanned pages and unsupported encodings. A
document that opens successfully can still produce no searchable text.

Explicit exception branches or raised errors in this file include Exception.

Known limitations
-----------------
Best-effort extraction does not preserve page layout, perform OCR or implement all PDF
encodings.

Examples
--------
read_docx(Path("notebook.docx"))

Other callable entry points in this module include read_pptx, read_xlsx, read_odt,
read_pdf_best_effort.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from brisart_inflate import brisart_zlib_decompress


def _xml_text(xml_bytes: bytes) -> str:
    try:
        root = ElementTree.fromstring(xml_bytes)
    except Exception:
        return ""
    parts = []
    for node in root.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())
    return "\n".join(parts)


def read_docx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.startswith("word/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_pptx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in sorted(archive.namelist()):
                if name.startswith("ppt/slides/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
                elif name.startswith("ppt/notesSlides/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_xlsx(path: Path) -> str:
    parts = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            if "xl/sharedStrings.xml" in names:
                text = _xml_text(archive.read("xl/sharedStrings.xml"))
                if text:
                    parts.append(text)
            for name in sorted(names):
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    text = _xml_text(archive.read(name))
                    if text:
                        parts.append(text)
    except Exception:
        return ""
    return "\n".join(parts)


def read_odt(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            if "content.xml" in archive.namelist():
                return _xml_text(archive.read("content.xml"))
    except Exception:
        return ""
    return ""


def read_pdf_best_effort(path: Path, max_bytes: int = 10_000_000) -> str:
    try:
        raw = path.read_bytes()[:max_bytes]
    except Exception:
        return ""
    chunks = []
    for match in re.finditer(rb"\((?:\\.|[^\\)])*\)", raw):
        value = match.group(0)[1:-1]
        value = value.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b"\n")
        decoded = value.decode("utf-8", "replace")
        if decoded.strip():
            chunks.append(decoded.strip())
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL):
        stream = match.group(1).strip(b"\r\n")
        try:
            inflated = brisart_zlib_decompress(stream)
        except Exception:
            continue
        for text_match in re.finditer(rb"\((?:\\.|[^\\)])*\)", inflated):
            value = text_match.group(0)[1:-1]
            value = value.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b"\n")
            decoded = value.decode("utf-8", "replace")
            if decoded.strip():
                chunks.append(decoded.strip())
    text = "\n".join(chunks)
    text = re.sub(r"\s+", " ", text).strip()
    return text
