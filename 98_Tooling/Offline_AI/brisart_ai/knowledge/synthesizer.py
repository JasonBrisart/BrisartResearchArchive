r"""
File: brisart_ai/knowledge/synthesizer.py

Purpose
-------
Render cited excerpts rather than inventing an answer.

The synthesizer renders selected source excerpts with citations. It is intentionally
extractive: the application should disclose partial evidence rather than manufacture an
answer that was not present in the index.

Public operations: query_wants_quantity (query); query_wants_comparison (query);
query_wants_reason (query); format_source (document).

Public operations: sentence_score (sentence, query_terms, quantity_mode=False,
comparison_mode=False, reason_mode=False); synthesize (query, docs, max_sources=6,
max_sentences=10, recent_topics=None) - Return the most relevant information from ranked
documents.

Internal helpers include _clean_sentence, _deduplication_key.

Communication / relationships
-----------------------------
Uses ranker query groups, supplied spelling corrections and relevance_engine passage
scoring.

It shares query concepts and passage coverage with the ranker, applies intent-related
excerpt cues, limits duplicate passages and caps how many excerpts one source can
contribute.

Direct project imports: brisart_ai.intent, brisart_ai.knowledge.ranker,
brisart_ai.knowledge.relevance_engine, brisart_ai.util.

Direct importing modules include brisart_ai/core/conversation.py,
brisart_ai/knowledge/tests/test_synthesizer.py.

Settings / parameters
---------------------
Limits source and excerpt counts and caps excerpts per source.

Call signatures: query_wants_quantity(query); query_wants_comparison(query);
query_wants_reason(query); format_source(document); sentence_score(sentence,
query_terms, quantity_mode=False, comparison_mode=False, reason_mode=False).

Call signatures: synthesize(query, docs, max_sources=6, max_sentences=10,
recent_topics=None).

Edge cases
----------
Duplicate excerpts are skipped; partial evidence and recovered spellings are labeled.

A cited passage can be relevant without proving the full proposition in the question.
Spelling recovery and partial coverage must be visible instead of silently treated as
certainty.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
Topic coverage does not establish truth or that a source answers every part of the
question.

Examples
--------
synthesize("What is the permit fee?", ranked_documents)

Other callable entry points in this module include query_wants_comparison,
query_wants_reason, format_source, sentence_score, synthesize.
"""

from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Set, Tuple

from brisart_ai.intent import INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_STATISTIC, detect_intent
from brisart_ai.knowledge.ranker import query_groups
from brisart_ai.knowledge.relevance_engine import scored_passages
from brisart_ai.util import tokenize

Document = Dict[str, object]
Candidate = Tuple[float, int, int, str, Document]


def query_wants_quantity(query: str) -> bool:
    return detect_intent(query) == INTENT_STATISTIC


def query_wants_comparison(query: str) -> bool:
    return detect_intent(query) == INTENT_COMPARISON


def query_wants_reason(query: str) -> bool:
    return detect_intent(query) == INTENT_EXPLANATION


_HAS_DIGIT = re.compile(r"\d")
_HAS_QUANTITY = re.compile(
    r"[$\u20ac\u00a3]\s*\d[\d,\.]*"
    r"|\d[\d,\.]*\s*"
    r"(million|billion|trillion|thousand|percent|%|households|"
    r"people|cats|dogs|pets|residents|adults|users|"
    r"estimated|approximately|dollars?|usd|"
    r"kilometers?|km|miles?|mi\b|meters?|metres?|feet|ft\b|"
    r"kilograms?|kg|pounds?|lbs?\b|tons?|tonnes?|"
    r"years?|months?|weeks?|days?|hours?|minutes?|seconds?|"
    r"calories|degrees)",
    re.IGNORECASE,
)
_HAS_COMPARISON_SIGNAL = re.compile(
    r"\b(than|more|less|longer|shorter|faster|slower|"
    r"better|worse|compared\s+to|versus|vs\.?|"
    r"outlive[sd]?|outlast[sd]?|"
    r"bigger|smaller|cheaper|higher|lower|"
    r"most|least|stronger|weaker)\b",
    re.IGNORECASE,
)
_HAS_REASON_SIGNAL = re.compile(
    r"\b(because|due\s+to|caused?\s+by|reason|since|"
    r"as\s+a\s+result|leads?\s+to|results?\s+in|"
    r"allows?|enables?|so\s+that|triggers?|prompts?)\b",
    re.IGNORECASE,
)


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


def _deduplication_key(sentence: str) -> str:
    return " ".join(re.findall(r"\w+", sentence.casefold()))


def sentence_score(
    sentence: str, query_terms: Set[str], quantity_mode: bool = False,
    comparison_mode: bool = False, reason_mode: bool = False,
) -> float:
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = collections.Counter(words)
    overlap = sum(counts[term] for term in query_terms)
    density = overlap / max(1, len(words))
    score = float(overlap + density)

    if overlap > 0:
        if quantity_mode:
            if _HAS_QUANTITY.search(sentence):
                score += 10.0
            elif _HAS_DIGIT.search(sentence):
                score += 3.0
        if comparison_mode and _HAS_COMPARISON_SIGNAL.search(sentence):
            score += 8.0
        if reason_mode and _HAS_REASON_SIGNAL.search(sentence):
            score += 8.0
    return score


def synthesize(
    query: str, docs: List[Document], max_sources: int = 6, max_sentences: int = 10,
    recent_topics: Iterable[str] | None = None,
) -> str:
    """Return the most relevant information from ranked documents."""
    if not docs:
        return "I don't have any indexed information that answers that yet."

    safe_source_limit = max(1, int(max_sources))
    safe_sentence_limit = max(1, int(max_sentences))
    groups = query_groups(query)

    fixes = docs[0].get("query_corrections", {})
    for term, corrected in fixes.items():
        if term in groups:
            groups[term] = groups[term] | {corrected}
    quantity_mode = query_wants_quantity(query)
    comparison_mode = query_wants_comparison(query)
    reason_mode = query_wants_reason(query)

    candidates: List[Candidate] = []
    for source_number, document in enumerate(docs[:safe_source_limit], start=1):
        text = str(document.get("text", ""))
        for sentence, hits, length in scored_passages(text, groups.values()):
            if not hits:
                continue
            coverage = hits / len(groups)
            score = 4.0 * hits + hits / max(8, length)
            if quantity_mode and _HAS_QUANTITY.search(sentence):
                score += 2.0 * coverage
            if comparison_mode and _HAS_COMPARISON_SIGNAL.search(sentence):
                score += 2.0 * coverage
            if reason_mode and _HAS_REASON_SIGNAL.search(sentence):
                score += 2.0 * coverage
            score += 0.45 / source_number
            candidates.append((score, source_number, hits, sentence, document))
    candidates.sort(key=lambda item: item[0], reverse=True)

    chosen: List[Candidate] = []
    seen = set()
    source_counts: Dict[int, int] = collections.defaultdict(int)
    if candidates and len(groups) > 1:
        best_hits = candidates[0][2]
        minimum_hits = min(best_hits, max(2, best_hits - 1))
        candidates = [candidate for candidate in candidates
                      if candidate[2] >= minimum_hits]
    for candidate in candidates:
        _, source_number, _, sentence, _ = candidate
        key = _deduplication_key(sentence)
        if not key or key in seen or source_counts[source_number] >= 3:
            continue
        seen.add(key)
        source_counts[source_number] += 1
        chosen.append(candidate)
        if len(chosen) >= safe_sentence_limit:
            break

    if not chosen:
        return (
            "I found related sources, but none of them contained a "
            "passage that directly answers that."
        )

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

    best_hits = chosen[0][2]
    lines: List[str] = []
    if fixes:
        lines.extend(["Search also matched: " + ", ".join(f"{term} -> {word}" for term, word in fixes.items()), ""])
    if best_hits < len(groups):
        lines.extend(["Closest excerpts I found. They may not answer the whole question.", ""])
    for original_number in order:
        paragraph = " ".join(by_source[original_number])
        lines.append(f"[{display_number[original_number]}] {paragraph}")
        lines.append("")

    lines.append("Sources:")
    for original_number in order:
        lines.append(f"[{display_number[original_number]}] {format_source(original_docs[original_number])}")

    return "\n".join(lines).rstrip()


__all__ = [
    "format_source", "query_wants_comparison", "query_wants_quantity",
    "query_wants_reason", "sentence_score", "synthesize",
]
