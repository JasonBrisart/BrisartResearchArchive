"""
File: brisart_native/brisart_robots.py

Purpose
-------
BrisartRobotsPolicy -- a pure-Python robots.txt interpreter implementing
the Robots Exclusion Protocol as standardised in RFC 9309, replacing
urllib.robotparser.RobotFileParser in Brisart Research Archive tooling.

Public interface:
- BrisartRobotsPolicy(max_bytes=DEFAULT_MAX_BYTES,
  max_rules=DEFAULT_MAX_RULES) -- Construct an empty policy (allows
  everything until parse() is called).
- BrisartRobotsPolicy.parse(source) -- Parse a robots.txt given as str,
  bytes, or an iterable of lines.
- BrisartRobotsPolicy.can_fetch(user_agent, url) -- True when the
  crawler may fetch the URL.
- BrisartRobotsPolicy.crawl_delay(user_agent) -- Seconds, or None.
- BrisartRobotsPolicy.for_status(status_code, text=None, **options) --
  Build the policy RFC 9309 prescribes for an HTTP response status.
- BrisartRobotsPolicy.truncated / rule_count / mode -- Inspection.
- DEFAULT_MAX_BYTES, DEFAULT_MAX_RULES, MAX_LINE_LENGTH,
  MAX_PATH_LENGTH, MAX_CRAWL_DELAY.

Design notes:

The standard library parser implements the original 1994 draft: the
first matching rule in file order wins, a rule is a literal prefix, and
a user-agent group matches by substring. RFC 9309 and every major crawler
work differently, so following the standard library here would make a
crawler fetch things a site has asked it not to. For example
"Disallow: /*.pdf$" blocks nothing under urllib.robotparser. This module
follows RFC 9309 instead:

1. Longest match wins. Every Allow and Disallow rule that matches the
   target is considered and the rule with the longest pattern is used;
   when an Allow and a Disallow tie, Allow wins. No match means allowed.
2. "*" matches any run of characters and a trailing "$" anchors the end
   of the path. A pattern is otherwise a case-sensitive prefix.
3. A group is one or more consecutive User-agent lines followed by
   rules. Blank lines and comments never split a group. Groups naming the
   same agent are merged. The crawler's product token (the leading
   letters, "_" and "-" of its user-agent string) is compared with the
   group agents for exact equality, ignoring case; only when no group
   names it does the "*" group apply.
4. Paths are normalised before comparing: percent-escapes of unreserved
   characters are decoded, other escapes are upper-cased, characters
   that must be encoded (non-ASCII, spaces, controls) are percent-
   encoded as UTF-8, and an encoded reserved character such as %2F stays
   distinct from "/". Control characters, tabs and newlines in a URL are
   dropped first, so "/ad\\tmin" cannot slip past "Disallow: /admin".
5. Everything is bounded: input is truncated at max_bytes, lines longer
   than MAX_LINE_LENGTH are ignored, at most max_rules rules are kept,
   and a URL whose path and query exceed MAX_PATH_LENGTH is refused. The
   wildcard matcher uses sequential substring searches, never regular
   expressions, so it never backtracks: matching costs a bounded number
   of scans over the path (growth is checked to be linear in
   tests/test_robots.py) and cannot be driven into catastrophic
   backtracking.
6. for_status implements the failure rules of RFC 9309 section 2.3.1:
   a 4xx response means "no robots.txt" (everything allowed) but a 5xx or
   an unusable status means "assume everything is disallowed".

Communication / relationships
-----------------------------
Standard library: none. This file imports nothing, so it can be copied
into any tool on its own. It does not depend on the other brisart_native
modules; it carries its own small path normaliser instead of importing
brisart_url.py. Behaviour is cross-checked against RFC 9309 and the
widely documented Google path-matching examples, and against
urllib.robotparser on inputs where the two algorithms must agree, by
brisart_native/tests/test_robots.py (tests may import the standard
library; this module may not).

Settings / parameters
---------------------
- DEFAULT_MAX_BYTES -- 524288 (512 KiB). RFC 9309 requires parsing at
  least 500 KiB. Anything beyond is ignored and `truncated` is set.
- DEFAULT_MAX_RULES -- 10000 Allow/Disallow rules kept across the file;
  later rules are ignored and `truncated` is set.
- MAX_LINE_LENGTH -- 8192 characters; a longer line is ignored whole.
- MAX_PATH_LENGTH -- 8192 characters of normalised path and query;
  can_fetch returns False for anything longer.
- MAX_CRAWL_DELAY -- 86400.0 seconds; larger Crawl-delay values are
  clamped to it.
- user_agent -- can_fetch/crawl_delay take either a bare product token
  ("BrisartAI") or a full header ("BrisartAI/1.0 (+https://example)").

Edge cases
----------
- An empty "Disallow:" and an empty "Allow:" match nothing.
- A pattern that does not start with "/" or "*" is treated as if it
  began with "/" (fail-closed for Disallow).
- Rules that appear before any User-agent line are ignored.
- A "User-agent" value is reduced to its leading product token, so
  "Googlebot/2.1" names "googlebot"; a value with no valid token is
  ignored.
- Directive names are case-insensitive; unknown directives (Sitemap,
  Host, misspellings) are ignored, not guessed at.
- A leading UTF-8 byte order mark is ignored; "\\n", "\\r\\n" and "\\r" all
  end a line, and no other character (such as U+2028 or form feed) does.
- Crawl-delay is not part of RFC 9309; it is read as a non-negative
  decimal number and anything else is ignored.
- An unparsed or empty policy allows everything.

Known limitations
-----------------
- Matching is against the URL path and query only; scheme, host and port
  are ignored, so use one policy per origin.
- Robots rules are advisory: nothing here enforces them against a
  determined or misconfigured client, and robots.txt is not an access
  control or security mechanism.
- Redirect handling, caching and fetching robots.txt are the caller's
  job; for_status only maps a final status to a policy.
- No Sitemap, Host or other non-standard directives are interpreted.
- Verified on CPython 3.12 only. Written to avoid features newer than
  Python 3.8 but not tested there.

Examples
--------
Run from the directory that contains the brisart_native folder.

::

    from brisart_native.brisart_robots import BrisartRobotsPolicy
    policy = BrisartRobotsPolicy()
    policy.parse("User-agent: *\\nDisallow: /private/\\nAllow: /private/ok.html\\n"
                 "Disallow: /*.pdf$\\n")
    assert policy.can_fetch("BrisartAI/1.0", "https://example.com/index.html")
    assert not policy.can_fetch("BrisartAI/1.0", "https://example.com/private/x")
    assert policy.can_fetch("BrisartAI/1.0", "https://example.com/private/ok.html")
    assert not policy.can_fetch("BrisartAI/1.0", "https://example.com/a/b.pdf")
    assert policy.can_fetch("BrisartAI/1.0", "https://example.com/a/b.pdf?x=1")
    assert not BrisartRobotsPolicy.for_status(503).can_fetch("BrisartAI", "/")
    assert BrisartRobotsPolicy.for_status(404).can_fetch("BrisartAI", "/")
"""

DEFAULT_MAX_BYTES = 512 * 1024
DEFAULT_MAX_RULES = 10000
MAX_LINE_LENGTH = 8192
MAX_PATH_LENGTH = 8192
MAX_CRAWL_DELAY = 86400.0

_C0_AND_SPACE = "".join(chr(i) for i in range(33))
_DROP_TAB_CR_LF = {9: None, 10: None, 13: None}
_ASCII_LOWER = {c: c + 32 for c in range(65, 91)}
_TOKEN_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-")
_SCHEME_FIRST = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
_SCHEME_REST = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-.")
_HEX = frozenset("0123456789ABCDEFabcdef")
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_RESERVED = frozenset(":/?#[]@!$&'()*+,;=")
_KEPT_RAW = _UNRESERVED | _RESERVED          # every other ASCII character is percent-encoded


def _token(user_agent):
    """Lower-cased product token: the leading run of letters, '_' and '-'."""
    text = user_agent.strip(" \t")
    end = 0
    while end < len(text) and text[end] in _TOKEN_CHARS:
        end += 1
    return text[:end].translate(_ASCII_LOWER)


def _normalize(text):
    """RFC 9309 section 2.2.2 normalisation of a path, pattern or target."""
    if text.isascii() and "%" not in text and not text.strip("".join(_KEPT_RAW)):
        return text
    out = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char == "%" and i + 2 < n and text[i + 1] in _HEX and text[i + 2] in _HEX:
            byte = int(text[i + 1:i + 3], 16)
            out.append(chr(byte) if chr(byte) in _UNRESERVED else "%%%02X" % byte)
            i += 3
        elif char < "\x80":
            out.append(char if char in _KEPT_RAW else "%%%02X" % ord(char))
            i += 1
        else:
            out.append("".join("%%%02X" % b for b in char.encode("utf-8", "surrogatepass")))
            i += 1
    return "".join(out)


def _target(url):
    """Path plus query of a URL (or bare path), normalised; None if it is too long."""
    text = url.strip(_C0_AND_SPACE).translate(_DROP_TAB_CR_LF)
    hash_at = text.find("#")
    if hash_at != -1:
        text = text[:hash_at]
    colon = text.find(":")
    if colon > 0 and text[0] in _SCHEME_FIRST and _SCHEME_REST.issuperset(text[:colon]):
        text = text[colon + 1:]
    if text.startswith("//"):
        end = len(text)
        for mark in ("/", "?"):
            found = text.find(mark, 2)
            if found != -1 and found < end:
                end = found
        text = text[end:]
    if not text or text[0] == "?":
        text = "/" + text
    elif text[0] != "/":
        text = "/" + text
    if len(text) > MAX_PATH_LENGTH * 3:
        return None
    text = _normalize(text)
    return None if len(text) > MAX_PATH_LENGTH else text


class _Rule:
    __slots__ = ("allow", "length", "segments", "anchored")

    def __init__(self, allow, pattern):
        self.allow = allow
        self.length = len(pattern)
        self.anchored = pattern.endswith("$")
        body = pattern[:-1] if self.anchored else pattern
        self.segments = body.split("*")

    def matches(self, target):
        segments = self.segments
        first = segments[0]
        if len(segments) == 1:
            return target == first if self.anchored else target.startswith(first)
        if not target.startswith(first):
            return False
        position = len(first)
        for middle in segments[1:-1]:
            found = target.find(middle, position)
            if found == -1:
                return False
            position = found + len(middle)
        last = segments[-1]
        if self.anchored:
            return len(target) - len(last) >= position and target.endswith(last)
        return target.find(last, position) != -1


class _Group:
    __slots__ = ("agents", "rules", "delay")

    def __init__(self):
        self.agents = []
        self.rules = []
        self.delay = None


class BrisartRobotsPolicy:
    """A parsed robots.txt that answers can_fetch() and crawl_delay() per RFC 9309."""

    def __init__(self, max_bytes=DEFAULT_MAX_BYTES, max_rules=DEFAULT_MAX_RULES):
        for name, value in (("max_bytes", max_bytes), ("max_rules", max_rules)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("%s must be a non-negative integer" % name)
        self._max_bytes = max_bytes
        self._max_rules = max_rules
        self._groups = []
        self._cache = {}
        self.mode = "rules"            # "rules", "allow_all" or "disallow_all"
        self.truncated = False
        self.rule_count = 0

    # ------------------------------------------------------------------ construction
    @classmethod
    def for_status(cls, status_code, text=None, **options):
        """Policy for a robots.txt fetch that ended with this HTTP status (RFC 9309 section 2.3.1)."""
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            raise TypeError("status_code must be an int")
        policy = cls(**options)
        if 200 <= status_code < 300:
            if text is not None:
                policy.parse(text)
        elif status_code == 429 or not (300 <= status_code < 500):
            policy.mode = "disallow_all"          # server error, rate limited, or not a usable HTTP status
        else:
            policy.mode = "allow_all"             # redirects not resolved and 4xx: the file is unavailable
        return policy

    def parse(self, source):
        """Replace the policy's rules with those parsed from str, bytes or an iterable of lines."""
        self._groups = []
        self._cache = {}
        self.mode = "rules"
        self.truncated = False
        self.rule_count = 0
        if isinstance(source, (bytes, bytearray, memoryview)):
            raw = bytes(source)
            if len(raw) > self._max_bytes:
                raw = raw[:self._max_bytes]
                self.truncated = True
            source = raw.decode("utf-8", "replace")
        if isinstance(source, str):
            if len(source) > self._max_bytes:
                source = source[:self._max_bytes]
                self.truncated = True
            lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        else:
            lines = self._bounded(source)
        if lines and lines[0].startswith("\ufeff"):
            lines[0] = lines[0][1:]
        group = None
        last_was_agent = False
        for line in lines:
            if len(line) > MAX_LINE_LENGTH:
                continue
            hash_at = line.find("#")
            if hash_at != -1:
                line = line[:hash_at]
            line = line.strip(" \t")
            if not line:
                continue
            key, colon, value = line.partition(":")
            if not colon:
                continue
            key = key.strip(" \t").translate(_ASCII_LOWER)
            value = value.strip(" \t")
            if key == "user-agent":
                agent = "*" if value == "*" else _token(value)
                if not agent:
                    continue
                if group is None or not last_was_agent:
                    group = _Group()
                    self._groups.append(group)
                group.agents.append(agent)
                last_was_agent = True
            elif key in ("allow", "disallow"):
                last_was_agent = False
                if group is None or not value:
                    continue
                if self.rule_count >= self._max_rules:
                    self.truncated = True
                    continue
                if value[0] not in "/*":
                    value = "/" + value
                group.rules.append(_Rule(key == "allow", _normalize(value)))
                self.rule_count += 1
            elif key == "crawl-delay":
                last_was_agent = False
                delay = self._number(value)
                if group is not None and delay is not None and group.delay is None:
                    group.delay = delay

    def _bounded(self, source):
        if isinstance(source, (int, float)) or source is None:
            raise TypeError("robots.txt source must be str, bytes or an iterable of lines")
        lines = []
        budget = self._max_bytes
        for item in source:
            if isinstance(item, (bytes, bytearray)):
                item = bytes(item).decode("utf-8", "replace")
            if not isinstance(item, str):
                raise TypeError("robots.txt lines must be str or bytes")
            item = item.rstrip("\r\n")
            budget -= len(item) + 1
            if budget < 0:
                self.truncated = True
                break
            lines.append(item)
        return lines

    @staticmethod
    def _number(value):
        if not value or not value.isascii():
            return None
        whole, dot, fraction = value.partition(".")
        if not whole.isdigit() or (dot and (not fraction.isdigit())):
            return None
        number = float(value)
        return MAX_CRAWL_DELAY if number > MAX_CRAWL_DELAY else number

    # ------------------------------------------------------------------ queries
    def _applicable(self, user_agent):
        token = _token(user_agent)
        cached = self._cache.get(token)
        if cached is None:
            named = [g for g in self._groups if token and token in g.agents]
            if not named:
                named = [g for g in self._groups if "*" in g.agents]
            rules = [rule for g in named for rule in g.rules]
            delay = next((g.delay for g in named if g.delay is not None), None)
            cached = (rules, delay)
            if len(self._cache) >= 64:
                self._cache.clear()
            self._cache[token] = cached
        return cached

    def can_fetch(self, user_agent, url):
        """True when `user_agent` may fetch `url` under this policy."""
        if not isinstance(user_agent, str) or not isinstance(url, str):
            raise TypeError("user_agent and url must be str")
        if self.mode == "disallow_all":
            return False
        if self.mode == "allow_all":
            return True
        target = _target(url)
        if target is None:
            return False                       # an absurdly long path is never fetched
        best_length = -1
        best_allow = True
        for rule in self._applicable(user_agent)[0]:
            if rule.length < best_length or (rule.length == best_length and best_allow):
                continue
            if rule.matches(target):
                best_length, best_allow = rule.length, rule.allow
        return best_allow

    def crawl_delay(self, user_agent):
        """Crawl-delay in seconds for this crawler, or None."""
        if not isinstance(user_agent, str):
            raise TypeError("user_agent must be str")
        if self.mode != "rules":
            return None
        return self._applicable(user_agent)[1]


__all__ = [
    "BrisartRobotsPolicy",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_RULES",
    "MAX_CRAWL_DELAY",
    "MAX_LINE_LENGTH",
    "MAX_PATH_LENGTH",
]
