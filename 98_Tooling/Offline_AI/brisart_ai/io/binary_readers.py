"""Purpose
-------
Extract searchable text from Office, OpenDocument and PDF files.

This file input and extraction component defines `read_docx`, `read_pptx`, `read_xlsx`,
`read_odt`, `read_pdf_best_effort`. Its scope is deliberately limited to the responsibilities
visible in this file rather than duplicating the application-wide workflow. Callers use these
declarations through the module interface; the file is not a separate service or background
daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Readers provide text to ingestion. PDF stream decompression uses the external Brisart Native API.

The direct in-project imports visible in this module are the standard library and its direct
caller. Public entry points `doctype`; this identifies where behavior is invoked without
implying a separate hidden dependency. Higher-level coordination remains with the calling
layer rather than being introduced here.

Settings / parameters
---------------------
Selected XML is limited to 16 MiB per member, 64 MiB total and 2,048 members. The PDF raw read honors max_bytes.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Unusable input yields no text. DTD-bearing XML members are skipped. Over-budget packages yield no text.

The behaviors documented above must be read together with the actual branches in
binary_readers.py; a caller must not infer success from an empty, rejected, or unsupported
result. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
PPTX order uses numeric part names, not presentation relationships. PDF support is approximate;
the raw read limit does not constrain stream expansion. Readers are not a sandbox.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
read_docx(Path("local-notes.docx"))

For a concrete entry point, inspect `read_docx`, `read_pptx`, `read_xlsx`, `read_odt`,
`read_pdf_best_effort`; invoke it through the existing application entry point or its
documented caller. The example above is illustrative of this file's present interface; do not
treat it as an instruction to create additional state or call private functions directly.
"""

from __future__ import annotations

import re
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

_MAX_XML_MEMBER_BYTES = 16 * 1024 * 1024
_MAX_XML_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_XML_MEMBERS = 2048


class _NoDoctypeTreeBuilder(ElementTree.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ElementTree.ParseError("DTDs are not allowed in imported documents")


def _xml_text(payload: bytes) -> str:
    try:
        parser = ElementTree.XMLParser(target=_NoDoctypeTreeBuilder())
        root = ElementTree.fromstring(payload, parser=parser)
    except (ElementTree.ParseError, LookupError, ValueError):
        return ""
    return "\n".join(node.text.strip() for node in root.iter() if node.text and node.text.strip())


def _read_package_xml(path: Path, select, order=None) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            members = [info for info in archive.infolist() if not info.is_dir() and select(info.filename)]
            if (len(members) > _MAX_XML_MEMBERS
                    or any(info.file_size > _MAX_XML_MEMBER_BYTES for info in members)
                    or sum(info.file_size for info in members) > _MAX_XML_TOTAL_BYTES):
                return ""
            if order is not None:
                members.sort(key=lambda info: order(info.filename))
            parts = []
            remaining = _MAX_XML_TOTAL_BYTES
            for info in members:
                limit = min(_MAX_XML_MEMBER_BYTES, remaining)
                with archive.open(info) as member:
                    payload = member.read(limit + 1)
                if len(payload) > limit:
                    return ""
                remaining -= len(payload)
                if text := _xml_text(payload):
                    parts.append(text)
            return "\n".join(parts)
    except (OSError, EOFError, RuntimeError, ValueError, zipfile.BadZipFile, zlib.error, NotImplementedError):
        return ""


def read_docx(path: Path) -> str:
    return _read_package_xml(path, lambda name: name.startswith("word/") and name.endswith(".xml"))


def _pptx_order(name: str):
    number = re.search(r"([0-9]{1,12})\.xml$", name)
    return ("/notesSlides/" in name, int(number[1]) if number else float("inf"), name)


def read_pptx(path: Path) -> str:
    return _read_package_xml(path, lambda name: name.endswith(".xml") and
                             name.startswith(("ppt/slides/", "ppt/notesSlides/")), _pptx_order)


def read_xlsx(path: Path) -> str:
    return _read_package_xml(path, lambda name: name == "xl/sharedStrings.xml" or
                             (name.startswith("xl/worksheets/") and name.endswith(".xml")),
                             lambda name: name)


def read_odt(path: Path) -> str:
    return _read_package_xml(path, lambda name: name == "content.xml")


def read_pdf_best_effort(path: Path, max_bytes: int = 10_000_000) -> str:
    if max_bytes <= 0:
        return ""
    try:
        with path.open("rb") as source:
            raw = source.read(max_bytes)
    except OSError:
        return ""
    chunks = []
    for match in re.finditer(rb"\((?:\\.|[^\\)])*\)", raw):
        value = match.group(0)[1:-1]
        value = value.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b"\n")
        decoded = value.decode("utf-8", "replace")
        if decoded.strip():
            chunks.append(decoded.strip())
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL):
        from brisart_inflate import brisart_zlib_decompress

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
