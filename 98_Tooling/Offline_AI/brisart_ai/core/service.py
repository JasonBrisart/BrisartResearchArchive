r"""
File: brisart_ai/core/service.py

Purpose
-------
Coordinate index, settings, memory, imports, notes and source removal for the two
launchers.

This is the common application boundary used by the headless CLI and Tk desktop. It owns
the lifetime of Index, SessionMemory and ResearchSettings so the two entry points cannot
drift into separate research implementations.

Public operations: BrisartService.counts (self); BrisartService.ask (self, text,
limit=8) - Answer a question; BrisartService.import_paths (self, paths);
BrisartService.list_sources (self).

Public operations: BrisartService.remove_source (self, source_id);
BrisartService.remove_sources (self, source_ids); BrisartService.get_source_for_note
(self, source_id); BrisartService.add_source_note (self, title, observation, source_id,
passage) - Save an exact excerpt with its provenance as a durable local note.

Public operations: BrisartService.add_note (self, title, body);
BrisartService.list_notes (self, limit=20); BrisartService.search_notes (self, query,
limit=10); BrisartService.toggle_setting (self, key).

Public operations: BrisartService.settings_panel_text (self); BrisartService.close
(self).

Internal helpers include BrisartService.__init__, BrisartService._extract_diagnostics.

Communication / relationships
-----------------------------
Desktop and CLI call this service; mutations go to knowledge modules.

Source-backed notes preserve a validated copy of the quoted passage with its original
location. Index removal is a separate mutation: deleting an imported file entry must not
delete its disk original or a previously saved note excerpt.

Direct project imports: brisart_ai.core.conversation, brisart_ai.core.session_memory,
brisart_ai.core.settings, brisart_ai.knowledge.index, brisart_ai.knowledge.ingest,
brisart_ai.knowledge.vault.

Direct importing modules include brisart_ai/core/tests/test_service_headless.py,
brisart_ai/ui/app.py, cli.py.

Concrete calls within this file include self.index.source_count,
self._extract_diagnostics, self.counts, self.index.list_sources,
self.index.remove_source, self.index.remove_sources, self.index.file_for_note,
self.get_source_for_note, self.add_note, self.settings.resolve_key,
self.settings.toggle, self.settings.render.

Settings / parameters
---------------------
Accepts an index path and optional settings path.

Call signatures: BrisartService.counts(self); BrisartService.ask(self, text, limit=8);
BrisartService.import_paths(self, paths); BrisartService.list_sources(self);
BrisartService.remove_source(self, source_id).

Call signatures: BrisartService.remove_sources(self, source_ids);
BrisartService.get_source_for_note(self, source_id);
BrisartService.add_source_note(self, title, observation, source_id, passage);
BrisartService.add_note(self, title, body); BrisartService.list_notes(self, limit=20).

Call signatures: BrisartService.search_notes(self, query, limit=10);
BrisartService.toggle_setting(self, key); BrisartService.settings_panel_text(self);
BrisartService.close(self).

Edge cases
----------
A sourced note rejects a stale source or an excerpt not present in the indexed text.

A sourced note is rejected if the selected indexed file has disappeared or if the quoted
text no longer occurs in the indexed snapshot. The service closes handles when its owner
is done.

Explicit exception branches or raised errors in this file include ValueError.

Known limitations
-----------------
Dropping an indexed file does not remove saved note excerpts or the original disk file.

Examples
--------
BrisartService(db_path).ask("When does the permit expire?")

Other callable entry points in this module include BrisartService.ask,
BrisartService.import_paths, BrisartService.list_sources, BrisartService.remove_source,
BrisartService.remove_sources, BrisartService.get_source_for_note,
BrisartService.add_source_note, plus 6 more.
"""

from __future__ import annotations

import contextlib
import io
import threading
from pathlib import Path
from typing import List, Optional, Tuple

from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings, TOGGLE_LABELS
from brisart_ai.knowledge.index import DEFAULT_DB, Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.vault import add_note, list_notes, reindex_missing_notes, search_notes

_DIAGNOSTIC_MARKERS = ("WARN", "SKIP", "ERROR")
_MAX_DIAGNOSTIC_LINES = 5


class BrisartService:
    """Owns one Index, SessionMemory, and ResearchSettings for the app's lifetime."""

    def __init__(self, db_path: str = DEFAULT_DB, settings_path: Optional[str] = None):
        self.db_path = db_path
        self.index = Index(db_path)

        reindexed = reindex_missing_notes(self.index)
        if reindexed:
            print(f"Startup cleanup: indexed {reindexed} previously unindexed note(s) for ranked search.")

        self.memory = SessionMemory(db_path)
        self.settings = (
            ResearchSettings() if settings_path is None else ResearchSettings(path=Path(settings_path))
        )
        self._stdout_lock = threading.Lock()
        self.last_diagnostics: List[str] = []

    def counts(self) -> Tuple[int, int, int]:
        total = self.index.source_count()
        files = self.index.source_count("file")
        web = self.index.source_count("web")
        return total, files, web

    def ask(self, text: str, limit: int = 8) -> str:
        """Answer a question."""
        buffer = io.StringIO()
        with self._stdout_lock:
            with contextlib.redirect_stdout(buffer):
                answer = build_conversation_answer(
                    text, self.index, self.memory, limit=limit,
                    settings=self.settings,
                )
        self.last_diagnostics = self._extract_diagnostics(buffer.getvalue())
        return answer

    @staticmethod
    def _extract_diagnostics(captured_output: str) -> List[str]:
        highlights: List[str] = []
        seen = set()
        for line in captured_output.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if not any(marker in cleaned for marker in _DIAGNOSTIC_MARKERS):
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            highlights.append(cleaned)
            if len(highlights) >= _MAX_DIAGNOSTIC_LINES:
                break
        return highlights

    def import_paths(self, paths: List[str]) -> str:
        count = ingest_paths(paths, self.index)
        total, _files, _web = self.counts()
        return f"Ingested {count} file(s) this run. Indexed sources total: {total}"


    def list_sources(self):
        return self.index.list_sources()

    def remove_source(self, source_id: int) -> bool:
        return self.index.remove_source(source_id)

    def remove_sources(self, source_ids) -> int:
        return self.index.remove_sources(source_ids)

    def get_source_for_note(self, source_id: int):
        return self.index.file_for_note(source_id)

    def add_source_note(self, title: str, observation: str, source_id: int, passage: str) -> str:
        """Save an exact excerpt with its provenance as a durable local note."""
        record = self.get_source_for_note(source_id)
        if record is None:
            raise ValueError("The selected source is no longer indexed.")
        source_title, location, text = record
        passage = passage.strip()
        if not passage or passage not in text:
            raise ValueError("The passage does not match the indexed file. Select it again.")
        body = f"Source: {source_title}\nLocation: {location}\n\nExcerpt:\n{passage}"
        if observation.strip():
            body += f"\n\nYour observations:\n{observation.strip()}"
        return self.add_note(title.strip() or source_title, body)

    def add_note(self, title: str, body: str) -> str:
        return add_note(self.index, title, body)

    def list_notes(self, limit: int = 20) -> str:
        return list_notes(self.index, limit=limit)

    def search_notes(self, query: str, limit: int = 10) -> str:
        return search_notes(self.index, query, limit=limit)

    def toggle_setting(self, key: str) -> Tuple[str, bool]:
        resolved = self.settings.resolve_key(key)
        new_value = self.settings.toggle(resolved)
        return TOGGLE_LABELS.get(resolved, resolved), new_value

    def settings_panel_text(self) -> str:
        return self.settings.render()

    def close(self) -> None:
        self.memory.close()
        self.index.close()


__all__ = ["BrisartService"]
