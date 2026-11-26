"""Purpose
-------
Classify local search questions and define lexical cues for supporting evidence.

This application module defines `name_candidates`, `is_generic_concept_page`,
`is_bare_generic_concept_title`, `looks_like_person_name`, `wants_person`. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
The ranker builds query plans from these rules. The relevance engine interprets
passage cues when ranking and selecting excerpts.

The direct in-project imports visible in this module are the standard library and its direct
caller. Public entry points `name_candidates`, `is_generic_concept_page`,
`is_bare_generic_concept_title`, `looks_like_person_name`, `wants_person`; this identifies
where behavior is invoked without implying a separate hidden dependency. Higher-level
coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Intent, scoring signals, and bounded English cue patterns are defined here.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Explicit negation and unrelated dates are not direct evidence. Renewal and
submission questions require a deadline cue; multiple tracked events in one
passage are treated conservatively. Dependency and alias patterns preserve explicit direction and negation.
Relationship qualifiers carry explicit dates or exact numeric release labels.
Dependency lifecycle statements keep starts and ends distinct. As-of qualifiers
require a calendar-valid date with an explicit year. Release qualifiers may
precede a claim or follow it; release labels are exact, not ranges.

The behaviors documented above must be read together with the actual branches in intent.py; a
caller must not infer success from an empty, rejected, or unsupported result. Error handling,
input validation, and early returns remain the responsibility of the concrete functions in
this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Explicit ISO and English month-name dates are calendar-checked.
A missing year is not inferred. Deadline paraphrases use explicit English
statement forms and preserve subject modifiers; other wording stays literal. The rules do not resolve
relative dates, release ranges, or arbitrary phrasing. Relationship parsing matches complete
statements; the relevance engine combines claims from separate passages.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
evidence_mode("When must I submit the workshop report?", 3)

For a concrete entry point, inspect `name_candidates`, `is_generic_concept_page`,
`is_bare_generic_concept_title`, `looks_like_person_name`, `wants_person`; invoke it through
the existing application entry point or its documented caller. The example above is
illustrative of this file's present interface; do not treat it as an instruction to create
additional state or call private functions directly.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, FrozenSet, List, Sequence, Set, Tuple

from brisart_url import brisart_unquote

INTENT_FOUNDER = "founder"
INTENT_INVENTOR = "inventor"
INTENT_STATISTIC = "statistic"
INTENT_EXPLANATION = "explanation"
INTENT_COMPARISON = "comparison"
INTENT_GENERAL = "general"

ALL_INTENTS: Tuple[str, ...] = (
    INTENT_FOUNDER, INTENT_INVENTOR, INTENT_STATISTIC,
    INTENT_EXPLANATION, INTENT_COMPARISON, INTENT_GENERAL,
)

_CREATION_VERBS: FrozenSet[str] = frozenset({
    "invented", "invent", "invents", "invention", "created", "create",
    "creates", "founded", "found", "founds", "made", "make", "makes",
    "started", "start", "starts", "built", "build", "builds", "developed",
    "develop", "develops", "designed", "design", "designs", "wrote", "write",
    "writes",
})

_KNOWN_COMPANIES: FrozenSet[str] = frozenset({
    "microsoft", "apple", "google", "amazon", "facebook", "meta", "netflix",
    "tesla", "twitter", "ibm", "intel", "nvidia", "oracle", "adobe", "spacex",
    "openai", "anthropic", "uber", "airbnb", "paypal", "ebay", "yahoo", "sony",
    "samsung", "nintendo", "sega", "valve", "spotify", "reddit", "linkedin",
    "youtube", "instagram", "tiktok", "snapchat", "discord", "dropbox",
    "salesforce", "cisco", "dell", "hp", "lenovo", "qualcomm", "amd", "boeing",
    "ford", "toyota", "honda", "walmart", "costco", "starbucks", "mcdonalds",
    "nike", "disney", "pixar", "wikipedia", "mozilla", "canonical", "redhat",
    "github", "gitlab", "atlassian", "shopify", "stripe", "square", "robinhood",
    "coinbase", "binance", "twitch", "doordash", "instacart", "peloton",
    "zillow", "yelp", "grubhub", "chegg", "asana", "notion", "figma", "canva",
    "palantir", "snowflake", "databricks", "block", "blizzard", "activision",
    "ubisoft", "riot", "epic", "slack", "zoom", "airtable", "twilio", "okta",
    "datadog", "roblox", "unity", "epicgames",
})

_PRODUCT_WORDS: FrozenSet[str] = frozenset({
    "powerpoint", "excel", "word", "outlook", "office", "windows", "teams",
    "azure", "onedrive", "sharepoint", "iphone", "ipad", "macbook", "android",
    "chrome", "gmail", "photoshop",
})

_STATISTIC_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "many"), ("how", "much"), ("number", "of"), ("count", "of"),
    ("amount", "of"), ("total", "of"), ("population", "of"),
)
_STATISTIC_WORDS: FrozenSet[str] = frozenset(
    {"population", "estimate", "estimated", "statistics", "census"}
)

_EXPLANATION_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("how", "does"), ("how", "do"), ("how", "did"), ("how", "is"),
    ("how", "are"), ("how", "can"), ("what", "causes"), ("what", "cause"),
    ("why", "do"), ("why", "does"), ("why", "is"), ("why", "are"),
)
_EXPLANATION_LEAD_WORDS: FrozenSet[str] = frozenset({"why", "explain"})

_WHEN_PHRASES: Tuple[Tuple[str, ...], ...] = (
    ("when", "was"), ("when", "did"), ("when", "were"), ("what", "year"),
)

_COMPARISON_QUERY_RE = re.compile(
    r"\b(vs\.?|versus|compare|comparison|compared|outlive[sd]?|outlast[sd]?|"
    r"better|worse|longer|shorter|faster|slower|bigger|smaller|cheaper|"
    r"more\s+expensive|higher|lower|stronger|weaker|difference|different|"
    r"which\s+is)\b",
    re.IGNORECASE,
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'\-]*")


def _words(text: str) -> List[str]:
    return _WORD_RE.findall(str(text or "").casefold())


def _has_phrase(words: Sequence[str], phrase: Sequence[str]) -> bool:
    span = len(phrase)
    if span == 0 or len(words) < span:
        return False
    target = tuple(phrase)
    for start in range(len(words) - span + 1):
        if tuple(words[start:start + span]) == target:
            return True
    return False


INTENT_BOOSTS: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: (
        "founder", "founders", "founded", "founding", "co-founder", "cofounder",
        "co-founders", "cofounders", "history", "origin", "origins", "company",
        "corporation", "established", "founded by", "created by", "started by",
        "early history", "biography", "entrepreneur",
    ),
    INTENT_INVENTOR: (
        "inventor", "inventors", "invented", "invention", "history", "developed",
        "discovered", "origin", "origins", "pioneer", "bell labs", "laboratories",
        "patent", "first", "timeline", "invented by", "developed by", "discovery",
    ),
    INTENT_STATISTIC: (
        "population", "statistics", "stats", "estimate", "estimated", "census",
        "demographics", "number", "numbers", "count", "million", "billion",
        "thousand", "percent", "percentage", "households", "survey", "data",
        "total", "figures",
    ),
    INTENT_EXPLANATION: (
        "explanation", "explained", "cause", "causes", "mechanism", "science",
        "guide", "behavior", "behaviour", "process", "works", "working",
        "reason", "reasons", "how", "why", "because", "theory", "principle",
        "principles",
    ),
    INTENT_COMPARISON: (
        "comparison", "compare", "compares", "compared", "versus", "vs",
        "difference", "differences", "study", "research", "data", "statistics",
        "analysis", "report",
    ),
    INTENT_GENERAL: (),
}

INTENT_PENALTIES: Dict[str, Tuple[str, ...]] = {
    INTENT_FOUNDER: (
        "powerpoint", "excel", "outlook", "office", "microsoft-365",
        "microsoft365", "download", "pricing", "buy", "subscription", "sign-in",
        "signin", "sign in", "log-in", "login", "account", "support", "help",
        "troubleshoot", "install", "product", "products", "store", "app", "apps",
        "template", "templates", "tutorial", "album", "song", "film", "movie",
        "invention",
    ),
    INTENT_INVENTOR: (
        "album", "song", "single", "band", "lyrics", "discography", "movie",
        "film", "tv-series", "download", "buy", "pricing", "store", "support",
        "login", "account", "shop", "datasheet", "buy-now", "coupon",
    ),
    INTENT_STATISTIC: (
        "breed", "breeds", "adoption", "adopt", "shelter", "rescue", "album",
        "song", "movie", "film", "shop", "store", "buy", "pricing", "login",
        "account", "recipe", "toys", "names", "glossary", "dictionary",
        "definition", "meaning",
    ),
    INTENT_EXPLANATION: (
        "buy", "shop", "store", "pricing", "coupon", "deal", "deals", "login",
        "account", "album", "song", "movie", "film", "glossary", "dictionary",
        "definition", "list-of", "best-", "top-10", "top-", "review", "reviews",
    ),
    INTENT_COMPARISON: (
        "buy", "shop", "store", "pricing", "coupon", "login", "account", "album",
        "song", "movie", "film", "glossary", "dictionary", "definition",
    ),
    INTENT_GENERAL: (),
}

DATE_BOOSTS: Tuple[str, ...] = (
    "timeline", "chronology", "history", "year", "date", "dates", "century",
    "anniversary",
)
_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20[0-2]\d)\b")
_WORK_QUALIFIER_RE = re.compile(
    r"\((?:album|song|single|ep|band|film|movie|tv series|television series"
    r"|novel|book|video game|game|magazine|comics|play|musical|opera"
    r"|soundtrack|mixtape)\)",
    re.IGNORECASE,
)
SIGNAL_PERSON = "<person>"
SIGNAL_YEAR = "<year>"
SIGNAL_WORK = "<work-of-art>"
SIGNAL_GENERIC = "<generic-concept>"
BOOST_WEIGHTS: Dict[str, float] = {SIGNAL_PERSON: 2.0, SIGNAL_YEAR: 1.5}
PENALTY_WEIGHTS: Dict[str, float] = {SIGNAL_WORK: 3.0, SIGNAL_GENERIC: 1.5}
DEFAULT_PENALTY_WEIGHT = 1.5
_NON_NAME_TOKENS: FrozenSet[str] = frozenset({
    "the", "of", "and", "a", "an", "in", "on", "for", "inc", "corp",
    "corporation", "company", "ltd", "llc", "group", "history", "invention",
    "album", "song", "film", "movie", "list", "index", "category", "wikipedia",
    "news", "home", "login", "account", "support", "download", "university",
    "institute", "labs", "laboratories", "museum", "school",
})
_NAME_PART_RE = re.compile(r"^[A-Z][a-z]{1,}$")
_NAME_INITIAL_RE = re.compile(r"^[A-Z]\.?$")
_GENERIC_CONCEPT_TITLES: FrozenSet[str] = frozenset({
    "invention", "inventions", "inventor", "inventors", "discovery",
    "innovation", "technology", "science", "engineering", "history", "company",
    "corporation", "business", "entrepreneur", "entrepreneurship", "founder",
    "founders", "creation", "design", "research", "development", "population",
    "statistics", "demographics", "estimation", "explanation", "causality",
    "behavior", "behaviour", "law", "laws", "legislation", "politics",
    "government",
})


def name_candidates(text: str) -> List[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    candidates = [raw]
    if "//" in raw or raw.count("/") >= 2:
        path = raw.split("?", 1)[0].split("#", 1)[0]
        segments = [seg for seg in path.split("/") if seg]
        if segments:
            last = brisart_unquote(segments[-1])
            last = re.sub(r"\.(html?|php|aspx?|htm)$", "", last, flags=re.I)
            if last and last not in candidates:
                candidates.append(last)
    return candidates


def is_generic_concept_page(text: str, topic_terms: Set[str]) -> bool:
    for candidate in name_candidates(text):
        title = re.sub(r"_", " ", str(candidate or "")).strip()
        title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().casefold()
        if not title or " " in title:
            continue
        if title not in _GENERIC_CONCEPT_TITLES:
            continue
        subject_terms = {term.casefold() for term in (topic_terms or set())}
        if title in subject_terms:
            return False
        return True
    return False


def is_bare_generic_concept_title(candidate: str) -> bool:
    """True when `candidate` is a bare generic-concept title/slug.

    >>> is_bare_generic_concept_title("Law")
    True
    >>> is_bare_generic_concept_title("Law - Wikipedia")
    True
    >>> is_bare_generic_concept_title("History of the Transistor")
    False
    >>> is_bare_generic_concept_title("Law of South Africa")
    False
    """
    if not candidate:
        return False
    cleaned = re.sub(r"[_\-]+", " ", str(candidate)).strip()
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()
    cleaned = re.split(r"\s+[-|:]\s+", cleaned, maxsplit=1)[0].strip()
    cleaned = cleaned.casefold()
    if not cleaned or " " in cleaned:
        return False
    return cleaned in _GENERIC_CONCEPT_TITLES


def looks_like_person_name(text: str) -> bool:
    raw = str(text or "").replace("_", " ")
    raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    if not raw or any(ch.isdigit() for ch in raw):
        return False
    parts = raw.split()
    if not 2 <= len(parts) <= 3:
        return False
    if any(part.casefold() in _NON_NAME_TOKENS for part in parts):
        return False
    if not _NAME_PART_RE.match(parts[0]):
        return False
    if not _NAME_PART_RE.match(parts[-1]):
        return False
    if len(parts) == 3 and not (
        _NAME_PART_RE.match(parts[1]) or _NAME_INITIAL_RE.match(parts[1])
    ):
        return False
    return True


def wants_person(query: str) -> bool:
    return "who" in set(_words(query))


def detect_intent(query: str) -> str:
    words = _words(query)
    if not words:
        return INTENT_GENERAL
    word_set = set(words)

    if any(_has_phrase(words, phrase) for phrase in _STATISTIC_PHRASES):
        return INTENT_STATISTIC
    if word_set & _STATISTIC_WORDS:
        return INTENT_STATISTIC

    if _COMPARISON_QUERY_RE.search(_NEGATED_COMPARISON.sub("", str(query or ""))):
        return INTENT_COMPARISON

    has_creation = bool(word_set & _CREATION_VERBS)

    if not has_creation or "who" not in word_set:
        if any(_has_phrase(words, phrase) for phrase in _EXPLANATION_PHRASES):
            return INTENT_EXPLANATION
        if words[0] in _EXPLANATION_LEAD_WORDS:
            return INTENT_EXPLANATION

    if has_creation:
        if word_set & _PRODUCT_WORDS:
            return INTENT_INVENTOR
        if word_set & _KNOWN_COMPANIES:
            return INTENT_FOUNDER
        return INTENT_INVENTOR

    return INTENT_GENERAL


def wants_date(query: str) -> bool:
    words = _words(query)
    return any(_has_phrase(words, phrase) for phrase in _WHEN_PHRASES)


def boost_terms(intent: str, query: str = "") -> Tuple[str, ...]:
    terms = INTENT_BOOSTS.get(intent, ())
    if query and wants_date(query):
        merged = list(terms)
        for term in DATE_BOOSTS:
            if term not in merged:
                merged.append(term)
        return tuple(merged)
    return terms


def penalty_terms(intent: str) -> Tuple[str, ...]:
    return INTENT_PENALTIES.get(intent, ())


def _normalize_haystack(text: str) -> Tuple[str, Set[str]]:
    lowered = str(text or "").casefold()
    spaced = re.sub(r"[^a-z0-9]+", " ", lowered)
    spaced = re.sub(r"\s+", " ", spaced).strip()
    return (spaced, set(spaced.split()))


def _match_vocabulary(
    haystack: str, tokens: Set[str], vocabulary: Sequence[str],
) -> List[str]:
    hits: List[str] = []
    for entry in vocabulary:
        normalized = re.sub(r"[^a-z0-9]+", " ", entry.casefold()).strip()
        if not normalized:
            continue
        if " " in normalized:
            if normalized in haystack:
                hits.append(entry)
        elif normalized in tokens:
            hits.append(entry)
    return hits


def score_intent(
    text: str, intent: str, query: str = "", boost_weight: float = 1.0,
    penalty_weight: float = DEFAULT_PENALTY_WEIGHT, max_boosts: int = 4,
    topic_terms: Set[str] | None = None,
) -> Tuple[float, List[str], List[str]]:
    haystack, tokens = _normalize_haystack(text)
    if not haystack:
        return (0.0, [], [])

    vocabulary_hits = _match_vocabulary(haystack, tokens, boost_terms(intent, query))
    penalties = _match_vocabulary(haystack, tokens, penalty_terms(intent))

    strong_boosts: List[str] = []

    if query and wants_date(query) and _YEAR_RE.search(haystack):
        strong_boosts.append(SIGNAL_YEAR)

    if (
        query and intent in (INTENT_FOUNDER, INTENT_INVENTOR)
        and wants_person(query)
        and any(looks_like_person_name(candidate) for candidate in name_candidates(text))
    ):
        strong_boosts.append(SIGNAL_PERSON)

    if _WORK_QUALIFIER_RE.search(str(text or "")):
        penalties = penalties + [SIGNAL_WORK]

    if topic_terms is not None and is_generic_concept_page(text, topic_terms):
        penalties = penalties + [SIGNAL_GENERIC]

    counted = vocabulary_hits[: max(0, max_boosts)]
    boost_total = sum(BOOST_WEIGHTS.get(term, 1.0) for term in counted) + \
        sum(BOOST_WEIGHTS.get(term, 1.0) for term in strong_boosts)
    penalty_total = sum(PENALTY_WEIGHTS.get(term, 1.0) for term in penalties)

    delta = (boost_total * boost_weight) - (penalty_total * penalty_weight)
    return (delta, counted + strong_boosts, penalties)


def describe_intent(intent: str, query: str = "") -> str:
    if intent == INTENT_GENERAL:
        return "general (no specific intent detected; term overlap only)"
    date_note = " +dates" if query and wants_date(query) else ""
    return (
        f"{intent}{date_note} "
        f"(boosts={len(boost_terms(intent, query))}, "
        f"penalties={len(penalty_terms(intent))})"
    )


_NEGATED_COMPARISON = re.compile(
    r"\b(?:(?:do not|don't|never)\s+compare|(?:not|no)\s+(?:a\s+)?comparison)\b", re.I,
)
_METHOD_QUERY = re.compile(
    r"^\s*(?:how\s+(?:does|do|did)|explain\s+how)\s+(.+?)"
    r"\s+(?:works?|worked|operates?|operated|functions?|functioned)[?.!\s]*$", re.I,
)


def mechanism_subject(query: str) -> str:
    """Return the subject only for a complete how-it-works query."""
    match = _METHOD_QUERY.fullmatch(query)
    return match[1] if match else ""


_MECHANISM = re.compile(r"\b(?:inform(?:s)?|combin(?:e|es|ed)|integrat(?:e|es|ed)|"
                        r"transforms?|converts?|returns?|feeds?|cycles?|updates?|"
                        r"begins?|starts?|controls?|uses?|generates?|produces?|filter(?:s|ed)?|"
                        r"enables?|drives?|gates?|carries?|passed|carried|"
                        r"(?:works?|operates?|functions?)\s+by)\b", re.I)
_ROLE = re.compile(r"\b(?:is|are|describes?|defines?|uses?|measures?|tracks?|"
                   r"focus(?:es)?|evaluates?|stabilizes?|controls?|serves?|"
                   r"regulates?|records?|detects?|provides?|handles?|tests?|reports?)\b", re.I)
_CONTRAST = re.compile(r"\b(?:unlike|whereas|while|different|contrast|compared)\b", re.I)
_METADATA = re.compile(r"^\s*(?:#{1,6}\s|file:|imports?\s|introduced\b|"
                       r"added\b|changelog\b|(?:[A-Z_]{3,})\s*=|```)", re.I)
# Indexed hints only; exact claim parsing remains the evidence gate.
RELATIONSHIP_POSTING_TERMS = frozenset({
    "depends", "depend", "requires", "require", "required", "relies", "rely", "known", "abbreviated", "aka",
    "dependency", "depending", "requiring", "relying", "dependent", "independent",
})

# Direct dependency questions, with one optional endpoint left to discover.
_DEPENDENCY_QUERIES = (
    re.compile(r"does (.+?) (?:depend on|require|rely on) (.+)", re.I),
    re.compile(r"what does (.+?) (?:depend on|require|rely on)", re.I),
    re.compile(r"what (?:depends on|requires|relies on) (.+)", re.I),
)
_ENTITY = re.compile(r"[\w][\w.-]*(?:\s+[\w][\w.-]*){0,5}")
_ENTITY_GLUE = re.compile(
    r"\b(?:it|they|and|or|not|never|may|might|could|would|will|if|unless|when|"
    r"because|whether|without|only|probably|optionally|currently|by|on|is|are|has|started|began|stopped|ceased|became|depends?|requires?|relies|rely|see|check)\b", re.I,
)
_DEPENDENCY_ACTIVE = re.compile(r"(.+?)\s+(depends? on|requires?|relies on|(?:does not|doesn['\u2019]t) (?:depend on|require|rely on)|no longer (?:depends on|requires|relies on))\s+(.+)", re.I)
_DEPENDENCY_STATE = re.compile(
    r"(.+?)\s+is (?:(not|no longer) dependent on|(dependent on|independent of))\s+(.+)", re.I,
)
_DEPENDENCY_PASSIVE_QUERY = re.compile(r"is (.+?) (?:required by|a dependency of) (.+)", re.I)
_DEPENDENCY_PASSIVE = re.compile(
    r"(.+?)\s+is ((?:not|no longer) )?(?:required by|a dependency of)\s+(.+)", re.I,
)
_DEPENDENCY_DATE_QUERY = re.compile(
    r"when did (.+?) (start|begin|stop|cease) (?:depending on|requiring|relying on) (.+)", re.I,
)
_DEPENDENCY_DATE_CLAIM = re.compile(
    r"(.+?) (started|began|stopped|ceased) (?:depending on|requiring|relying on) (.+?) on <date>", re.I,
)
_DEPENDENCY_DATE_PASSIVE = re.compile(
    r"(.+?) (became|ceased to be) (?:required by|a dependency of) (.+?) on <date>", re.I,
)


def dependency_date_request(query: str):
    match = _DEPENDENCY_DATE_QUERY.fullmatch(" ".join(query.strip().rstrip("?!. ").split()))
    if match:
        left, right = _named_endpoint(match[1]), _named_endpoint(match[3])
        if left and right and left != right:
            return (left, right), "start" if match[2].casefold() in {"start", "begin"} else "end"
    return None


def dependency_date_statement(text: str):
    """Return ordered entities, lifecycle event and normalized explicit date."""
    dates = list(date_mentions(text))
    if len(dates) != 1 or dates[0][1] is None:
        return None
    (start, end), value = dates[0]
    statement = " ".join((text[:start] + "<date>" + text[end:]).strip().removesuffix(".").split())
    if match := _DEPENDENCY_DATE_CLAIM.fullmatch(statement):
        left, right = match[1], match[3]
    elif match := _DEPENDENCY_DATE_PASSIVE.fullmatch(statement):
        left, right = match[3], match[1]
    else:
        return None
    left, right = _named_endpoint(left), _named_endpoint(right)
    if left and right and left != right:
        event = "start" if match[2].casefold() in {"started", "began", "became"} else "end"
        return left, right, event, value
    return None


def _named_endpoint(text: str) -> str:
    text = " ".join(text.casefold().split()).removeprefix("the ")
    return text if _ENTITY.fullmatch(text) and not _ENTITY_GLUE.search(text) else ""


# Qualifiers must be attached to a statement, never inferred from filenames or ingest time.
_RELATIONSHIP_PREFIX = re.compile(
    r"^\s*(as of|on|(?:in|for) (?:version|release)|from)\s+(.+?),\s*(?!\s*[0-9]{4}(?:,|\s+through\b))", re.I,
)
_VERSION_VALUE = re.compile(r"v?([0-9]+(?:\.[0-9]+){1,2})", re.I)
_VERSION_SUFFIX = re.compile(
    r"(?:,\s*|\s+)(?:in|for) (?:version|release)\s+(v?[0-9][^\s,?!.]*(?:\.[^\s,?!.]+)*|latest)\s*[?!.]*$",
    re.I,
)


def _explicit_day(text: str) -> str:
    for span, value in date_mentions(text):
        if span == (0, len(text)) and value and value[0] is not None:
            return date(*value).isoformat()
    return ""


def relationship_context(text: str, *, query: bool = False):
    """Split explicit qualifiers into (start day, end day, exact release)."""
    start = end = version = ""
    valid = True
    if suffix := _VERSION_SUFFIX.search(text):
        value = _VERSION_VALUE.fullmatch(suffix[1])
        valid = value is not None
        version = value[1] if value else ""
        text = text[:suffix.start()]
    while match := _RELATIONSHIP_PREFIX.match(text):
        kind, payload = match[1].casefold(), match[2].strip()
        text = text[match.end():]
        if kind.endswith((" version", " release")):
            value = _VERSION_VALUE.fullmatch(payload)
            if version or not value:
                valid = False
            else:
                version = value[1]
        elif start or (query and kind != "as of") or (not query and kind == "as of"):
            valid = False
        else:
            days = re.split(r"\s+through\s+", payload, flags=re.I) if kind == "from" else [payload, payload]
            normalized = [_explicit_day(day) for day in days]
            if len(normalized) != 2 or not all(normalized):
                valid = False
                continue
            start, end = normalized
            if start > end:
                valid = False
    return text, (start, end, version) if valid else None


def dependency_request(query: str) -> tuple[str, str] | None:
    """Return ordered entity names; an empty side is requested, not assumed."""
    query = " ".join(query.strip().rstrip("?!. ").split())
    if match := _DEPENDENCY_PASSIVE_QUERY.fullmatch(query):
        left, right = _named_endpoint(match[2]), _named_endpoint(match[1])
        return (left, right) if left and right and left != right else None
    for number, pattern in enumerate(_DEPENDENCY_QUERIES):
        match = pattern.fullmatch(query)
        if not match:
            continue
        if number == 0:
            left, right = match.groups()
            left, right = _named_endpoint(left), _named_endpoint(right)
            return (left, right) if left and right and left != right else None
        name = _named_endpoint(match[1])
        if not name:
            return None
        return (name, "") if number == 1 else ("", name)
    return None


def dependency_statement(text: str) -> tuple[str, str, bool] | None:
    """Extract the ordered names and explicit negative polarity from a statement."""
    text = text.strip().rstrip(".! ")
    match = _DEPENDENCY_PASSIVE.fullmatch(text)
    negative = False
    if match:
        left, right = match[3], match[1]
        negative = bool(match[2])
    elif match := _DEPENDENCY_STATE.fullmatch(text):
        left, right = match[1], match[4]
        negative = bool(match[2]) or (match[3] or "").casefold() == "independent of"
    else:
        match = _DEPENDENCY_ACTIVE.fullmatch(text)
        if not match:
            return None
        left, right = match[1], match[3]
        negative = match[2].casefold().startswith(("does not ", "doesn't ", "doesn\u2019t ", "no longer "))
    left, right = _named_endpoint(left), _named_endpoint(right)
    return (left, right, negative) if left and right and left != right else None


_ALIAS = re.compile(r"(.+?)\s+(?:is also known as|is abbreviated as|aka)\s+(.+)", re.I)


def alias_statement(text: str) -> tuple[str, str] | None:
    """Extract a declared canonical name and alias; never guess acronyms."""
    match = _ALIAS.fullmatch(text.strip().rstrip(".! "))
    if match:
        canonical, alias = map(_named_endpoint, match.groups())
        if canonical and alias and canonical != alias:
            return canonical, alias
    return None


_DATE_QUERY = re.compile(r"^\s*(?:when\b|(?:what|which)\s+(?:date|day)\b)", re.I)
_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|"
          r"July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_DAY = r"(?:0?[1-9]|[12][0-9]|3[01])(?:st|nd|rd|th)?"
_DATE_VALUE = re.compile(
    rf"\b(?:(?P<iso>[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})|"
    rf"(?:(?P<m1>{_MONTH})\.?\s+(?P<d1>{_DAY})|(?P<d2>{_DAY})\s+(?P<m2>{_MONTH}))"
    r"(?:,?\s+(?P<year>[0-9]{4}))?)\b", re.I,
)
_MONTH_NUMBERS = {name: number for number, name in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1
)}


def date_mentions(text: str):
    """Yield source spans and normalized dates, with None for invalid values."""
    for match in _DATE_VALUE.finditer(text):
        value = None
        try:
            if match["iso"]:
                parsed = date.fromisoformat(match["iso"])
                value = (parsed.year, parsed.month, parsed.day)
            else:
                month = _MONTH_NUMBERS[(match["m1"] or match["m2"])[:3].lower()]
                day = int(re.match(r"[0-9]+", match["d1"] or match["d2"])[0])
                year = int(match["year"]) if match["year"] else None
                date(year if year is not None else 2000, month, day)
                value = (year, month, day)
        except ValueError:
            pass
        yield match.span(), value


# Query and source cues stay paired so one event cannot answer another.
_DATE_EVENTS = (
    (re.compile(r"\bexpir\w*\b", re.I), re.compile(r"\b(?:expir\w*|valid until)\b", re.I), False),
    (re.compile(r"\brenew\w*\b", re.I), re.compile(r"\brenew\w*\b", re.I), True),
    (re.compile(r"\b(?:submit|submission|apply|application)\w*\b", re.I),
     re.compile(r"\b(?:submit|submission|apply|application)\w*\b", re.I), True),
)
_DEADLINE_MARKER = re.compile(r"\b(?:deadline|due|by|closes?)\b", re.I)
_EXPLICIT_DUE = re.compile(r"\b(?:deadline|due)\b", re.I)
_DEADLINE_EVIDENCE = re.compile(r"\b(?:expir\w*|deadline|due|valid until)\b", re.I)

_NO_CONTRAST = re.compile(r"\b(?:no (?:direct )?comparison|not compared|not a comparison)\b", re.I)
_NEGATED_DEADLINE = re.compile(
    r"\b(?:does not expire|doesn't expire|never expires?|no (?:expiry|expiration|deadline)|"
    r"(?:expiry|expiration|deadline|due date)\s+(?:is\s+)?not)\b", re.I,
)

_COMPARISON_MENTION = re.compile(
    r"\b(?:agenda|roster|display order|listed (?:together|alongside)|"
    r"(?:will|plan to) compare|(?:scheduled|planned) comparison)\b", re.I,
)


# Full statements only. Do not drop subject modifiers or trailing conditions.
_DEADLINE_PARAPHRASES = tuple(
    (event, re.compile(pattern))
    for event, pattern in (
        ("expiry", r"(.+?) expires on <date>"),
        ("expiry", r"(?:the )?(?:expiry|expiration) date (?:for|of) (.+?) is <date>"),
        ("expiry", r"(.+?)['\u2019]s (?:expiry|expiration) date is <date>"),
        ("renewal", r"(.+?) renewal is due (?:on|by) <date>"),
        ("renewal", r"(?:the )?renewal deadline (?:for|of) (.+?) is <date>"),
        ("submission", r"submit (.+?) by <date>"),
        ("submission", r"(.+?) must be submitted by <date>"),
        ("submission", r"(?:the )?submission deadline (?:for|of) (.+?) is <date>"),
    )
)
_DEADLINE_SUBJECT = re.compile(r"[\w]+(?:[ -][\w]+)*")


def deadline_claim_key(text: str, span: tuple[int, int]) -> tuple[str, ...]:
    """Normalize conservative deadline paraphrases; otherwise use literal wording."""
    start, end = span
    statement = " ".join((text[:start] + "<date>" + text[end:]).casefold().split())
    for event, pattern in _DEADLINE_PARAPHRASES:
        match = pattern.fullmatch(statement.removesuffix("."))
        if match:
            subject = match[1].removeprefix("the ")
            if _DEADLINE_SUBJECT.fullmatch(subject):
                return (event, subject)
    return (statement,)


def evidence_mode(query: str, topic_count: int, *, intent: str | None = None) -> str:
    """Infer the requested evidence shape, without rewriting the user's subject."""
    if intent is None:
        intent = detect_intent(query)
    if topic_count == 2 and intent == INTENT_COMPARISON:
        return "comparison"
    if topic_count and intent == INTENT_EXPLANATION and mechanism_subject(query):
        return "mechanism"
    if topic_count and _DATE_QUERY.search(query) and (_EXPLICIT_DUE.search(query)
            or any(cue.search(query) for cue, _, _ in _DATE_EVENTS)):
        return "deadline"
    return ""


def deadline_answers(query: str, text: str) -> bool:
    """Require the requested event, not another date in the same topic."""
    requested = [(source, needs_marker) for cue, source, needs_marker in _DATE_EVENTS if cue.search(query)]
    if not requested:
        return bool(_EXPLICIT_DUE.search(text))
    if len(requested) != 1:
        return False
    source, needs_marker = requested[0]
    if not source.search(text):
        return False
    if sum(bool(cue.search(text)) for _, cue, _ in _DATE_EVENTS) > 1:
        return False
    return not needs_marker or bool(_DEADLINE_MARKER.search(text))


def passage_evidence(mode: str, text: str, hits: int, total: int, words: int) -> int:
    """Grade explicit evidence above mentions; callers supply topic coverage."""
    if not hits or _METADATA.search(text):
        return 0
    if mode == "deadline":
        dates = list(date_mentions(text))
        return int(bool(dates and all(value is not None for _, value in dates) and (_DEADLINE_EVIDENCE.search(text)
                        or (_DEADLINE_MARKER.search(text)
                            and any(cue.search(text) for _, cue, _ in _DATE_EVENTS)))
                        and not _NEGATED_DEADLINE.search(text)))
    if words < 4:
        return 0
    if mode == "comparison":
        if _COMPARISON_MENTION.search(text):
            return 0
        if hits == total and _CONTRAST.search(text) and not _NO_CONTRAST.search(text):
            return 2
        return int(hits == 1 and bool(_ROLE.search(text)))
    if mode == "mechanism":
        return int(hits == total and bool(_MECHANISM.search(text)))
    return 0


__all__ = [
    "ALL_INTENTS", "BOOST_WEIGHTS", "DATE_BOOSTS", "DEFAULT_PENALTY_WEIGHT",
    "INTENT_BOOSTS", "INTENT_COMPARISON", "INTENT_EXPLANATION", "INTENT_FOUNDER",
    "INTENT_GENERAL", "INTENT_INVENTOR", "INTENT_PENALTIES", "INTENT_STATISTIC",
    "PENALTY_WEIGHTS", "SIGNAL_GENERIC", "SIGNAL_PERSON", "SIGNAL_WORK",
    "SIGNAL_YEAR", "boost_terms", "describe_intent", "detect_intent",
    "is_bare_generic_concept_title", "is_generic_concept_page",
    "looks_like_person_name", "name_candidates", "penalty_terms", "score_intent",
    "wants_date", "wants_person",
]
