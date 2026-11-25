r"""
File: brisart_ai/io/readers.py

Purpose
-------
Own the import format registry, path discovery and reader dispatch.

The extension registry is the single authority for file eligibility across the picker
and the recursive import walker. Keeping that decision here prevents the GUI from
advertising formats the reader cannot dispatch.

Public operations: is_supported (path); iter_supported_files (paths) - Yield supported
files from a mix of individual paths and folders; read_file (path) - Extract searchable
text from one supported file.

Internal helpers include _pretty_json, _rtf_to_text.

Communication / relationships
-----------------------------
Ingestion walks paths through this module; the desktop picker uses the same registry.

Folder traversal discovers candidate files; read_file then dispatches to text, markup,
or document-container extraction. Duplicate resolved paths are skipped before ingestion.

Direct project imports: brisart_ai.io.binary_readers, brisart_ai.io.extractor,
brisart_json, brisart_ai.util.

Direct importing modules include brisart_ai/io/tests/test_readers.py,
brisart_ai/knowledge/ingest.py, brisart_ai/ui/dialogs.py,
brisart_ai/ui/tests/test_source_management.py.

Settings / parameters
---------------------
SUPPORTED_EXTENSIONS and SUPPORTED_EXTENSIONLESS_NAMES control eligibility.

Module configuration and named constants: TEXT_EXTENSIONS (set, 53 entries),
BINARY_TEXT_EXTENSIONS (set, 5 entries), SUPPORTED_EXTENSIONS,
SUPPORTED_EXTENSIONLESS_NAMES (set, 5 entries).

Call signatures: is_supported(path); iter_supported_files(paths); read_file(path).

Edge cases
----------
Folders are walked recursively; repeated resolved paths are not yielded twice.

A matching extension is only a routing hint. Unsupported, inaccessible, empty, and
malformed files must not be presented as successfully extracted evidence.

Explicit exception branches or raised errors in this file include
(BrisartJSONDecodeError, TypeError), OSError, (OSError, PermissionError).

Known limitations
-----------------
Eligibility by name does not guarantee recoverable text or a valid file.

Examples
--------
read_file(Path("notes.md"))

Other callable entry points in this module include iter_supported_files, read_file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Iterator

from brisart_ai.io.binary_readers import (
    read_docx, read_odt, read_pdf_best_effort, read_pptx, read_xlsx,
)
from brisart_ai.io.extractor import csv_to_text, html_to_text
from brisart_json import BrisartJSONDecodeError, brisart_dumps, brisart_loads
from brisart_ai.util import safe_read_text

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".py", ".pyw", ".html", ".htm",
    ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".toml", ".xml",
    ".svg", ".yaml", ".yml", ".json", ".jsonl", ".ndjson", ".css",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cs", ".go", ".rs", ".sh", ".bash", ".zsh",
    ".ps1", ".bat", ".cmd", ".sql", ".tex", ".rtf", ".srt", ".vtt",
    ".properties", ".env", ".gitignore", ".dockerfile",
}
BINARY_TEXT_EXTENSIONS = {".docx", ".pptx", ".xlsx", ".odt", ".pdf"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | BINARY_TEXT_EXTENSIONS

SUPPORTED_EXTENSIONLESS_NAMES = {
    "dockerfile", "makefile", "license", "readme", "changelog",
}


def is_supported(path: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    return (
        suffix in SUPPORTED_EXTENSIONS
        or name in SUPPORTED_EXTENSIONLESS_NAMES
    )


def iter_supported_files(paths: Iterable[str]) -> Iterator[Path]:
    """Yield supported files from a mix of individual paths and folders."""
    seen = set()
    for raw in paths:
        path = Path(raw).expanduser()
        try:
            path = path.resolve()
        except OSError:
            continue
        if path.is_file():
            if is_supported(path) and path not in seen:
                seen.add(path)
                yield path
            continue
        if not path.is_dir():
            continue
        try:
            for child in path.rglob("*"):
                try:
                    if child.is_file() and is_supported(child):
                        resolved = child.resolve()
                        if resolved not in seen:
                            seen.add(resolved)
                            yield resolved
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue


def _pretty_json(raw: str) -> str:
    try:
        parsed = brisart_loads(raw)
        return brisart_dumps(parsed, indent=2, sort_keys=True)
    except (BrisartJSONDecodeError, TypeError):
        return raw


def _rtf_to_text(raw: str) -> str:
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", raw)
    raw = raw.replace("{", " ").replace("}", " ")
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def read_file(path: Path) -> str:
    """Extract searchable text from one supported file."""
    ext = path.suffix.lower()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".pptx":
        return read_pptx(path)
    if ext == ".xlsx":
        return read_xlsx(path)
    if ext == ".odt":
        return read_odt(path)
    if ext == ".pdf":
        return read_pdf_best_effort(path)
    raw = safe_read_text(path)
    if ext in {".html", ".htm", ".svg"}:
        _title, text, _links = html_to_text(raw)
        return text
    if ext == ".csv":
        return csv_to_text(raw)
    if ext == ".tsv":
        return raw.replace("\t", " | ")
    if ext == ".json":
        return _pretty_json(raw)
    if ext in {".jsonl", ".ndjson"}:
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if line:
                lines.append(_pretty_json(line))
        return "\n".join(lines)
    if ext == ".rtf":
        return _rtf_to_text(raw)
    return raw
