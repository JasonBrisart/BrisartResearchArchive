"""
File: v2/tests/v1_probe.py

Purpose
-------
Reproduce, on demand, the v1 defects that v2 fixed. It loads the v1
modules from the sibling v1/ folder and the modules of a newer version
(v2 by default), runs one predicate per defect against each, and prints
which version shows it. test_v1_lineage.py runs the same checks as unit
tests, and v3/tests reuses this file so every later version is held to
the same list.

Communication / relationships
-----------------------------
Standard library: argparse, gc, importlib.util, inspect, sys, time,
types, zlib, pathlib.
Not collected by unittest (the name does not start with test_).
Imported by v2/tests/test_v1_lineage.py and v3/tests/test_v1_lineage.py.

Settings / parameters
---------------------
- --v1 DIR -- Folder holding the v1 modules (default: ../../v1).
- --target DIR -- Folder holding the newer modules (default: ../../v2).
- --skip-slow -- Skip the timing probe M8 (about ten seconds on v1).

Edge cases
----------
v1/brisart_robots.py imports brisart_ai.native.brisart_url at call time;
load_v1() installs a stand-in package pointing at v1/brisart_url.py so it
runs unmodified. A predicate that raises counts as "defect absent".

Known limitations
-----------------
Each predicate demonstrates one concrete input, not the full extent of a
defect. M8 compares wall-clock growth (best of two runs, garbage
collector paused) and can still be disturbed by a heavily loaded
machine; BRISART_SKIP_SLOW=1 skips it in the lineage tests.

Examples
--------
::

    python -B v2/tests/v1_probe.py
    python -B v2/tests/v1_probe.py --target v3
"""

import argparse
import gc
import importlib.util
import inspect
import sys
import time
import types
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAMES = ("codec", "hash", "inflate", "json", "markup", "robots", "url")


def _load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_v1(folder=None):
    folder = Path(folder or REPO / "v1")
    modules = {"url": _load_file("probe_v1_url", folder / "brisart_url.py")}
    if "brisart_ai.native.brisart_url" not in sys.modules:
        package = types.ModuleType("brisart_ai")
        native = types.ModuleType("brisart_ai.native")
        package.__path__ = []
        native.__path__ = []
        package.native = native
        native.brisart_url = modules["url"]
        sys.modules.update({"brisart_ai": package, "brisart_ai.native": native,
                            "brisart_ai.native.brisart_url": modules["url"]})
    for name in NAMES:
        if name not in modules:
            modules[name] = _load_file("probe_v1_" + name, folder / ("brisart_%s.py" % name))
    return types.SimpleNamespace(**modules)


def load_version(folder, label):
    folder = Path(folder)
    return types.SimpleNamespace(**{name: _load_file("probe_%s_%s" % (label, name), folder / ("brisart_%s.py" % name))
                                    for name in NAMES})


# ------------------------------------------------------------------ helpers
def over_subscribed_stream():
    """A dynamic block decoding to b"a" whose literal/length code is over-subscribed."""
    value, count = 0, 0

    def bits(v, n):
        nonlocal value, count
        value |= (v & ((1 << n) - 1)) << count
        count += n

    def code(c, n):
        for i in range(n - 1, -1, -1):
            bits((c >> i) & 1, 1)
    lengths = [0] * 258
    lengths[97] = lengths[256] = lengths[257] = 1
    bits(1, 1)
    bits(2, 2)
    bits(1, 5)
    bits(0, 5)
    bits(15, 4)
    for symbol in (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15):
        bits(4 if symbol < 16 else 0, 3)
    for length in lengths + [0]:
        code(length, 4)
    code(0, 1)
    code(1, 1)
    return value.to_bytes((count + 7) // 8, "little")


def events(markup, text, chunk=None):
    out = []

    class Parser(markup.BrisartMarkupParser):
        def handle_starttag(self, tag, attrs):
            out.append(("start", tag, tuple(attrs)))

        def handle_endtag(self, tag):
            out.append(("end", tag))

        def handle_data(self, data):
            out.append(("data", data))

    parser = Parser()
    if chunk is None:
        parser.feed(text)
    else:
        for i in range(0, len(text), chunk):
            parser.feed(text[i:i + chunk])
    parser.close()
    return out


def joined_data(markup, text, chunk=None):
    return "".join(e[1] for e in events(markup, text, chunk) if e[0] == "data")


def policy(m, text):
    p = m.robots.BrisartRobotsPolicy()
    p.parse(text.splitlines())
    return p


def accepts(function):
    try:
        function()
    except BaseException:
        return False
    return True


def raises(function, error_type, exact=False):
    try:
        function()
    except BaseException as error:
        return type(error) is error_type if exact else isinstance(error, error_type)
    return False


def returns(function, expected):
    try:
        return function() == expected
    except BaseException:
        return False


def grows_quadratically(m):
    """Four times the input costs about 4x for linear code and about 16x for quadratic code."""
    def run(k):
        doc = '<p class="a">hello <b>world</b></p>\n' * k
        best = None
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            for _ in range(2):
                started = time.perf_counter()
                events(m.markup, doc)
                elapsed = time.perf_counter() - started
                best = elapsed if best is None or elapsed < best else best
        finally:
            if was_enabled:
                gc.enable()
        return best
    run(500)
    return run(16000) / max(run(4000), 1e-4) > 7.0


# ------------------------------------------------------------------ the defects
def build_checks(slow=True):
    bomb = zlib.compress(bytes(3_000_000), 9)
    stored_bad_nlen = bytes([1]) + (5).to_bytes(2, "little") + (0).to_bytes(2, "little") + b"hello"
    dictionary = zlib.compressobj(6, zlib.DEFLATED, 15, 8, 0, zdict=b"dictionary")
    fdict = dictionary.compress(b"dictionary text") + dictionary.flush()
    cycle = []
    cycle.append(cycle)
    base = "http://a/b/c/d;p?q"
    checks = [
        ("C1", "Base64 'Z' (impossible length) decodes", lambda m: accepts(lambda: m.codec.brisart_b64decode("Z"))),
        ("C2", "Base64 'Zg=' (wrong padding) accepted", lambda m: accepts(lambda: m.codec.brisart_b64decode("Zg="))),
        ("C3", "Base64 '=Zg=' (padding first) decodes", lambda m: accepts(lambda: m.codec.brisart_b64decode("=Zg="))),
        ("C4", "non-canonical Base64 'Zh==' accepted", lambda m: accepts(lambda: m.codec.brisart_b64decode("Zh=="))),
        ("C5", "data after padding decodes", lambda m: accepts(lambda: m.codec.brisart_b64decode("Zm9vYg==Zm9v"))),
        ("C6", "outer whitespace silently stripped", lambda m: returns(lambda: m.codec.brisart_b64decode(" Zm9v "), b"foo")),
        ("H1", "stable_hash('\\ud800') == stable_hash('?')",
         lambda m: m.hash.brisart_stable_hash("\ud800") == m.hash.brisart_stable_hash("?")),
        ("H2", "sha256(None) accepted as empty input", lambda m: accepts(lambda: m.hash.brisart_sha256(None))),
        ("I1", "no output cap: 2.9 KB expands to 3 MB",
         lambda m: "max_output" not in inspect.signature(m.inflate.brisart_zlib_decompress).parameters
         and len(m.inflate.brisart_zlib_decompress(bomb)) == 3_000_000),
        ("I2", "stored block with a wrong NLEN accepted", lambda m: accepts(lambda: m.inflate.brisart_inflate(stored_bad_nlen))),
        ("I3", "over-subscribed Huffman code accepted",
         lambda m: returns(lambda: m.inflate.brisart_inflate(over_subscribed_stream()), b"a")),
        ("I4", "adler32(b'', 0xFFFF) not reduced", lambda m: m.inflate.brisart_adler32(b"", 0xFFFF) != zlib.adler32(b"", 0xFFFF)),
        ("I5", "preset-dictionary error is not a ValueError",
         lambda m: raises(lambda: m.inflate.brisart_zlib_decompress(fdict), NotImplementedError)
         and not raises(lambda: m.inflate.brisart_zlib_decompress(fdict), ValueError)),
        ("J1", "'01' parses as 1", lambda m: returns(lambda: m.json.brisart_loads("01"), 1)),
        ("J2", "'1.' parses as 1.0", lambda m: returns(lambda: m.json.brisart_loads("1."), 1.0)),
        ("J3", "non-ASCII digits parse", lambda m: returns(lambda: m.json.brisart_loads("\u0661\u0662"), 12)),
        ("J4", "\\u escapes accept '+', ' ' and '_'",
         lambda m: all(returns(lambda t=t: m.json.brisart_loads(t), "\u0123") for t in ('"\\u+123"', '"\\u 123"', '"\\u1_23"'))),
        ("J5", "unpaired surrogate escape returned", lambda m: returns(lambda: m.json.brisart_loads('"\\ud800"'), "\ud800")),
        ("J6", "NaN accepted and emitted",
         lambda m: accepts(lambda: m.json.brisart_loads("NaN")) and returns(lambda: m.json.brisart_dumps(float("nan")), "NaN")),
        ("J7", "duplicate keys keep the last value", lambda m: returns(lambda: m.json.brisart_loads('{"a":1,"a":2}'), {"a": 2})),
        ("J8", "'1e999' parses to infinity", lambda m: returns(lambda: m.json.brisart_loads("1e999"), float("inf"))),
        ("J9", "deep nesting raises RecursionError",
         lambda m: raises(lambda: m.json.brisart_loads("[" * 3000 + "]" * 3000), RecursionError)),
        ("J10", "malformed numbers raise a bare ValueError",
         lambda m: all(raises(lambda t=t: m.json.brisart_loads(t), ValueError, exact=True) for t in ("1e", "\u00b2"))),
        ("J11", "non-str keys stringified",
         lambda m: returns(lambda: m.json.brisart_dumps({1: 2}), '{"1": 2}')
         and returns(lambda: m.json.brisart_dumps({(1, 2): 3}), '{"(1, 2)": 3}')),
        ("J12", "self-referencing list raises RecursionError", lambda m: raises(lambda: m.json.brisart_dumps(cycle), RecursionError)),
        ("U1", "'java<TAB>script:x' has an empty scheme", lambda m: returns(lambda: m.url.brisart_urlsplit("java\tscript:x").scheme, "")),
        ("U2", "' javascript:x' has an empty scheme", lambda m: returns(lambda: m.url.brisart_urlsplit(" javascript:x").scheme, "")),
        ("U3", "Kelvin-sign host lower-cases to 'k.com'",
         lambda m: returns(lambda: m.url.brisart_urlsplit("http://\u212a.com/").hostname, "k.com")),
        ("U4", "non-ASCII letter accepted in a scheme", lambda m: returns(lambda: m.url.brisart_urlsplit("\u00e9x://a").scheme, "\u00e9x")),
        ("U5", "quote() maps a lone surrogate like '?'",
         lambda m: returns(lambda: m.url.brisart_quote("\ud800") == m.url.brisart_quote("?"), True)),
        ("U6", "urljoin drops the trailing slash for '.', '..', './g/.'",
         lambda m: [m.url.brisart_urljoin(base, r) for r in (".", "..", "./g/.")] == ["http://a/b/c", "http://a/b", "http://a/b/c/g"]),
        ("U7", "urlencode() of a dict raises", lambda m: raises(lambda: m.url.brisart_urlencode({"a": "b"}), Exception)),
        ("U8", "urlencode() encodes bytes as their repr",
         lambda m: returns(lambda: m.url.brisart_urlencode([("a", b"x y")]), "a=b%27x+y%27")),
        ("U9", "parse_qsl has no field limit", lambda m: len(m.url.brisart_parse_qsl("&".join("a=1" for _ in range(5000)))) == 5000),
        ("U10", "'http://good.com\\@evil.com/' resolves to a host",
         lambda m: returns(lambda: m.url.brisart_urlsplit("http://good.com\\@evil.com/").hostname, "evil.com")),
        ("M1", "'>' inside a quoted value ends the tag",
         lambda m: events(m.markup, '<a title="x>y">')[0] == ("start", "a", (("title", "x"),))),
        ("M2", "references decoded inside <script>", lambda m: ("data", "&") in events(m.markup, "<script>&amp;</script>")),
        ("M3", "a repeated attribute is reported twice", lambda m: len(events(m.markup, "<a href=1 href=2>")[0][2]) == 2),
        ("M4", "'</\u017fcript>' (long s) closes a script",
         lambda m: events(m.markup, "<script>x</\u017fcript>y</script>")[:3] == [("start", "script", ()), ("data", "x"), ("data", "y")]),
        ("M5", "a no-break space separates attributes",
         lambda m: events(m.markup, "<a\u00a0href=x>")[0] == ("start", "a", (("href", "x"),))),
        ("M6", "'java&Tab;script:' not decoded in an attribute",
         lambda m: events(m.markup, '<a href="java&Tab;script:x">')[0][2] == (("href", "java&Tab;script:x"),)),
        ("M7", "decoding depends on feed() boundaries",
         lambda m: joined_data(m.markup, "a &amp; b") != joined_data(m.markup, "a &amp; b", 5)),
        ("R1", "'Disallow: /*.pdf$' blocks nothing",
         lambda m: policy(m, "User-agent: *\nDisallow: /*.pdf$\n").can_fetch("x", "http://h/a.pdf")),
        ("R2", "first match beats a longer Allow",
         lambda m: not policy(m, "User-agent: *\nDisallow: /a\nAllow: /a/b\n").can_fetch("x", "http://h/a/b/c")),
        ("R3", "group 'bot' applies to Googlebot",
         lambda m: not policy(m, "User-agent: bot\nDisallow: /\n").can_fetch("Googlebot/2.1", "http://h/x")),
        ("R4", "a blank line discards a group's rules",
         lambda m: policy(m, "User-agent: *\n\nDisallow: /a\n").can_fetch("x", "http://h/a")),
        ("R5", "'%3F' acts as a query delimiter",
         lambda m: not policy(m, "User-agent: *\nDisallow: /a?b\n").can_fetch("x", "http://h/a%3Fb")),
        ("R6", "'/ad<TAB>min' slips past 'Disallow: /admin'",
         lambda m: policy(m, "User-agent: *\nDisallow: /admin\n").can_fetch("x", "/ad\tmin")),
    ]
    if slow:
        checks.append(("M8", "tokenizing time grows quadratically", grows_quadratically))
    return checks


def shows(predicate, modules):
    try:
        return bool(predicate(modules))
    except BaseException:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproduce the v1 defects and check a newer version for each.")
    parser.add_argument("--v1", default=str(REPO / "v1"))
    parser.add_argument("--target", default=str(REPO / "v2"))
    parser.add_argument("--skip-slow", action="store_true")
    options = parser.parse_args(argv)
    v1 = load_v1(options.v1)
    target = load_version(options.target, "target")
    failures = 0
    label = Path(options.target).name
    print("%-4s %-6s %-6s %s" % ("id", "v1", label, "defect"))
    checks = build_checks(not options.skip_slow)
    for ident, claim, predicate in checks:
        before, after = shows(predicate, v1), shows(predicate, target)
        failures += (not before) + after
        print("%-4s %-6s %-6s %s" % (ident, "SHOWS" if before else "-", "SHOWS" if after else "-", claim))
    print("\n%d defects: each must show on v1 and not on %s; %d do not." % (len(checks), label, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
