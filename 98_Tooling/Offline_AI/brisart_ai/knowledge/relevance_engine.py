"""
File: brisart_ai/knowledge/relevance_engine.py

Purpose
-------
Rank passages, select excerpts, and grade evidence for the Brisart retrieval engine.

This retrieval and indexing component defines `rarity_weight`, `presence_points`,
`term_contribution`, `shape_multiplier`, `proximity_bonus`. Its scope is deliberately limited
to the responsibilities visible in this file rather than duplicating the application-wide
workflow. Callers use these declarations through the module interface; the file is not a
separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Receives ranked documents and the shared query plan; intent.py defines evidence cues.
The ranker and answer selection share direct evidence grading.

The direct in-project imports visible in this module are `brisart_ai.util`,
`brisart_ai.intent`. Public entry points `rarity_weight`, `presence_points`,
`term_contribution`, `shape_multiplier`, `proximity_bonus`; this identifies where behavior is
invoked without implying a separate hidden dependency. Higher-level coordination remains with
the calling layer rather than being introduced here.

Settings / parameters
---------------------
Source and excerpt limits are supplied by the answer caller. Short document profiles are cached.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Nearby dates can help rank related documents without becoming citations.
Date ranking grades direct and contextual evidence in one paragraph pass.
Separate comparison sources are preferred to unsupported co-mentions.
Dependency answers combine scoped claims, cite explicit aliases, and label
three-hop inferences or disagreements. Dependency lists include complete
disputes alongside supported links when they fit the citation budget. Among collected proofs, prefer
fewer hops, then fewer sources and excerpts that fit the citation budget. Exact release and date scopes gate
every link. Duplicate claims do not vote.

The behaviors documented above must be read together with the actual branches in
relevance_engine.py; a caller must not infer success from an empty, rejected, or unsupported
result. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Quality and confidence are heuristic support labels, not probabilities.
Date contradictions require matching claim identity and year scope. Dependency
start and end claims are grouped by ordered endpoints and scoped release.
Known relationship disagreements remain conflicting even when citations cannot fit. The intent
module normalizes recognized paraphrases; unmatched wording compares literally.
Date comparison normalizes supported formats without changing cited wording.
Conflicts are reported, not resolved. Alias chains are not inferred. Bounded
candidate and presentation budgets can omit evidence. Unqualified claims are
not evidence for a requested release or date, and vice versa.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
select_evidence(plan, documents, max_sources=6, max_sentences=10)

For a concrete entry point, inspect `rarity_weight`, `presence_points`, `term_contribution`,
`shape_multiplier`, `proximity_bonus`; invoke it through the existing application entry point
or its documented caller. The example above is illustrative of this file's present interface;
do not treat it as an instruction to create additional state or call private functions
directly.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from functools import lru_cache

from brisart_ai.util import title_tokens, tokenize
from brisart_ai.intent import (
    INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_STATISTIC,
    alias_statement, date_mentions, deadline_answers, deadline_claim_key, dependency_date_statement, dependency_statement, passage_evidence, relationship_context,
)
from typing import Dict, List, Sequence, Set, Tuple

RARITY_TIERS: Tuple[Tuple[float, float], ...] = (
    (0.20, 0.4), (0.05, 1.0), (0.01, 1.8), (0.00, 2.6),
)


def rarity_weight(document_frequency: int, total_documents: int) -> float:
    """Fixed-tier weight for a term's corpus rarity. Not a log curve."""
    if document_frequency <= 0 or total_documents <= 0:
        return 0.0
    share = document_frequency / total_documents
    for threshold, weight in RARITY_TIERS:
        if share >= threshold:
            return weight
    return RARITY_TIERS[-1][1]


PRESENCE_SCHEDULE: Tuple[Tuple[int, float], ...] = (
    (8, 1.6), (4, 1.5), (2, 1.3), (1, 1.0),
)


def presence_points(term_frequency: int) -> float:
    """Fixed-schedule credit for how many times a term occurs in one document."""
    if term_frequency <= 0:
        return 0.0
    for threshold, points in PRESENCE_SCHEDULE:
        if term_frequency >= threshold:
            return points
    return PRESENCE_SCHEDULE[-1][1]


def term_contribution(term_frequency: int, document_frequency: int, total_documents: int) -> float:
    """One term's total contribution to a document's base score."""
    return presence_points(term_frequency) * rarity_weight(document_frequency, total_documents)


SHAPE_BRACKETS: Tuple[Tuple[float, float], ...] = (
    (2.50, 0.55), (1.50, 0.75), (0.75, 1.00), (0.00, 1.15),
)


def shape_multiplier(document_length: float, average_length: float) -> float:
    """Fixed-bracket multiplier for a document's length relative to the corpus."""
    if average_length <= 0:
        return 1.0
    ratio = document_length / average_length
    for threshold, multiplier in SHAPE_BRACKETS:
        if ratio >= threshold:
            return multiplier
    return SHAPE_BRACKETS[-1][1]


PROXIMITY_WINDOW_CHARS = 120
PROXIMITY_BONUS_PER_PAIR = 0.15
PROXIMITY_BONUS_CAP = 0.6
SIGNAL_PROXIMITY = "<proximity>"

_WORD_BOUNDARY_RE = re.compile(r"[A-Za-z0-9]+")


def _term_positions(haystack: str, terms: Set[str]) -> Dict[str, List[int]]:
    positions: Dict[str, List[int]] = {}
    for match in _WORD_BOUNDARY_RE.finditer(haystack):
        word = match.group(0).casefold()
        if word in terms:
            positions.setdefault(word, []).append(match.start())
    return positions


def proximity_bonus(haystack: str, matched_terms: Sequence[str]) -> Tuple[float, List[str]]:
    """Bonus multiplier for matched query terms appearing physically close together."""
    distinct_terms = sorted(set(t.casefold() for t in matched_terms if t))
    if len(distinct_terms) < 2:
        return (1.0, [])

    positions = _term_positions(haystack, set(distinct_terms))
    qualifying_pairs = 0
    for i in range(len(distinct_terms)):
        for j in range(i + 1, len(distinct_terms)):
            left_positions = positions.get(distinct_terms[i])
            right_positions = positions.get(distinct_terms[j])
            if not left_positions or not right_positions:
                continue
            if _closest_distance(left_positions, right_positions) <= PROXIMITY_WINDOW_CHARS:
                qualifying_pairs += 1

    if qualifying_pairs == 0:
        return (1.0, [])
    bonus = min(PROXIMITY_BONUS_CAP, qualifying_pairs * PROXIMITY_BONUS_PER_PAIR)
    return (1.0 + bonus, [f"{SIGNAL_PROXIMITY}:{qualifying_pairs}"])


def _closest_distance(left_positions: Sequence[int], right_positions: Sequence[int]) -> int:
    i = j = 0
    best = abs(left_positions[0] - right_positions[0]) if left_positions and right_positions else PROXIMITY_WINDOW_CHARS + 1
    while i < len(left_positions) and j < len(right_positions):
        left, right = left_positions[i], right_positions[j]
        best = min(best, abs(left - right))
        if left < right:
            i += 1
        elif left > right:
            j += 1
        else:
            return 0
    return best


def passages(text: str):
    """Yield source lines or sentences; window overlong unpunctuated text."""
    lines = iter(text.splitlines())
    pending = None
    while True:
        line = next(lines, None)
        if line is None:
            if pending:
                yield pending
            break
        line = line.strip()
        if pending:
            if line and len(line) <= 100 and re.match(r"(?:[$€£]?\d|yes\b|no\b)", line, re.I):
                yield pending + "\n" + line
                pending = None
                continue
            yield pending
            pending = None
        if 2 <= len(line) <= 85 and line.endswith(":"):
            pending = line
            continue
        yield from _sentence_windows(line)


def _sentence_windows(line: str):
    for part in re.split(r"(?<=[.!?])\s+", line):
        if not part:
            continue
        if len(part) <= 700:
            yield part
            continue
        for start in range(0, len(part), 550):
            if start and start + 150 >= len(part):
                break
            end = min(len(part), start + 700)
            yield ("... " if start else "") + part[start:end].strip() + (" ..." if end < len(part) else "")


def _passage_profiles(text: str):
    for passage in passages(text):
        words = title_tokens(passage)
        yield passage, frozenset(words) | frozenset(tokenize(passage)), len(words)


@lru_cache(maxsize=48)
def _small_document_profiles(text: str):
    return tuple(_passage_profiles(text))


def scored_passages(text: str, groups):
    """Match a query to passages; reuse tokenization of recently read short files."""
    masks = {}
    for number, forms in enumerate(groups):
        for form in forms:
            masks[form] = masks.get(form, 0) | (1 << number)
    profiles = (_small_document_profiles(text) if len(text) <= 32768
                else _passage_profiles(text))
    for passage, tokens, length in profiles:
        mask = 0
        for token, value in masks.items():
            if token in tokens:
                mask |= value
        yield passage, mask.bit_count(), length


Document = Dict[str, object]
Candidate = Tuple[float, int, int, str, Document]


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


def _deduplication_key(sentence: str) -> str:
    return " ".join(re.findall(r"\w+", sentence.casefold()))


def sentence_score(
    sentence: str, query_terms: Set[str], quantity_mode: bool = False,
    comparison_mode: bool = False, reason_mode: bool = False,
) -> float:
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = Counter(words)
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


# These gates favor explicit evidence, not a document's topic or filename.
_CONTINUATION = re.compile(r"^(?:the\s+(?:resulting|integrated|updated)\b|"
                           r"(?:this|that|it|then|next|as a result)\b)", re.I)


_TENTATIVE = re.compile(
    r"\b(?:may|might|could|tentative(?:ly)?|proposed|estimated|unconfirmed|subject to change)\b",
    re.I,
)


def _tentative(text):
    # Do not mistake the month May for a modal verb.
    return bool(_TENTATIVE.search(re.sub(r"\b(?:May\s+[0-9]{1,2}|[0-9]{1,2}\s+May)\b", "", text, flags=re.I)))


def result_evidence_quality(plan, key, passage):
    """Ordinal passage quality, independent of title and document rank."""
    grade, hits, _ = key
    if not hits and not grade:
        return 0
    if _tentative(passage):
        return 1
    if plan.mode:
        if plan.mode == "deadline" or plan.endpoints or plan.mode == "comparison":
            return 3 if grade == 2 else 1
        return 3 if grade else 1
    return 2 if hits == len(plan.groups) else 1


_CONFLICT_STATUSES = frozenset({
    "date_conflict", "date_conflict_limit", "relationship_conflict", "relationship_conflict_limit",
    "relationship_alias_conflict", "relationship_indirect_dispute", "relationship_list_disputed",
    "relationship_list_omitted_disputes",
})


def evidence_confidence(plan, chosen, status):
    """Describe support for this answer, never the truth of its sources."""
    if status in _CONFLICT_STATUSES:
        return "Conflicting"
    if not chosen:
        return "Insufficient"
    if status == "relationship_inferred":
        return "Inferred"
    if any(_tentative(item[3]) for item in chosen):
        return "Tentative"
    if status == "supported" and plan.mode:
        return "Direct support"
    return "Limited support"


def _relationship_body(plan, passage):
    """Return statement text only when all explicit qualifiers match."""
    text, context = relationship_context(passage)
    if context is None or plan.relationship_scope is None:
        return None
    start, end, version = context
    day, _, release = plan.relationship_scope
    if version != release or bool(start) != bool(day) or (day and not start <= day <= end):
        return None
    return text


def _direct_grade(plan, text, hits, total, words):
    if plan.endpoints:
        body = _relationship_body(plan, text)
        if plan.relationship_event:
            dated = dependency_date_statement(body) if body and not _tentative(body) else None
            return 2 if dated and dated[:2] == plan.endpoints and dated[2] == plan.relationship_event else 0
        claim = dependency_statement(body) if body else None
        if claim:
            left, right, negative = claim
            subject, target = plan.endpoints
            if (not subject or left == subject) and (not target or right == target):
                return 2 if not negative or (subject and target) else 0
        return 0
    grade = passage_evidence(plan.mode, text, hits, total, words)
    if grade and plan.mode == "deadline":
        return 2 if deadline_answers(plan.text, text) else 0
    return grade


def _paragraphs(text):
    return re.split(r"\r?\n[ \t]*\r?\n", text)


def best_ranked_passage(plan, text, groups):
    """Return the best passage and key; related dates do not certify an answer."""
    best_key, best_passage = (0, 0, 0.0), ""
    total = len(groups)
    mode = plan.mode
    sections = _paragraphs(text) if mode == "deadline" else (text,)
    for paragraph in sections:
        previous_hits = 0
        for passage, hits, words in scored_passages(paragraph, groups.values()):
            grade = _direct_grade(plan, passage, hits, total, words)
            if mode == "deadline" and grade and _tentative(passage):
                grade = 1
            elif mode == "deadline" and not grade:
                # Context is useful for ranking, never sufficient for a citation.
                grade = passage_evidence(mode, passage, max(hits, previous_hits), total, words)
            key = (grade, hits, hits / max(8, words))
            if key > best_key:
                best_key, best_passage = key, passage
            previous_hits = hits
    return best_key, best_passage


def _grounded_candidates(documents, groups, plan, max_sources, max_sentences):
    """Select explicit evidence for the requested answer type."""
    mode = plan.mode
    comparison = mode == "comparison"
    roles = [None for _ in groups]
    joint = None
    mechanism = None
    dates = []
    for number, document in enumerate(documents, 1):
        text = str(document.get("text", ""))
        for paragraph in _paragraphs(text):
            prev = None
            for excerpt in passages(paragraph):
                words = set(tokenize(excerpt))
                matched = tuple(i for i, forms in enumerate(groups.values()) if words & forms)
                candidate = (0.0, number, len(matched), excerpt, document)
                if prev and not matched and _CONTINUATION.search(excerpt) and passage_evidence("mechanism", excerpt, 1, 1, len(words)):
                    mechanism = (*prev[:3], prev[3] + " " + excerpt, document)
                prev = None
                grade = _direct_grade(plan, excerpt, len(matched), len(groups), len(words))
                if not grade:
                    continue
                if mode == "deadline":
                    dates.append(candidate)
                elif comparison:
                    if grade == 2:
                        if joint is None:
                            joint = candidate
                    else:
                        if roles[matched[0]] is None:
                            roles[matched[0]] = candidate
                elif mechanism is None:
                    mechanism = candidate
                    prev = candidate if mode == "mechanism" else None
    if mode == "deadline":
        if not dates:
            return [], [], "insufficient"
        firm = [candidate for candidate in dates if not _tentative(candidate[3])]
        preferred = (firm or dates)[0]
        # Group only like statements in the same year scope. Preserve the
        # original passages for citations and never infer a missing year.
        claims = {}
        for candidate in firm:
            passage = candidate[3]
            dates_found = list(date_mentions(passage))
            if len(dates_found) != 1 or dates_found[0][1] is None:
                continue
            span, value = dates_found[0]
            signature = (value[0], deadline_claim_key(passage, span))
            existing_value, existing = claims.setdefault(signature, (value, candidate))
            if value != existing_value:
                if max_sentences < 2 or (max_sources < 2 and existing[1] != candidate[1]):
                    return [], [], "date_conflict_limit"
                return [existing, candidate], [], "date_conflict"
        return [preferred], [], "supported"
    if not comparison:
        return [mechanism] if mechanism else [], [], "supported"
    if joint:
        return [joint], [], "supported"
    missing = [term for term, evidence in zip(groups, roles) if not evidence]
    return [item for item in roles if item], missing, "supported"


def _relationship_evidence(plan, docs, max_sources, max_sentences):
    """Combine explicit claims without letting copies vote or hiding a conflict."""
    if plan.relationship_scope is None:
        return [], "relationship_invalid_scope", []
    aliases, claims, dated_claims = defaultdict(dict), [], []
    for number, doc in enumerate(docs, 1):
        for excerpt in passages(str(doc.get("text", ""))):
            body = _relationship_body(plan, excerpt)
            if not body:
                continue
            record = (0.0, number, 0, excerpt, doc)
            if declaration := alias_statement(body):
                name, alias = declaration
                aliases[alias].setdefault(name, record)
            elif plan.relationship_event:
                dated = dependency_date_statement(body) if not _tentative(body) else None
                if dated and dated[2] == plan.relationship_event:
                    dated_claims.append((dated, record))
            elif claim := dependency_statement(body):
                claims.append((claim, record))

    def resolve(name):
        options = aliases.get(name, {})
        if len(options) == 1:
            canonical, citation = next(iter(options.items()))
            if canonical not in aliases:  # no ungrounded or cyclic alias merges
                return canonical, (citation,)
        return name, ()

    endpoints = tuple(resolve(name) for name in plan.endpoints)
    subject, target = (item[0] for item in endpoints)
    query_citations = tuple(record for _, citations in endpoints for record in citations)
    edges = defaultdict(dict)
    for (left, right, negative), record in claims:
        left_name, left_cites = resolve(left)
        right_name, right_cites = resolve(right)
        if left_name == right_name:
            continue
        proof = (record, *left_cites, *right_cites)
        by_polarity = edges[left_name, right_name]
        if negative not in by_polarity or len(proof) < len(by_polarity[negative]):
            by_polarity[negative] = proof

    def result(proof, status):
        selected = list({(record[1], record[3]): record for record in proof}.values())
        if len(selected) > max_sentences or len({record[1] for record in selected}) > max_sources:
            return [], ("relationship_conflict_limit" if status in _CONFLICT_STATUSES else "relationship_limit"), []
        return selected, status, []

    for name in plan.endpoints:
        declarations = aliases.get(name, {})
        if len(declarations) > 1:
            return result(tuple(declarations.values())[:2], "relationship_alias_conflict")

    if plan.relationship_event:
        # Compare only the same ordered pair, transition, release and year scope.
        by_year = {}
        for (left, right, _, value), record in dated_claims:
            if any(len(aliases.get(name, {})) > 1 for name in (left, right)):
                continue
            left, left_proof = resolve(left)
            right, right_proof = resolve(right)
            if (left, right) != (subject, target):
                continue
            proof = (record, *left_proof, *right_proof, *query_citations)
            previous = by_year.setdefault(value[0], (value, proof))
            if previous[0] != value:
                chosen, status, missing = result((*previous[1], *proof), "date_conflict")
                return (chosen, status, missing) if chosen else ([], "date_conflict_limit", [])
        if len(by_year) > 1:
            return result(tuple(record for _, proof in by_year.values() for record in proof), "relationship_date_scopes")
        if by_year:
            return result(next(iter(by_year.values()))[1], "supported")
        return [], "insufficient", []

    if subject and target:
        direct = edges.get((subject, target), {})
        if False in direct:
            if True in direct:
                return result((*direct[False], *direct[True], *query_citations), "relationship_conflict")
            return result((*direct[False], *query_citations), "supported")
        # Only unambiguous, undisputed links may support an inference.
        outgoing, incoming = defaultdict(list), defaultdict(list)
        ambiguous = {alias for alias, names in aliases.items()
                     if len(names) != 1 or next(iter(names)) in aliases}
        for (left, right), polarities in edges.items():
            if False in polarities and True not in polarities and not ({left, right} & ambiguous):
                outgoing[left].append((right, polarities[False]))
                incoming[right].append(left)
        # Reverse reachability prunes branches that cannot reach the target
        # within the hop budget. A global visited set on forward paths would
        # discard alternative proofs with different citation costs.
        distance = {target: 0}
        layer = [target]
        for depth in range(1, 4):
            layer = [left for right in layer for left in incoming[right] if left not in distance]
            layer = list(dict.fromkeys(layer))
            distance.update(dict.fromkeys(layer, depth))
        if subject in distance:
            trailing = (*direct.get(True, ()), *query_citations)
            status = "relationship_indirect_dispute" if True in direct else "relationship_inferred"
            frontier = [(subject, (subject,), ())]
            for depth in range(1, 4):
                following = []
                best, best_cost = None, None
                for left, path, prefix in frontier:
                    for right, proof in outgoing[left]:
                        if right in path or distance.get(right, 4) > 3 - depth:
                            continue
                        combined = (*prefix, *proof)
                        answer = result((*combined, *trailing), status)
                        if not answer[0]:
                            continue
                        if right == target:
                            cost = (len({record[1] for record in answer[0]}), len(answer[0]))
                            if best_cost is None or cost < best_cost:
                                best, best_cost = answer, cost
                        elif depth < 3:
                            following.append((right, (*path, right), combined))
                if best is not None:
                    return best
                if not following:
                    break
                frontier = following
            return [], ("relationship_conflict_limit" if True in direct else "relationship_limit"), []
        if True in direct:
            return result((*direct[True], *query_citations), "supported")
    else:
        matches = [polarities for (left, right), polarities in edges.items()
                   if (not subject or subject == left) and (not target or target == right)
                   and False in polarities]
        # Treat both polarities of a disputed link as one indivisible proof.
        # Reserve space for complete disputes first, then fill with other links.
        selected = ()
        showed_dispute = omitted_dispute = False
        for polarities in sorted(matches, key=lambda item: True not in item):
            denial = polarities.get(True, ())
            proof = (*selected, *polarities[False], *denial)
            if result((*proof, *query_citations), "supported")[0]:
                selected = proof
                showed_dispute |= bool(denial)
            else:
                omitted_dispute |= bool(denial)
        if selected:
            status = ("relationship_list_omitted_disputes" if omitted_dispute else
                      "relationship_list_disputed" if showed_dispute else "relationship_list")
            return result((*selected, *query_citations), status)
        if matches:
            return [], ("relationship_conflict_limit" if omitted_dispute else "relationship_limit"), []
    return [], "insufficient", []


def select_evidence(plan, docs, *, max_sources, max_sentences):
    """Return selected excerpts, support status, and any missing comparison terms."""
    if plan.endpoints:
        return _relationship_evidence(plan, docs, max_sources, max_sentences)
    groups = plan.groups.copy()
    for term, corrected in docs[0].get("query_corrections", {}).items() if docs else ():
        if term in groups:
            groups[term] = groups[term] | {corrected}
    quantity_mode = plan.intent == INTENT_STATISTIC
    comparison_mode = plan.intent == INTENT_COMPARISON
    reason_mode = plan.intent == INTENT_EXPLANATION
    mode = plan.mode
    missing = []
    status = "supported"
    if mode:
        scope = docs if mode == "deadline" else docs[:max_sources]
        candidates, missing, status = _grounded_candidates(scope, groups, plan, max_sources, max_sentences)
        if status in {"date_conflict_limit", "date_conflict"}:
            return candidates, status, []
        if not candidates:
            return [], "insufficient", missing
        if missing:
            status = "missing_comparison_side"
        elif mode == "comparison" and len(candidates) == 2:
            if max_sentences < 2:
                return [], "comparison_limit", []
            status = "separate_comparison_sources"
    else:
        candidates = []
    for source_number, document in enumerate(docs[:max_sources] if not mode else (), start=1):
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
    source_counts: Dict[int, int] = defaultdict(int)
    if not mode and candidates and len(groups) > 1:
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
        if len(chosen) >= max_sentences:
            break

    if not chosen:
        return [], "no_passage", []
    if not mode and chosen[0][2] < len(groups):
        status = "partial"
    return chosen, status, missing


__all__ = [
    "PRESENCE_SCHEDULE", "PROXIMITY_BONUS_CAP", "PROXIMITY_BONUS_PER_PAIR",
    "PROXIMITY_WINDOW_CHARS", "RARITY_TIERS", "SHAPE_BRACKETS", "SIGNAL_PROXIMITY",
    "presence_points", "proximity_bonus", "rarity_weight", "shape_multiplier",
    "term_contribution",
]
