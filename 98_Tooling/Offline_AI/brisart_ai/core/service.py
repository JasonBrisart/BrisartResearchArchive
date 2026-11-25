r"""
File: brisart_ai/core/service.py

Purpose
-------
Coordinate local imports, source management, sourced notes and question answering.

Communication / relationships
-----------------------------
Called by CLI and Tk desktop; owns Index, SessionMemory and ResearchSettings.

Settings / parameters
---------------------
Uses per-user index and settings paths unless callers supply overrides.

Edge cases
----------
Sourced notes reject stale or mismatched excerpts and preserve a copy with provenance.

Known limitations
-----------------
A Tk display is needed only for the desktop, not the service.

Examples
--------
Use BrisartService(db_path).ask("question").
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
