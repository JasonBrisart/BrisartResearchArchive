r"""
File: brisart_ai/core/conversation.py

Purpose
-------
Build a cited answer from enabled local sources.

The conversation layer chooses eligible source types and builds an answer from the
existing index. It deliberately does not perform file ingestion, persistence schema
changes, or live web research.

Public operations: build_conversation_answer (query, index, memory, limit=8,
settings=None) - Build a source-grounded answer to one question.

Communication / relationships
-----------------------------
Calls the Brisart ranker and excerpt renderer and records compact context through
SessionMemory.

A question is normalized, session context is consulted, ranked local documents are
gathered and excerpts are synthesized. Only then is the exchange recorded. This order
matters because no-evidence responses must not silently widen source scope.

Direct project imports: brisart_ai.core.settings, brisart_ai.io.input_cleaner,
brisart_ai.knowledge.ranker, brisart_ai.knowledge.synthesizer.

Direct importing modules include brisart_ai/core/service.py,
brisart_ai/core/tests/test_conversation.py.

Concrete calls within this file include settings.get.

Settings / parameters
---------------------
The source toggles independently enable file and note evidence.

Call signatures: build_conversation_answer(query, index, memory, limit=8,
settings=None).

Edge cases
----------
When both are off, lookup is skipped; historical web rows are never eligible.

Disabling both source types bypasses retrieval entirely. Historical web records may
still exist in a migrated database but are not candidates for answers.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
This is extractive ranking, not semantic inference or internet research.

Examples
--------
build_conversation_answer(question, index, memory, settings=settings)
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
