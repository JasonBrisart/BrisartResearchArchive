r"""
File: brisart_ai/util.py

Purpose
-------
Share text, URL, digest and timestamp helpers across application owners.

Communication / relationships
-----------------------------
- brisart_ai/knowledge/index.py: now_ts(), stable_hash(), tokenize()
- brisart_ai/knowledge/ranker.py: tokenize(), title_tokens(), term_variants(),
  query_frame_terms()
- brisart_ai/knowledge/synthesizer.py: split_sentences(), tokenize(),
  expand_query_terms()
- brisart_ai/knowledge/ingest.py: file_hash()
- brisart_ai/io/readers.py: safe_read_text()
- brisart_ai/io/extractor.py: normalize_url()
- brisart_ai/web/crawler.py: normalize_url(), same_site(), stable_hash()
- brisart_ai/core/session_memory.py: now_ts(), tokenize()
- Imports brisart_hash.brisart_sha256() (replacing
  hashlib.sha256()) and brisart_url's
  brisart_urlsplit()/brisart_urlunsplit()/brisart_quote()/
  brisart_unquote() (replacing the corresponding urllib.parse
  functions); see 94_Native_API's/Official for how each of these
  was independently verified against the real stdlib function it
  replaces before being wired in here. Otherwise imports nothing from
  elsewhere in brisart_ai; only the standard library (re, time,
  pathlib) beyond that.

Settings / parameters
---------------------
- STOPWORDS: a small, English-only stopword set used by tokenize() to
  drop function words before terms are indexed or matched.
- WORD_RE: token boundary pattern for tokenize(); alphanumerics plus
  internal underscores/hyphens, at least two characters.
- term_variants() covers regular English singular/plural pairs only
  (-s, -es, -ies); terms shorter than MIN_VARIANT_LENGTH get none.
- QUESTION_FRAME_RE: "how do/does/did/can/will/would/could/should ...
  work(s)"; the trailing "work" is the question's frame, not its topic.
- SENTENCE_RE: a lookbehind split on sentence-ending punctuation, used
  by split_sentences(); sentences outside the 30-700 character band
  are dropped.

Edge cases
----------
- tokenize(None) and tokenize("") both return [] rather than raising.
- file_hash() streams a file in 1 MB chunks rather than reading it
  whole, each chunk fed through BrisartHash256.update().
- safe_read_text() reads at most max_bytes (5,000,000) and decodes them as
  UTF-8 with errors="replace", so it never raises. Text in another
  encoding, such as UTF-16 or Latin-1, comes back with replacement characters.
- normalize_url("") returns ""; normalize_url() on a schemeless string
  assumes https and prepends it before parsing.
- same_site() compares the netloc (host plus any port or user info),
  case-insensitively, so the same host on two ports is two sites.
- term_variants() never strips "ss" ("class" stays "class") and always
  includes the term itself; irregular plurals ("children") are not known.
- query_frame_terms() returns an empty set when "work" is the only topic
  word, so "how does it work" still searches for "work".

Known limitations
-----------------
- tokenize() drops one-character words and every STOPWORDS entry, which
  includes everyday words such as "file", "data", "use", "one" and "two", so
  a query made only of those words has no searchable terms.
- term_variants() knows regular English plurals only.
- safe_read_text() does not detect UTF-16 or Latin-1 (see Edge cases).

Examples
--------
::

    tokenize("Hello, World! Co-founder of the data lab")
    # ['hello', 'world', 'co-founder', 'lab']
    normalize_url("Example.COM/A%20b#top")
    # 'https://example.com/A%20b'
    query_frame_terms("how do lawsuits work?")
    # {'work'}
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
    raw = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return raw.decode(encoding, "replace")
        except Exception:
            continue
    return raw.decode("utf-8", "replace")
