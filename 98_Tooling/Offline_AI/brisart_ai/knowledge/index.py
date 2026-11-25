r"""
File: brisart_ai/knowledge/index.py

Purpose
-------
Store indexed source text and token postings, and remove selected index records.

The SQLite index owns the durable source rows and token postings that Brisart retrieval
consumes. SQLite supplies storage and transactions; no SQLite full-text ranking
algorithm determines relevance.

Public operations: Index.add_source (self, source_type, location, title, text,
content_hash='', size_bytes=0, extension=''); Index.list_sources (self) - Return
imported files and notes, newest first, for source management; Index.file_for_note
(self, source_id) - Return the indexed title, path and text of an imported file;
Index.remove_source (self, source_id).

Public operations: Index.remove_sources (self, source_ids) - Remove a batch atomically;
dependent index records cascade in SQLite; Index.source_count (self, source_type=None);
Index.clear (self); Index.close (self).

Public operations: filter_source_rows (rows, query) - Case-insensitive substring search
over type, title and location.

Internal helpers include Index.__init__, Index._init_schema, Index.__enter__,
Index.__exit__.

Communication / relationships
-----------------------------
Ingest and vault write sources; the ranker reads postings; the desktop uses source
metadata for management.

Ingestion writes source text and postings; the ranker reads them; vault notes and
source-management actions update related rows. Batch removal is transactional and relies
on foreign-key behavior for dependent index records.

Direct project imports: brisart_ai, brisart_ai.util.

Direct importing modules include brisart_ai/core/service.py,
brisart_ai/core/tests/test_conversation.py, brisart_ai/knowledge/tests/test_index.py,
brisart_ai/knowledge/tests/test_ingest.py, brisart_ai/knowledge/tests/test_ranker.py,
brisart_ai/knowledge/tests/test_vault.py, brisart_ai/tests/test_state.py,
brisart_ai/ui/app.py, brisart_ai/ui/dialogs.py,
brisart_ai/ui/tests/test_source_management.py, cli.py, run.py, plus 1 more.

Concrete calls within this file include state.index_path, sqlite3.connect,
self.conn.execute, self._init_schema, self.conn.executescript, self.conn.commit,
self.conn.close, self.close, self.remove_sources, self.conn.executemany.

Settings / parameters
---------------------
The caller may select a database path or :memory:.

Module configuration and named constants: DEFAULT_DB.

Call signatures: Index.add_source(self, source_type, location, title, text,
content_hash='', size_bytes=0, extension=''); Index.list_sources(self);
Index.file_for_note(self, source_id); Index.remove_source(self, source_id);
Index.remove_sources(self, source_ids).

Call signatures: Index.source_count(self, source_type=None); Index.clear(self);
Index.close(self); filter_source_rows(rows, query).

Edge cases
----------
Batch removal is atomic; SQLite cascades dependent rows. Original files and independent
saved excerpts are not deleted.

A removed index entry does not erase its original file or separately saved note
snapshots. Source text represents the last indexed copy, not a live filesystem view.

Explicit exception branches or raised errors in this file include ValueError,
RuntimeError.

Known limitations
-----------------
SQLite provides record storage and lookup, not FTS ranking.

Examples
--------
index.remove_sources([2, 3])

Other callable entry points in this module include Index.list_sources,
Index.file_for_note, Index.remove_source, Index.remove_sources, Index.source_count,
Index.clear, Index.close, plus 1 more.
"""

from __future__ import annotations

import collections
import sqlite3
from pathlib import Path
from typing import Optional

from brisart_ai import state
from brisart_ai.util import now_ts, stable_hash, tokenize

DEFAULT_DB = str(state.index_path())


class Index:
    """Local SQLite-backed source and term index."""

    def __init__(self, path: str = DEFAULT_DB):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                location TEXT NOT NULL,
                title TEXT,
                text TEXT NOT NULL,
                content_hash TEXT,
                size_bytes INTEGER,
                extension TEXT,
                indexed_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS terms (
                term TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                tf INTEGER NOT NULL,
                PRIMARY KEY(term, source_id),
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_terms_term ON terms(term);
            CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
            CREATE INDEX IF NOT EXISTS idx_sources_location ON sources(location);
            CREATE INDEX IF NOT EXISTS idx_sources_indexed_at ON sources(indexed_at);
            """
        )
        self.conn.commit()



    def add_source(
        self, source_type: str, location: str, title: str, text: str,
        content_hash: str = "", size_bytes: int = 0, extension: str = "",
    ) -> bool:
        cleaned_type = str(source_type or "").strip()
        cleaned_location = str(location or "").strip()
        cleaned_title = str(title or "").strip()
        cleaned_text = str(text or "").strip()
        cleaned_hash = str(content_hash or "").strip()
        cleaned_extension = str(extension or "").strip().lower()

        if not cleaned_type:
            raise ValueError("source_type cannot be empty")
        if not cleaned_location:
            raise ValueError("location cannot be empty")
        if not cleaned_text:
            return False

        source_key = stable_hash(cleaned_type + "|" + cleaned_location)
        indexed_at = now_ts()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO sources(source_key, source_type, location, title, text,
                    content_hash, size_bytes, extension, indexed_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_type=excluded.source_type, location=excluded.location,
                    title=excluded.title, text=excluded.text, content_hash=excluded.content_hash,
                    size_bytes=excluded.size_bytes, extension=excluded.extension,
                    indexed_at=excluded.indexed_at
                """,
                (source_key, cleaned_type, cleaned_location, cleaned_title, cleaned_text,
                 cleaned_hash, max(0, int(size_bytes or 0)), cleaned_extension, indexed_at),
            )
            row = self.conn.execute("SELECT id FROM sources WHERE source_key = ?", (source_key,)).fetchone()
            if row is None:
                raise RuntimeError("Source was written but could not be retrieved")
            source_id = int(row[0])
            self.conn.execute("DELETE FROM terms WHERE source_id = ?", (source_id,))
            counts = collections.Counter(
                tokenize(cleaned_title + " " + cleaned_location + " " + cleaned_text)
            )
            if counts:
                self.conn.executemany(
                    "INSERT OR REPLACE INTO terms(term, source_id, tf) VALUES(?,?,?)",
                    [(term, source_id, int(tf)) for term, tf in counts.items()],
                )
        return True

    def list_sources(self):
        """Return imported files and notes, newest first, for source management."""
        return self.conn.execute(
            "SELECT id, source_type, title, location FROM sources "
            "WHERE source_type IN ('file', 'note') ORDER BY id DESC"
        ).fetchall()

    def file_for_note(self, source_id: int):
        """Return the indexed title, path and text of an imported file."""
        return self.conn.execute(
            "SELECT title, location, text FROM sources WHERE id = ? AND source_type = 'file'",
            (source_id,),
        ).fetchone()

    def remove_source(self, source_id: int) -> bool:
        return bool(self.remove_sources((source_id,)))

    def remove_sources(self, source_ids) -> int:
        """Remove a batch atomically; dependent index records cascade in SQLite."""
        removed = 0
        with self.conn:
            for source_id in dict.fromkeys(source_ids):
                row = self.conn.execute(
                    "SELECT source_type, location FROM sources WHERE id = ?", (source_id,)
                ).fetchone()
                if row is None or row[0] not in ("file", "note"):
                    continue
                if row[0] == "note" and row[1].startswith("note:") and row[1][5:].isascii() and row[1][5:].isdigit():
                    if self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes'").fetchone():
                        self.conn.execute("DELETE FROM notes WHERE id = ?", (int(row[1][5:]),))
                self.conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
                removed += 1
        return removed

    def source_count(self, source_type: Optional[str] = None) -> int:
        if source_type:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM sources WHERE source_type = ?", (source_type,)
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()
        return int(row[0] if row else 0)

    def clear(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM terms")
            self.conn.execute("DELETE FROM sources")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Index":
        return self

    def __exit__(self, exception_type, exception_value, traceback) -> None:
        self.close()


__all__ = ["DEFAULT_DB", "Index"]


def filter_source_rows(rows, query: str):
    """Case-insensitive substring search over type, title and location."""
    terms = query.casefold().split()
    return [row for row in rows if all(
        term in " ".join(str(value) for value in row[1:]).casefold()
        for term in terms
    )]


