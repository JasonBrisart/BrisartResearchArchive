"""
Purpose
-------
Rank local sources by passage coverage, then by document-level evidence.

Communication / relationships
-----------------------------
Reads Brisart token postings from ordinary SQLite tables in batches.
Also supplies unranked matching IDs to vault collection and timeline queries. Shares query concepts with
synthesizer.py and passage matching with relevance_engine.py.

Settings / parameters
---------------------
The shortlist contains up to five times the requested limit plus ten
candidates. Each extra matched concept in one passage outranks metadata.
One document-length snapshot is cached per open index and invalidated on writes.

Edge cases
----------
Known English word families and regular plural variants share one concept.
An explicit empty source scope returns no results; ties use source ID.
Exact Python declarations can outrank mentions. Unmatched alphabetic
query terms may recover a unique one-edit neighbor in the eligible vocabulary.

Known limitations
-----------------
The initial shortlist still requires an indexed term hit; this is not
semantic retrieval. Typo recovery requires a shared two-letter prefix
and skips ambiguous or oversized candidate vocabularies.

Examples
--------
search(index, "When does the permit expire?", source_types={"file"})
"""

from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from brisart_ai.intent import (
    INTENT_GENERAL, detect_intent, is_bare_generic_concept_title,
    name_candidates, score_intent,
)
from brisart_ai.knowledge import relevance_engine
from brisart_ai.util import query_frame_terms, term_variants, title_tokens, tokenize

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "many", "me", "more", "most", "much", "my", "myself", "no",
    "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same",
    "she", "should", "so", "some", "such", "than", "that", "the",
    "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
}

GENERIC_QUERY_VERBS: Set[str] = {
    "explain", "explains", "explained", "explanation", "describe", "describes",
    "described", "description", "define", "defines", "defined", "definition",
    "meaning", "meanings", "tell", "tells", "give", "gives", "summarize",
    "summarizes", "summarise", "summarises", "outline", "outlines", "elaborate",
    "elaborates", "clarify", "clarifies", "understand", "understands", "know",
    "knows", "find", "finds", "show", "shows", "list", "lists", "compare", "versus", "vs",
}

COVERAGE_FLOOR = 0.15
INTENT_WEIGHT = 0.30
INTENT_MIN_FACTOR = 0.40
INTENT_MAX_FACTOR = 1.90
INTENT_TEXT_CHARS = 2000
INTENT_CANDIDATE_FACTOR = 5
INTENT_CANDIDATE_MIN = 10
TITLE_MATCH_WEIGHT = 0.12
TITLE_MATCH_MAX_FACTOR = 1.42
GENERIC_TERM_DAMPING = 0.2
SIGNAL_TITLE_MATCH = "<title-match>"
GENERIC_CONCEPT_TITLE_PENALTY_FACTOR = 0.35
SIGNAL_GENERIC_CONCEPT_TITLE = "<generic-concept-title>"
PHRASE_MATCH_FACTOR = 1.35
PHRASE_MATCH_MIN_WORDS = 2
SIGNAL_PHRASE_MATCH = "<phrase-match>"

_PHRASE_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _normalize_for_phrase(text: str) -> str:
    return _PHRASE_NORMALIZE_RE.sub(" ", str(text or "").casefold()).strip()


# Related English forms that can safely share one query concept. These are
# deliberately narrow: e.g. "found" alone is not treated as "founded".
_WORD_FAMILIES = tuple(frozenset(family.split()) for family in (
    "founded founder founders founding established",
    "expire expires expired expiration expiry",
    "renew renews renewed renewal renewals renewing",
    "approve approves approved approval approvals",
    "cancel cancels canceled cancelled cancellation cancellations",
    "invent invented inventor inventors invention inventions",
))


def query_groups(query: str):
    """Return ordered topic terms and their accepted spellings."""
    frame = query_frame_terms(query)
    terms = [term for term in tokenize(query) if term not in STOPWORDS and term not in frame]
    focused = [term for term in terms if term not in GENERIC_QUERY_VERBS]
    groups = {}
    covered = set()
    for term in (focused or terms):
        if term in covered:
            continue
        forms = next((family for family in _WORD_FAMILIES if term in family), None)
        if forms is None:
            forms = term_variants(term)
        groups[term] = forms
        covered.update(forms)
    return groups


def title_match_adjust(
    title: str, meaningful_terms: Set[str], term_rarity: Optional[Dict[str, float]] = None,
) -> Tuple[float, List[str]]:
    """Boost a score for meaningful query terms present in the title."""
    if not title or not meaningful_terms:
        return (1.0, [])
    title_terms = {
        term for term in meaningful_terms
        if term_variants(term) & set(title_tokens(title))
    }
    if not title_terms:
        return (1.0, [])

    average_rarity = (sum(term_rarity.values()) / len(term_rarity)) if term_rarity else 1.0
    if average_rarity <= 0:
        average_rarity = 1.0

    weighted_total = 0.0
    matched_terms: List[str] = []
    for term in sorted(title_terms):
        relative_weight = 1.0
        if term_rarity:
            relative_weight = term_rarity.get(term, average_rarity) / average_rarity
        if term in GENERIC_QUERY_VERBS:
            relative_weight *= GENERIC_TERM_DAMPING
        weighted_total += relative_weight
        matched_terms.append(term)

    factor = min(TITLE_MATCH_MAX_FACTOR, 1.0 + (TITLE_MATCH_WEIGHT * weighted_total))
    return (factor, [f"{SIGNAL_TITLE_MATCH}:{','.join(matched_terms)}"])


def generic_concept_title_adjust(title: str, location: str) -> Tuple[float, List[str]]:
    """Penalize a document whose title/URL is a bare generic concept."""
    candidates = [title] + name_candidates(location or "")
    for candidate in candidates:
        if is_bare_generic_concept_title(candidate):
            return (GENERIC_CONCEPT_TITLE_PENALTY_FACTOR, [SIGNAL_GENERIC_CONCEPT_TITLE])
    return (1.0, [])


def phrase_match_adjust(query: str, haystack: str) -> Tuple[float, List[str]]:
    """Boost a score when the literal query phrase appears verbatim."""
    normalized_query = _normalize_for_phrase(query)
    if len(normalized_query.split()) < PHRASE_MATCH_MIN_WORDS:
        return (1.0, [])
    normalized_haystack = _normalize_for_phrase(haystack)
    if normalized_query and f" {normalized_query} " in f" {normalized_haystack} ":
        return (PHRASE_MATCH_FACTOR, [SIGNAL_PHRASE_MATCH])
    return (1.0, [])


def proximity_adjust(matched_terms: Sequence[str], haystack: str) -> Tuple[float, List[str]]:
    """Boost a score when matched query terms sit close together."""
    return relevance_engine.proximity_bonus(haystack, matched_terms)


def intent_adjust(
    base_score: float, title: str, text: str, location: str, intent: str, query: str,
    topic_terms: Optional[Set[str]] = None, term_rarity: Optional[Dict[str, float]] = None,
    matched_terms: Optional[Set[str]] = None,
) -> Tuple[float, List[str], List[str]]:
    """Apply title-match, generic-concept, phrase-match, proximity, and intent adjustments."""
    haystack = " ".join(
        part for part in (str(title or ""), str(location or ""), str(text or "")[:INTENT_TEXT_CHARS]) if part
    )

    score = base_score
    boosts: List[str] = []
    penalties: List[str] = []

    title_factor, title_boosts = title_match_adjust(title, topic_terms or set(), term_rarity)
    if title_factor != 1.0:
        score *= title_factor
        boosts.extend(title_boosts)

    generic_factor, generic_penalties = generic_concept_title_adjust(title, location)
    if generic_factor != 1.0:
        score *= generic_factor
        penalties.extend(generic_penalties)

    phrase_factor, phrase_boosts = phrase_match_adjust(query, haystack)
    if phrase_factor != 1.0:
        score *= phrase_factor
        boosts.extend(phrase_boosts)

    proximity_factor, proximity_boosts = proximity_adjust(sorted(matched_terms or set()), haystack)
    if proximity_factor != 1.0:
        score *= proximity_factor
        boosts.extend(proximity_boosts)

    if intent == INTENT_GENERAL:
        return (score, boosts, penalties)

    delta, intent_boosts, intent_penalties = score_intent(haystack, intent, query, topic_terms=topic_terms)
    factor = 1.0 + (delta * INTENT_WEIGHT)
    factor = max(INTENT_MIN_FACTOR, min(INTENT_MAX_FACTOR, factor))
    score *= factor
    boosts.extend(intent_boosts)
    penalties.extend(intent_penalties)

    return (score, boosts, penalties)


def _concept_postings(index, groups, scope):
    """Get the app's own token postings, grouping variants by query concept."""
    owners = collections.defaultdict(list)
    for concept, forms in groups.items():
        for form in forms:
            owners[form].append(concept)
    merged = {concept: collections.defaultdict(int) for concept in groups}
    forms = sorted(owners)
    for offset in range(0, len(forms), 400):
        batch = forms[offset:offset + 400]
        marks = ",".join("?" for _ in batch)
        sql = ("SELECT terms.term, terms.source_id, terms.tf FROM terms "
               "JOIN sources ON sources.id = terms.source_id "
               f"WHERE terms.term IN ({marks})")
        params = tuple(batch)
        if scope is not None:
            if not scope:
                return merged
            sql += " AND sources.source_type IN (" + ",".join("?" for _ in scope) + ")"
            params += tuple(scope)
        for form, source_id, frequency in index.conn.execute(sql, params):
            for concept in owners[form]:
                merged[concept][source_id] += frequency
    return merged


def _one_edit(left: str, right: str) -> bool:
    """One insertion, deletion, substitution or adjacent transposition."""
    if len(left) > len(right):
        left, right = right, left
    if len(right) - len(left) > 1 or left == right:
        return False
    i = next((n for n, ch in enumerate(left) if ch != right[n]), len(left))
    if len(left) != len(right):
        return left[i:] == right[i + 1:]
    if left[i + 1:] == right[i + 1:]:
        return True
    return (i + 1 < len(left) and left[i:i + 2] == right[i:i + 2][::-1]
            and left[i + 2:] == right[i + 2:])


def _fill_unmatched_terms(index, groups, scope):
    postings = _concept_postings(index, groups, scope)
    missing = [term for term in groups if not postings[term] and len(term) >= 5 and term.isalpha()]
    if not missing:
        return postings, {}
    fixes = {}
    for term in missing[:4]:
        # Keep the first two letters stable; bound vocabulary work and abstain on ambiguity.
        prefix = term[:2]
        params = [prefix, prefix + chr(0x10ffff), len(term) - 1, len(term) + 1]
        sql = ("SELECT DISTINCT terms.term FROM terms JOIN sources ON sources.id=terms.source_id "
               "WHERE terms.term >= ? AND terms.term < ? AND length(terms.term) BETWEEN ? AND ?")
        if scope is not None:
            sql += " AND sources.source_type IN (" + ",".join("?" for _ in scope) + ")"
            params.extend(scope)
        rows = index.conn.execute(sql + " ORDER BY terms.term LIMIT 257", params).fetchall()
        if len(rows) > 256:
            continue
        matches = [word for (word,) in rows if word.isalpha() and _one_edit(term, word)]
        if len(matches) == 1 and not any(matches[0] in forms for forms in groups.values()):
            fixes[term] = matches[0]
            groups[term] = groups[term] | {matches[0]}
    return (_concept_postings(index, groups, scope) if fixes else postings), fixes


def matching_source_ids(index, groups, source_types):
    """Return all matches, for operations that do not need relevance order."""
    return sorted({source_id for rows in _concept_postings(index, groups, source_types).values()
                   for source_id in rows})


def _build_doc_length_sql(source_types: Optional[Iterable[str]], source_type: Optional[str]) -> str:
    if source_types:
        placeholders = ",".join(["?"] * len(source_types))
        return f"""SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type IN ({placeholders}) GROUP BY terms.source_id"""
    if source_type:
        return """SELECT terms.source_id, SUM(terms.tf) AS total_terms FROM terms
            JOIN sources ON sources.id = terms.source_id
            WHERE sources.source_type = ? GROUP BY terms.source_id"""
    return "SELECT source_id, SUM(tf) AS total_terms FROM terms GROUP BY source_id"


def _load_document_lengths(
    index, types_list: Optional[List[str]], source_type: Optional[str],
) -> Tuple[Dict[int, float], float]:
    # data_version catches commits from other handles; total_changes catches ours.
    stamp = None
    if not index.conn.in_transaction:
        stamp = (index.conn.total_changes, index.conn.execute("PRAGMA data_version").fetchone()[0],
                 tuple(sorted(types_list)) if types_list else (), source_type)
        cached = getattr(index, "_ranker_lengths", None)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    doc_length_sql = _build_doc_length_sql(types_list, source_type)
    if types_list:
        rows = index.conn.execute(doc_length_sql, tuple(types_list)).fetchall()
    elif source_type:
        rows = index.conn.execute(doc_length_sql, (source_type,)).fetchall()
    else:
        rows = index.conn.execute(doc_length_sql).fetchall()
    lengths: Dict[int, float] = {sid: float(total or 0) for sid, total in rows}
    average_length = (sum(lengths.values()) / len(lengths)) if lengths else 1.0
    if average_length <= 0:
        average_length = 1.0
    result = lengths, average_length
    if stamp is not None:
        index._ranker_lengths = stamp, result
    return result


def search(
    index, query: str, limit: int = 8, source_type: Optional[str] = None,
    source_types: Optional[Iterable[str]] = None,
) -> List[Dict[str, object]]:
    """Search indexed sources and rank matches by relevance."""
    groups = query_groups(query)
    if limit <= 0 or not groups:
        return []
    meaningful_terms = set(groups)
    meaningful_total = len(groups)
    types_list = list(dict.fromkeys(source_types)) if source_types is not None else None
    if types_list == []:
        return []
    if types_list:
        total_sources = max(1, sum(index.source_count(t) for t in types_list))
    elif source_type:
        total_sources = max(1, index.source_count(source_type))
    else:
        total_sources = max(1, index.source_count())

    scope = types_list if types_list is not None else ([source_type] if source_type else None)
    postings, corrections = _fill_unmatched_terms(index, groups, scope)
    if not any(postings.values()):
        return []
    doc_lengths, average_doc_length = _load_document_lengths(index, types_list, source_type)
    scores: Dict[int, float] = collections.defaultdict(float)
    matched_meaningful: Dict[int, Set[str]] = collections.defaultdict(set)
    term_rarity: Dict[str, float] = {}

    for term, merged in postings.items():
        rows = sorted(merged.items())

        document_frequency = len(rows)
        if document_frequency == 0:
            continue

        rarity = relevance_engine.rarity_weight(document_frequency, total_sources)
        term_rarity[term] = rarity

        for source_id, term_frequency in rows:
            contribution = relevance_engine.term_contribution(term_frequency, document_frequency, total_sources)
            scores[source_id] += contribution
            matched_meaningful[source_id].add(term)

    if not scores:
        return []

    for source_id, raw_score in list(scores.items()):
        doc_length = doc_lengths.get(source_id, average_doc_length)
        scores[source_id] = raw_score * relevance_engine.shape_multiplier(doc_length, average_doc_length)

    adjusted_scores: Dict[int, float] = {}
    for source_id, base_score in scores.items():
        coverage = (
            len(matched_meaningful[source_id]) / meaningful_total if meaningful_total > 0 else 1.0
        )
        multiplier = COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * coverage
        adjusted_scores[source_id] = base_score * multiplier

    intent = detect_intent(query)
    # Case-sensitive identifiers avoid boosting ordinary prose matches.
    identifiers = [word for word in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", query)
                   if "_" in word or (not word.isupper() and any(c.isupper() for c in word[1:]))]
    declaration = None
    if identifiers:
        names = "|".join(map(re.escape, dict.fromkeys(identifiers)))
        declaration = re.compile(
            rf"(?m)^[ \t]*(?:(?:async[ \t]+)?(?:def|class)[ \t]+(?:{names})[ \t]*[(:\[]"
            rf"|(?:{names})[ \t]*=(?!=))"
        )
    candidate_pool = sorted(adjusted_scores.items(), key=lambda item: (-item[1], item[0]))[
        : max(0, limit) * INTENT_CANDIDATE_FACTOR + INTENT_CANDIDATE_MIN]

    rows_by_id: Dict[int, tuple] = {}
    reasons: Dict[int, Tuple[List[str], List[str]]] = {}

    for source_id, base_score in candidate_pool:
        row = index.conn.execute(
            "SELECT source_type, location, title, text, extension, size_bytes, indexed_at FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if row is None:
            continue
        rows_by_id[source_id] = row

        best_key, best_passage = (0, 0.0), ""
        for passage, hits, count in relevance_engine.scored_passages(row[3], groups.values()):
            key = (hits, hits / max(8, count))
            if key > best_key:
                best_key, best_passage = key, passage
        hits = best_key[0]
        new_score, boosts, penalties = intent_adjust(
            base_score, row[2] or row[1], best_passage, row[1], intent, query,
            topic_terms=meaningful_terms, term_rarity=term_rarity,
            matched_terms=matched_meaningful.get(source_id),
        )
        if hits:
            boosts.append(f"<passage-coverage>:{hits}/{meaningful_total}")
        # One additional concept in the same passage outweighs metadata.
        adjusted_scores[source_id] = hits + new_score / (1.0 + new_score)
        if declaration and (str(row[4]).lower().lstrip(".") == "py" or row[1].lower().endswith(".py")) and declaration.search(row[3]):
            adjusted_scores[source_id] += meaningful_total + 1
            boosts.append("<exact-symbol-definition>")
        reasons[source_id] = (boosts, penalties)

    ranked = sorted(
        ((source_id, adjusted_scores[source_id]) for source_id in rows_by_id),
        key=lambda item: (-item[1], item[0]),
    )[:max(0, limit)]

    documents: List[Dict[str, object]] = []
    for source_id, score in ranked:
        row = rows_by_id.get(source_id)
        if row is None:
            continue
        boosts, penalties = reasons.get(source_id, ([], []))
        documents.append({
            "id": source_id, "score": score, "source_type": row[0], "location": row[1],
            "title": row[2] or row[1], "text": row[3], "extension": row[4],
            "size_bytes": row[5], "indexed_at": row[6], "intent": intent,
            "intent_boosts": boosts, "intent_penalties": penalties,
            "query_corrections": corrections,
        })
    return documents


__all__ = [
    "COVERAGE_FLOOR", "GENERIC_CONCEPT_TITLE_PENALTY_FACTOR", "GENERIC_QUERY_VERBS",
    "GENERIC_TERM_DAMPING", "INTENT_MAX_FACTOR", "INTENT_MIN_FACTOR",
    "INTENT_TEXT_CHARS", "INTENT_WEIGHT", "PHRASE_MATCH_FACTOR",
    "PHRASE_MATCH_MIN_WORDS", "SIGNAL_GENERIC_CONCEPT_TITLE", "SIGNAL_PHRASE_MATCH",
    "SIGNAL_TITLE_MATCH", "STOPWORDS", "TITLE_MATCH_MAX_FACTOR", "TITLE_MATCH_WEIGHT",
    "generic_concept_title_adjust", "intent_adjust", "phrase_match_adjust",
    "proximity_adjust", "search", "title_match_adjust",
]
