"""
File: v3/tests/test_json.py

Purpose
-------
Verify v3/brisart_json.py against RFC 8259 accept and reject corpora,
against the json module on mutated documents (with its documented
leniencies switched to match), by serializer equivalence and round
trips, and against hostile input: depth bombs, huge numbers, duplicate
keys, lone surrogates, escape tricks, cycles and size limits, including
the v3 check that oversized bytes input is refused before decoding.

Communication / relationships
-----------------------------
Standard library: unittest, json, sys (reference only), plus support.py
in this folder.
Verifies: v3/brisart_json.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Mutations insert, replace and delete characters chosen to hit every
grammar edge (quotes, backslashes, signs, exponents, non-ASCII digits,
NUL, vertical tab, byte order mark, surrogate escapes).

Known limitations
-----------------
Agreement with json is checked on generated input, not proven.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_json.py
"""

import json
import sys
import unittest

import support
from brisart_json import BrisartJSONDecodeError, brisart_dumps, brisart_loads


def same(a, b, ordered=True):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if (list(a) != list(b)) if ordered else (set(a) != set(b)):
            return False
        return all(same(a[k], b[k], ordered) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y, ordered) for x, y in zip(a, b))
    if isinstance(a, float):
        return repr(a) == repr(b)
    return a == b


def reject_constant(name):
    raise ValueError(name)


def has_inf(value):
    if isinstance(value, float):
        return value in (float("inf"), float("-inf"))
    if isinstance(value, list):
        return any(has_inf(v) for v in value)
    if isinstance(value, dict):
        return any(has_inf(v) for v in value.values())
    return False


ACCEPT = ["[]", "{}", "[1,2,3]", '{"a":{"b":[]}}', "[1e1]", "[1E+2]", "[-0]", "[-0.0]", "[1e-400]", "0", "-1",
          '"\\u0060\\u012a\\u12AB"', '["\\uD801\\udc37"]', '"\\"\\\\\\/\\b\\f\\n\\r\\t"', '"\\u0000"', "null",
          ' \t\n\r[ 1 , 2 ] \t\n\r', "[" * 99 + "]" * 99, "1" * 4300]
REJECT = ["", " ", "[", "[1,]", "[,1]", '{"a":1,}', "{'a':1}", "[01]", "[-01]", "[1.]", "[.5]", "[+1]", "[1e]",
          "[0x10]", "[NaN]", "[Infinity]", '["\\x"]', '["\\u12"]', '["\\u+123"]', '["\\u 123"]', '["\\u1_23"]',
          '["a\nb"]', '["a\x00b"]', "[tru]", "[1]x", "\ufeff[]", "[\u0663]", "[1\u00b2]", '["\\ud800"]',
          '["\ud800"]', "[1e999]", "1" * 4301, "[" * 101 + "]" * 101, '{"a":1,"a":2}', "/*c*/1", "[1]\x0b"]


class CorpusTests(unittest.TestCase):
    def test_accept(self):
        for text in ACCEPT:
            brisart_loads(text)

    def test_reject(self):
        for text in REJECT:
            with self.assertRaises(BrisartJSONDecodeError, msg=ascii(text[:40])):
                brisart_loads(text)

    def test_values_match_json(self):
        for text in ACCEPT:
            if "1e-400" in text:
                continue
            self.assertTrue(same(brisart_loads(text), json.loads(text)), text[:40])

    def test_error_position(self):
        with self.assertRaises(BrisartJSONDecodeError) as caught:
            brisart_loads('{\n  "a": 1,\n  "b": ?\n}')
        self.assertEqual((caught.exception.lineno, caught.exception.colno, caught.exception.msg), (3, 8, "Expecting value"))


class DifferentialTests(unittest.TestCase):
    def value(self, r, depth=0):
        if depth > 4 or r.random() < 0.4:
            return r.choice([None, True, False, 0, -1, 2 ** 70, 1.5, -0.0, 1e22, 1e-7, "", "a\u00e9\U0001f600 \n\"\\/",
                             5e-324, 1.7976931348623157e308])
        if r.random() < 0.5:
            return [self.value(r, depth + 1) for _ in range(r.randint(0, 4))]
        return {r.choice(["a", "b", "\u00e9", "", "k\n"]) + str(r.randint(0, 3)): self.value(r, depth + 1)
                for _ in range(r.randint(0, 4))}

    ALPHABET = list('{}[],:"\\ -+.eE0123456789tfnul\n\t\x00\x0b\u00a0\u0663\ufeffu/IN') + ["true", "1e5", "\\u00e9", "\\ud800"]

    def test_mutated_documents_get_jsons_verdict(self):
        r = support.rng("json-diff")
        accepted = 0
        for _ in range(support.scaled(10000)):
            doc = json.dumps(self.value(r), ensure_ascii=r.random() < 0.5, indent=r.choice([None, 1]))
            for _ in range(r.randint(0, 3)):
                if not doc:
                    break
                i = r.randrange(len(doc) + 1)
                piece = r.choice(self.ALPHABET)
                mode = r.random()
                doc = doc[:i] + piece + doc[i:] if mode < 0.4 else (doc[:i] + piece + doc[i + 1:] if mode < 0.7 else doc[:i] + doc[i + 1:])
            try:
                theirs = ("ok", json.loads(doc, parse_constant=reject_constant))
                if has_inf(theirs[1]):
                    theirs = ("err", None)
            except (ValueError, RecursionError):
                theirs = ("err", None)
            try:
                ours = ("ok", brisart_loads(doc, duplicate_keys="last", allow_lone_surrogates=True, max_depth=10000))
            except BrisartJSONDecodeError:
                ours = ("err", None)
            self.assertEqual(ours[0], theirs[0], ascii(doc))
            if ours[0] == "ok":
                accepted += 1
                self.assertTrue(same(ours[1], theirs[1]), ascii(doc))
        self.assertGreater(accepted, 0)

    def test_serializer_matches_json(self):
        r = support.rng("json-dump")
        for _ in range(300):
            value = self.value(r)
            for kw in ({}, {"indent": 2}, {"sort_keys": True}, {"ensure_ascii": True}, {"separators": (",", ":")}):
                reference = dict(kw)
                reference.setdefault("ensure_ascii", False)        # the defaults differ: documented in the module
                self.assertEqual(brisart_dumps(value, **kw), json.dumps(value, **reference))
                self.assertTrue(same(brisart_loads(brisart_dumps(value, **kw), duplicate_keys="last"), value,
                                     ordered=not kw.get("sort_keys")))


class SecurityTests(unittest.TestCase):
    def test_depth_bombs_never_recurse(self):
        limit = sys.getrecursionlimit()
        for text in ("[" * 500000, '{"a":' * 200000, "[" * 500000 + "]" * 500000):
            with self.assertRaises(BrisartJSONDecodeError) as caught:
                brisart_loads(text)
            self.assertIn("nesting depth", str(caught.exception))
        self.assertEqual(sys.getrecursionlimit(), limit)
        deep = []
        cursor = deep
        for _ in range(20000):
            cursor.append([])
            cursor = cursor[0]
        self.assertEqual(brisart_dumps(deep, max_depth=20005), "[" * 20001 + "]" * 20001)
        with self.assertRaises(ValueError):
            brisart_dumps(deep)

    def test_policies(self):
        self.assertEqual(brisart_loads('{"a":1,"a":2}', duplicate_keys="last"), {"a": 2})
        self.assertEqual(brisart_loads('{"a":1,"a":2}', duplicate_keys="first"), {"a": 1})
        self.assertEqual(brisart_loads('"\\ud800"', allow_lone_surrogates=True), "\ud800")
        self.assertTrue(brisart_loads("NaN", allow_nan=True) != brisart_loads("NaN", allow_nan=True))
        for value in (float("nan"), {1: 2}, {(1, 2): 3}, object(), "\ud800"):
            with self.assertRaises((ValueError, TypeError)):
                brisart_dumps(value)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(ValueError):
            brisart_dumps(cycle)

    def test_length_limit_for_str_and_bytes(self):
        doc = "[" + "1," * 50 + "1]"
        brisart_loads(doc, max_length=len(doc))
        with self.assertRaises(BrisartJSONDecodeError):
            brisart_loads(doc, max_length=len(doc) - 1)
        brisart_loads(doc.encode(), max_length=len(doc))

    def test_oversized_bytes_are_refused_before_decoding(self):
        # Invalid UTF-8 at the very end: decoding would report it; the size check must come first.
        blob = b"[" + b"1," * 600 + b"\xff"
        with self.assertRaises(BrisartJSONDecodeError) as caught:
            brisart_loads(blob, max_length=100)
        self.assertIn("exceeds max_length", str(caught.exception))
        with self.assertRaises(BrisartJSONDecodeError) as caught:
            brisart_loads(blob, max_length=1000)
        self.assertIn("UTF-8", str(caught.exception))
        multibyte = ("[" + '"\u20ac",' * 30 + "1]").encode()            # 3 bytes per euro sign
        self.assertEqual(len(brisart_loads(multibyte, max_length=len(multibyte.decode()))), 31)


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: "[" + ",".join(["1"] * (30_000 * k)) + "]", brisart_loads)
        support.assert_roughly_linear(self, lambda k: '"' + "\\n" * (40_000 * k) + '"', brisart_loads)
        support.assert_roughly_linear(self, lambda k: "{" + ",".join('"k%d":%d' % (i, i) for i in range(15_000 * k)) + "}",
                                      brisart_loads)
        support.assert_roughly_linear(self, lambda k: list(range(30_000 * k)), brisart_dumps)


if __name__ == "__main__":
    unittest.main()
