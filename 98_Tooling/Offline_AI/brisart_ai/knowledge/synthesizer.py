"""
File: brisart_ai/knowledge/synthesizer.py

Purpose
-------
Render engine-selected excerpts, confidence labels, and citations.

This retrieval and indexing component defines `format_source`, `synthesize`. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Passes the query plan to relevance_engine.py; does not classify or score passages.

The direct in-project imports visible in this module are `brisart_ai.knowledge.ranker`,
`brisart_ai.knowledge.relevance_engine`. Public entry points `format_source`, `synthesize`;
this identifies where behavior is invoked without implying a separate hidden dependency.
Higher-level coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
The caller supplies ranked documents and source and excerpt limits.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Renders missing comparison sides, partial coverage, relationship inferences
and disagreements without deciding which source is correct. Date conflicts
can come from deadlines or dependency lifecycle claims. Invalid qualifier
messages are distinct from unsupported evidence. Dependency-list notices
distinguish cited disagreements from disputes omitted by the citation budget.
A known disagreement remains visible even when no complete proof fits.

The behaviors documented above must be read together with the actual branches in
synthesizer.py; a caller must not infer success from an empty, rejected, or unsupported
result. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Extractive rendering cannot establish source accuracy.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
synthesize(plan, documents)

For a concrete entry point, inspect `format_source`, `synthesize`; invoke it through the
existing application entry point or its documented caller. The example above is illustrative
of this file's present interface; do not treat it as an instruction to create additional state
or call private functions directly.
"""

from __future__ import annotations

import collections
import re
from typing import Dict, List

from brisart_ai.knowledge.ranker import QueryPlan, prepare_query
from brisart_ai.knowledge.relevance_engine import evidence_confidence, select_evidence

Document = Dict[str, object]


def _clean_sentence(sentence: str) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    text = text.lstrip(".,;:|- ").strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def format_source(document: Document) -> str:
    source_type = str(document.get("source_type", "source"))
    location = str(document.get("location", ""))
    title = str(document.get("title") or location or "Untitled source")
    return f"{source_type}: {title} :: {location}"


def synthesize(
    query: str | QueryPlan, docs: List[Document], max_sources: int = 6, max_sentences: int = 10,
) -> str:
    """Return the most relevant information from ranked documents."""
    if not docs:
        return "Evidence confidence: Insufficient. I don't have any indexed information that answers that yet."

    safe_source_limit = max(1, int(max_sources))
    safe_sentence_limit = max(1, int(max_sentences))
    fixes = docs[0].get("query_corrections", {})
    plan = prepare_query(query)
    chosen, status, missing = select_evidence(
        plan, docs, max_sources=safe_source_limit, max_sentences=safe_sentence_limit,
    )
    if status == "date_conflict_limit":
        return "Evidence confidence: Conflicting. Found differing dates, but both cannot be shown within the citation limit."
    if status == "insufficient" and plan.mode == "deadline":
        return "Evidence confidence: Insufficient. I found related sources, but not enough evidence for the requested date or event."
    if status == "insufficient":
        return "Evidence confidence: Insufficient. I found related sources, but not enough evidence to answer that directly."
    if status == "relationship_invalid_scope":
        return "Use an ISO date (YYYY-MM-DD) or a month-name date with a year, and an exact numeric release if needed. For start or end questions, omit the as-of date."
    if status == "relationship_conflict_limit":
        return ("Evidence confidence: Conflicting. The relationship evidence cannot be shown completely "
                "within the current source or excerpt limit.")
    if status == "relationship_limit":
        return "The relationship evidence cannot be shown completely within the current source or excerpt limit."
    if status == "comparison_limit":
        return "Not enough room to show evidence for both sides of the comparison."
    if status == "no_passage":
        return "Evidence confidence: Insufficient. I found related sources, but none of them contained a passage that directly answers that."

    by_source: Dict[int, List[str]] = collections.defaultdict(list)
    original_docs: Dict[int, Document] = {}
    order: List[int] = []
    for _, source_number, _, sentence, document in chosen:
        if source_number not in by_source:
            order.append(source_number)
        by_source[source_number].append(_clean_sentence(sentence))
        original_docs[source_number] = document

    display_number: Dict[int, int] = {}
    for new_index, original_number in enumerate(order, start=1):
        display_number[original_number] = new_index

    lines: List[str] = []
    if fixes:
        lines.extend(["Search also matched: " + ", ".join(f"{term} -> {word}" for term, word in fixes.items()), ""])
    lines.extend([f"Evidence confidence: {evidence_confidence(plan, chosen, status)}.", ""])
    if status == "date_conflict":
        lines.extend(["Sources give different dates for the same event. Neither date is selected as authoritative.", ""])
    relationship_messages = {
        "relationship_date_scopes": "The cited dates have different year scopes. No single date is selected:",
        "relationship_alias_conflict": "Sources disagree about what this alias refers to. I did not merge those entities.",
        "relationship_conflict": "Sources disagree about this dependency. The evidence below shows both claims.",
        "relationship_indirect_dispute": "A source denies the dependency, but other sources support an inferred chain. This is not an established direct link.",
        "relationship_inferred": "Inferred dependency chain from the cited links. This is not a direct dependency statement.",
        "relationship_list_disputed": "Sources disagree about some dependencies. The excerpts show both sides of each cited dispute and any other dependencies that fit (not an exhaustive list):",
        "relationship_list_omitted_disputes": "Some disputed dependencies could not be shown in full within the citation limit and were left out. The excerpts show the evidence that fits (not an exhaustive list):",
        "relationship_list": "Direct dependencies found in the cited sources (not an exhaustive list):",
    }
    if status in relationship_messages:
        lines.extend([relationship_messages[status], ""])
    if status == "missing_comparison_side":
        labels = ", ".join(term.upper() for term in missing)
        lines.extend([f"Not enough evidence for a comparison. Missing support for: {labels}.", ""])
    elif status == "separate_comparison_sources":
        lines.extend(["The sources describe each separately:", ""])
    elif status == "partial":
        lines.extend(["Closest excerpts I found. They may not answer the whole question.", ""])
    for original_number in order:
        paragraph = " ".join(by_source[original_number])
        lines.append(f"[{display_number[original_number]}] {paragraph}")
        lines.append("")

    lines.append("Sources:")
    for original_number in order:
        lines.append(f"[{display_number[original_number]}] {format_source(original_docs[original_number])}")

    return "\n".join(lines).rstrip()


__all__ = ["format_source", "synthesize"]
