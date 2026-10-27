"""
File: v3/tests/v2_probe.py

Purpose
-------
Reproduce, on demand, every "v2 did X" statement in v3/CHANGELOG.md. It loads the v2 modules from the sibling v2/ folder and the v3
modules from v3/, runs one predicate per claim against each, and prints
which version shows the behaviour. A claim that cannot be reproduced
here does not belong in the changelog.

Communication / relationships
-----------------------------
Standard library: argparse, importlib.util, sys, pathlib.
Not collected by unittest (the name does not start with test_);
test_standards.py checks that every probe ID appears in v3/CHANGELOG.md.

Settings / parameters
---------------------
- --v2 DIR -- Folder holding the v2 modules (default: ../../v2 relative
  to this file).

Edge cases
----------
A predicate that raises counts as "behaviour absent".

Known limitations
-----------------
Each predicate demonstrates one concrete input, not the full extent of
a behaviour. The inflate change (the output cap is checked before a
literal byte is written rather than just after) is not externally
observable and therefore has no probe.

Examples
--------
::

    python -B v3/tests/v2_probe.py
"""

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
V3 = HERE.parents[1]
NAMES = ("codec", "hash", "inflate", "json", "robots", "url")


def load(folder, prefix, names):
    modules = {}
    for name in names:
        path = Path(folder) / ("brisart_%s.py" % name)
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location(prefix + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules


def accepts(function):
    try:
        function()
    except BaseException:
        return False
    return True


def error_text(function):
    try:
        function()
    except BaseException as error:
        return str(error)
    return ""


def robots_rules(module, source, budget):
    policy = module.BrisartRobotsPolicy(max_bytes=budget)
    policy.parse(source)
    return policy


def build_checks():
    euro = "user-agent: *\n" + "disallow: /\u20ac\u20ac\u20ac\n" * 100       # 14 + 21 bytes per rule line
    cut = "user-agent: *\ndisallow: /\nallow: /public/reports/only\n"
    return [
        ("V1", "json: oversized bytes input was decoded before the max_length check",
         lambda m: "UTF-8" in error_text(lambda: m["json"].brisart_loads(b"[" + b"1," * 600 + b"\xff", max_length=100))),
        ("V2", "robots: the max_bytes budget counted characters, not UTF-8 bytes, for str input",
         lambda m: robots_rules(m["robots"], euro, 14 + 21 * 10).rule_count > 11),
        ("V3", "robots: a line cut by the budget was parsed as a shorter, broader rule",
         lambda m: robots_rules(m["robots"], cut, len(cut) - 15).can_fetch("x", "/public/x")),
        ("V4", "url: BrisartSplitResult attributes could be reassigned while the object was hashable",
         lambda m: accepts(lambda: setattr(m["url"].brisart_urlsplit("http://a/b"), "path", "/c"))),
        ("V5", "url: BrisartSplitResult accepted non-str components",
         lambda m: accepts(lambda: m["url"].BrisartSplitResult("http", "a", 5, "", ""))),
        ("A1", "codec: no Base32, Base32hex or Base16",
         lambda m: not hasattr(m["codec"], "brisart_b32encode")),
        ("A2", "hash: no SHA-224, HMAC or digest comparison",
         lambda m: not hasattr(m["hash"], "brisart_hmac")),
        ("A3", "inflate: no CRC-32 or gzip decoding",
         lambda m: not hasattr(m["inflate"], "brisart_gzip_decompress")),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproduce the v2 behaviours cited in the v3.0.0 changelog.")
    parser.add_argument("--v2", default=str(V3.parent / "v2"))
    options = parser.parse_args(argv)
    v2 = load(options.v2, "v2_", NAMES)
    v3 = load(V3, "v3_", NAMES)
    failures = 0
    print("%-3s %-7s %-7s %s" % ("id", "v2", "v3", "claim"))
    for ident, claim, predicate in build_checks():
        try:
            before = bool(predicate(v2))
        except BaseException:
            before = False
        try:
            after = bool(predicate(v3))
        except BaseException:
            after = False
        failures += (not before) + after
        print("%-3s %-7s %-7s %s" % (ident, "SHOWS" if before else "-", "SHOWS" if after else "-", claim))
    print("\n%d claims: every claim must show on v2 and not on v3; %d do not." % (len(build_checks()), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
