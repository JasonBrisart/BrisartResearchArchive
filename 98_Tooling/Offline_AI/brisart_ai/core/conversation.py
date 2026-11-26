"""Purpose
-------
Answer a local question through the Brisart retrieval engine and record the exchange.

This application service and state component defines `build_conversation_answer`. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Settings choose the source scope. The ranker collects scoped documents and the
synthesizer renders the relevance engine's selected evidence.

The direct in-project imports visible in this module are `brisart_ai.core.settings`,
`brisart_ai.io.input_cleaner`, `brisart_ai.knowledge.ranker`,
`brisart_ai.knowledge.synthesizer`. Public entry points `build_conversation_answer`; this
identifies where behavior is invoked without implying a separate hidden dependency.
Higher-level coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
The caller sets the result limit; at most six sources are displayed. Date
queries consider at least eight ranked results for disagreement checks.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Disabled source types are not searched. Relationship candidates may exceed the
citation limit so conflicting claims are not silently dropped.

The behaviors documented above must be read together with the actual branches in
conversation.py; a caller must not infer success from an empty, rejected, or unsupported
result. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
The answer is extractive. Stored conversation topics do not affect retrieval.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
build_conversation_answer("Does Atlas Index rely on Cedar Store?", index, memory)

For a concrete entry point, inspect `build_conversation_answer`; invoke it through the
existing application entry point or its documented caller. The example above is illustrative
of this file's present interface; do not treat it as an instruction to create additional state
or call private functions directly.
"""

from __future__ import annotations

from typing import Optional

from brisart_ai.core.settings import ResearchSettings
from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.knowledge.ranker import prepare_query, relationship_documents, search
from brisart_ai.knowledge.synthesizer import synthesize


def build_conversation_answer(
    query: str, index, memory, limit: int = 8,
    settings: Optional[ResearchSettings] = None,
) -> str:
    """Build a source-grounded answer to one question."""
    cleaned = normalize_shellish_input(query)

    allowed_source_types = set()
    if settings is None or settings.get("search_local_files"):
        allowed_source_types.add("file")
    if settings is not None and settings.get("search_notes"):
        allowed_source_types.add("note")

    plan = prepare_query(cleaned) if allowed_source_types else None
    docs = []
    if plan is not None and limit > 0:
        if plan.endpoints:
            docs = relationship_documents(index, plan, allowed_source_types)
        else:
            # Date answers need room to notice a conflicting source even when
            # the display budget allows only one citation.
            search_limit = max(limit, 8) if plan.mode == "deadline" else limit
            docs = search(index, plan, limit=search_limit, source_types=allowed_source_types)

    if plan is not None and docs:
        answer = synthesize(plan, docs, max_sources=min(6, limit))
    else:
        answer = (
            "Evidence confidence: Insufficient. I don't have indexed local information that answers that yet. "
            "Try importing relevant files or adding research notes."
        )

    memory.add("user", cleaned)
    memory.add("assistant", answer)

    return answer


__all__ = ["build_conversation_answer"]
