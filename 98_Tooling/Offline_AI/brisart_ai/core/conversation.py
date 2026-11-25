r"""
File: brisart_ai/core/conversation.py

Purpose
-------
Answer questions exclusively from enabled indexed files and notes.

Communication / relationships
-----------------------------
Called by BrisartService.ask; uses the local ranker, synthesizer and session memory.

Settings / parameters
---------------------

Edge cases
----------
With both toggles off, return no evidence rather than searching all source types.

Known limitations
-----------------
Previously indexed web rows are intentionally excluded.

Examples
--------
Call build_conversation_answer(query, index, memory, settings=settings).
"""

from __future__ import annotations

from typing import Optional

from brisart_ai.core.settings import ResearchSettings
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.ranker import search
from brisart_ai.knowledge.synthesizer import synthesize


def build_conversation_answer(
    query: str, index, memory, limit: int = 8,
    settings: Optional[ResearchSettings] = None,
) -> str:
    """Build a source-grounded answer to one question."""
    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)

    allowed_source_types = set()
    if settings is None or settings.get("search_local_files"):
        allowed_source_types.add("file")
    if settings is not None and settings.get("search_notes"):
        allowed_source_types.add("note")

    def _gather_docs():
        return search(index, cleaned, limit=limit, source_types=allowed_source_types)

    docs = _gather_docs() if allowed_source_types else []

    if docs:
        answer = synthesize(cleaned, docs, recent_topics=recent)
    else:
        answer = (
            "I don't have indexed local information that answers that yet. "
            "Try importing relevant files or adding research notes."
        )

    memory.add("user", cleaned)
    memory.add("assistant", answer)

    return answer


__all__ = ["build_conversation_answer"]
