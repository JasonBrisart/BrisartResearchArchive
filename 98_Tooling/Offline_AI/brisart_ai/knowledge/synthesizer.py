"""
Purpose
-------
Select and cite excerpts from ranked local evidence without generating claims.

Communication / relationships
-----------------------------
Shares query groups with ranker.py and passage matching with relevance_engine.py.

Settings / parameters
---------------------
Source and excerpt limits default to six and ten, with at most three
excerpts per source. Coverage outweighs bounded intent-specific cues.

Edge cases
----------
Repetition cannot inflate concept coverage. Short lines can be evidence.
Recovered spellings and partial matches are labeled and identical normalized excerpts appear once.

Known limitations
-----------------
A match is not proof that a passage answers a question or that a source
is correct. This module does not infer missing facts.

Examples
--------
synthesize("When does the permit expire?", ranked_documents)
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
