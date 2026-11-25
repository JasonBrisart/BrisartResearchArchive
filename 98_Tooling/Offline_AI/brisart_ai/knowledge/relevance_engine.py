"""
Purpose
-------
Own lexical evidence measurements for local document and passage scoring.

Communication / relationships
-----------------------------
The ranker uses rarity, presence, length and proximity measurements.
The ranker and synthesizer use the same passage splitter and concept counts.

Settings / parameters
---------------------
Rarity is tiered and repetition credit is capped. Proximity uses a
120-character window. Long lines use 700-character windows with overlap.

Edge cases
----------
Short lines are retained. Long excerpts mark truncation with ellipses.
Closest-position comparisons walk sorted positions in linear time.
A bounded in-memory cache reuses profiles for up to 48 documents of at
most 32,768 characters. Short labels retain adjacent numeric or yes/no values.

Known limitations
-----------------
Line and sentence boundaries are heuristic, not grammatical parsing.
Long text windows may start or end inside a word.

Examples
--------
list(scored_passages("Permit expiry: June 30", [{"expiry", "expire"}]))
"""

from __future__ import annotations

import re
from functools import lru_cache

from brisart_ai.util import title_tokens, tokenize
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


__all__ = [
    "PRESENCE_SCHEDULE", "PROXIMITY_BONUS_CAP", "PROXIMITY_BONUS_PER_PAIR",
    "PROXIMITY_WINDOW_CHARS", "RARITY_TIERS", "SHAPE_BRACKETS", "SIGNAL_PROXIMITY",
    "presence_points", "proximity_bonus", "rarity_weight", "shape_multiplier",
    "term_contribution",
]
