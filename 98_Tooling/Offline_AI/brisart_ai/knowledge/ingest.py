r"""
File: brisart_ai/knowledge/ingest.py

Purpose
-------
Discover supported local imports and write their extracted text to the index.

Ingestion is the boundary between filesystem extraction and durable indexed evidence. It
does not own ranking or GUI file selection.

Public operations: ingest_paths (paths, index) - Ingest supported files from paths into
the supplied index.

Communication / relationships
-----------------------------
Uses io.readers for discovery and extraction and delegates writes to Index.

The reader walks supported paths and extracts text; the index stores source metadata and
token postings. Reimport is needed after a source changes on disk.

Direct project imports: brisart_ai.io.readers, brisart_ai.util.

Direct importing modules include brisart_ai/core/service.py,
brisart_ai/knowledge/tests/test_ingest.py.

Concrete calls within this file include index.add_source.

Settings / parameters
---------------------
Accepts a mixture of file and directory paths.

Call signatures: ingest_paths(paths, index).

Edge cases
----------
Unreadable or empty inputs do not become useful indexed evidence.

A supported filename can still be unreadable or yield no useful text. Folder traversal
should not produce multiple records for the same resolved input path.

Explicit exception branches or raised errors in this file include (OSError,
UnicodeError, ValueError, RuntimeError), Exception, OSError.

Known limitations
-----------------
Indexes a snapshot; it does not watch the filesystem for edits.

Examples
--------
ingest_paths(["notes.md", "reference/"], index)
"""

from __future__ import annotations

from typing import Iterable

from brisart_ai.io.readers import iter_supported_files, read_file
from brisart_ai.util import file_hash


def ingest_paths(paths: Iterable[str], index) -> int:
    """Ingest supported files from paths into the supplied index."""
    count = 0
    for path in iter_supported_files(paths):
        try:
            text = read_file(path)
            if not text or not text.strip():
                print(f"SKIPPED EMPTY: {path}")
                continue
            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = 0
            try:
                content_hash = file_hash(path)
            except OSError as exc:
                print(f"WARN: could not hash {path}: {exc}")
                content_hash = ""
            indexed = index.add_source(
                source_type="file", location=str(path), title=path.name, text=text,
                content_hash=content_hash, size_bytes=size_bytes,
                extension=path.suffix.lower(),
            )
            if indexed:
                count += 1
                print(f"INGESTED: {path}")
            else:
                print(f"SKIPPED EMPTY: {path}")
        except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
            print(f"WARN: could not ingest {path}: {exc}")
        except Exception as exc:
            print(f"WARN: unexpected ingestion failure for {path}: {exc}")
    return count


__all__ = ["ingest_paths"]
