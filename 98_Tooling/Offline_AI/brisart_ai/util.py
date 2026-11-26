r"""
File: brisart_ai/util.py

Purpose
-------
Provide shared token, text, digest, URL and timestamp primitives.

Public operations: now_ts (); stable_hash (value); file_hash (path); tokenize (text).

Public operations: title_tokens (title) - Tokens of a title or file name, split on
underscores, hyphens and dots; term_variants (term) - The term plus its regular
singular/plural forms ("lawsuits" <-> "lawsuit"); query_frame_terms (query) - Words that
frame a question rather than name its topic ("work" in "how do X work");
expand_query_terms (query) - Query tokens minus frame words, each with its
singular/plural variants.

Public operations: split_sentences (text); normalize_url (url); same_site (a, b);
safe_read_text (path, max_bytes=5000000).

Communication / relationships
-----------------------------
Retrieval and readers use these helpers; hashing and URL parsing use external Brisart
modules.

Direct project imports: brisart_hash, brisart_url.

Direct importing modules include brisart_ai/core/session_memory.py,
brisart_ai/io/extractor.py, brisart_ai/io/readers.py, brisart_ai/knowledge/index.py,
brisart_ai/knowledge/ingest.py, brisart_ai/knowledge/ranker.py,
brisart_ai/knowledge/relevance_engine.py, brisart_ai/knowledge/synthesizer.py,
brisart_ai/knowledge/vault.py, brisart_ai/tests/test_util.py.

Settings / parameters
---------------------
safe_read_text enforces a byte ceiling; tokenization uses an ASCII-oriented pattern and
stop words.

Module configuration and named constants: STOPWORDS (set, 79 entries), WORD_RE,
SENTENCE_RE, TITLE_SPLIT_RE, MIN_VARIANT_LENGTH=3, QUESTION_FRAME_RE, FRAME_TERMS.

Call signatures: now_ts(); stable_hash(value); file_hash(path); tokenize(text);
title_tokens(title).

Call signatures: term_variants(term); query_frame_terms(query);
expand_query_terms(query); split_sentences(text); normalize_url(url).

Call signatures: same_site(a, b); safe_read_text(path, max_bytes=5000000).

Edge cases
----------
BOM-marked UTF-8 and UTF-16 are recognized; malformed text decodes with replacement.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
Non-BOM legacy encodings and full linguistic segmentation are not inferred.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
term_variants("lawsuits")

Other callable entry points in this module include stable_hash, file_hash, tokenize,
title_tokens, term_variants, query_frame_terms, expand_query_terms, plus 4 more.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List, Set

from brisart_hash import brisart_sha256
from brisart_url import (
    brisart_quote,
    brisart_unquote,
    brisart_urlsplit,
    brisart_urlunsplit,
)

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "her", "his", "i", "in", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with",
    "you", "your", "how", "about", "into", "over", "under", "can",
    "could", "should", "would", "not", "no", "yes", "do", "does",
    "did", "than", "then", "there", "here", "if", "so", "like",
    "file", "files", "data", "using", "use", "used", "also", "may",
    "one", "two",
}

WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]{1,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
TITLE_SPLIT_RE = re.compile(r"[_\-.]+")
MIN_VARIANT_LENGTH = 3
QUESTION_FRAME_RE = re.compile(
    r"\bhow\s+(?:do|does|did|can|will|would|could|should)\b.*\bwork(?:s|ed)?\b\W*$",
    re.IGNORECASE,
)
FRAME_TERMS = frozenset({"work", "works", "worked"})
_VOWELS = set("aeiou")


def now_ts() -> int:
    return int(time.time())


def stable_hash(value: str) -> str:
    return brisart_sha256(value.encode("utf-8", "replace")).hexdigest()


def file_hash(path: Path) -> str:
    h = brisart_sha256(b"")
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def tokenize(text: str) -> List[str]:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def title_tokens(title: str) -> List[str]:
    """Tokens of a title or file name, split on underscores, hyphens and dots."""
    return tokenize(TITLE_SPLIT_RE.sub(" ", title or ""))


def term_variants(term: str) -> Set[str]:
    """The term plus its regular singular/plural forms ("lawsuits" <-> "lawsuit")."""
    term = str(term or "").lower()
    variants = {term} if term else set()
    if len(term) < MIN_VARIANT_LENGTH or not term.isalpha():
        return variants
    if term.endswith("ies") and len(term) > 4:
        variants.add(term[:-3] + "y")
    elif term.endswith("es") and len(term) > 4 and (term[-3] in "sxz" or term[-4:-2] in ("ch", "sh")):
        variants.add(term[:-2])
    elif term.endswith("s") and not term.endswith("ss") and len(term) > 3:
        variants.add(term[:-1])
    if term.endswith("y") and term[-2] not in _VOWELS:
        variants.add(term[:-1] + "ies")
    elif term.endswith(("s", "x", "z", "ch", "sh")):
        variants.add(term + "es")
    else:
        variants.add(term + "s")
    return variants


def query_frame_terms(query: str) -> Set[str]:
    """Words that frame a question rather than name its topic ("work" in "how do X work")."""
    if not QUESTION_FRAME_RE.search(query or ""):
        return set()
    frame = set(tokenize(query)) & FRAME_TERMS
    topic = [t for t in tokenize(query) if t not in FRAME_TERMS]
    return frame if topic else set()


def expand_query_terms(query: str) -> Set[str]:
    """Query tokens minus frame words, each with its singular/plural variants."""
    frame = query_frame_terms(query)
    expanded: Set[str] = set()
    for term in tokenize(query):
        if term not in frame:
            expanded |= term_variants(term)
    return expanded


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    out = []
    for sentence in SENTENCE_RE.split(text):
        sentence = sentence.strip()
        if 30 <= len(sentence) <= 700:
            out.append(sentence)
    return out


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    parsed = brisart_urlsplit(url)
    if not parsed.scheme:
        url = "https://" + url
        parsed = brisart_urlsplit(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = brisart_quote(brisart_unquote(path), safe="/%:@")
    return brisart_urlunsplit(
        type(parsed)(scheme, netloc, path, parsed.query, "")
    )


def same_site(a: str, b: str) -> bool:
    return brisart_urlsplit(a).netloc.lower() == brisart_urlsplit(b).netloc.lower()


def safe_read_text(path: Path, max_bytes: int = 5_000_000) -> str:
    with path.open("rb") as stream:
        raw = stream.read(max(0, max_bytes))
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8-sig", "replace")
