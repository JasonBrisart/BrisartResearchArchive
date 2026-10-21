"""
File: v1/tests/test_json.py

Purpose
-------
Characterise v1/brisart_json.py: valid documents parse to the same values
as the json module, serialization round-trips, the embedded self-test
passes, and the known leniencies and failure modes that v2 removed are
pinned down.

Communication / relationships
-----------------------------
Standard library: unittest, json (reference only), plus support.py in
this folder.
Verifies: v1/brisart_json.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Generated values avoid NaN, non-string keys and lone surrogates, where
v1 is known to differ; those cases live in KnownDefectTests.

Known limitations
-----------------
v1 is recursive, so generated values stay shallow.

Examples
--------
::

    python -B -m unittest discover -s v1/tests -p test_json.py
"""

import json
import unittest

import support
import brisart_json
from brisart_json import BrisartJSONDecodeError, brisart_dumps, brisart_loads


def value(r, depth=0):
    if depth > 3 or r.random() < 0.4:
        return r.choice([None, True, False, 0, -7, 2 ** 70, 1.5, -0.25, 1e22, "", "a\u00e9\n\"\\", "x" * 20])
    if r.random() < 0.5:
        return [value(r, depth + 1) for _ in range(r.randint(0, 4))]
    return {r.choice(["a", "b", "\u00e9", ""]) + str(r.randint(0, 9)): value(r, depth + 1) for _ in range(r.randint(0, 4))}


class CorrectBehaviourTests(unittest.TestCase):
    def test_embedded_self_test(self):
        brisart_json._self_test()

    def test_valid_documents_match_json(self):
        r = support.rng("v1-json")
        for _ in range(support.scaled(800)):
            v = value(r)
            for kw in ({}, {"indent": 2}, {"sort_keys": True}):
                text = json.dumps(v, ensure_ascii=r.random() < 0.5, **kw)
                self.assertEqual(brisart_loads(text), json.loads(text))
                self.assertEqual(brisart_loads(brisart_dumps(v, **kw)), json.loads(json.dumps(v)))

    def test_serializer_matches_json_without_ascii_escaping(self):
        r = support.rng("v1-json-dump")
        for _ in range(support.scaled(300)):
            v = value(r)
            for kw in ({}, {"sort_keys": True}, {"indent": 2}):
                self.assertEqual(brisart_dumps(v, **kw), json.dumps(v, ensure_ascii=False, **kw))

    def test_malformed_documents_are_rejected(self):
        for text in ("", "[", "[1,]", '{"a"}', "{'a':1}", "[1 2]", '"\\x"', '"a\nb"', "tru", "[1]x"):
            with self.assertRaises(BrisartJSONDecodeError, msg=repr(text)):
                brisart_loads(text)


class KnownDefectTests(unittest.TestCase):
    def test_J1_J2_J3_lenient_numbers(self):
        self.assertEqual(brisart_loads("01"), 1)
        self.assertEqual(brisart_loads("1."), 1.0)
        self.assertEqual(brisart_loads("\u0661\u0662"), 12)

    def test_J4_lenient_unicode_escapes(self):
        for text in ('"\\u+123"', '"\\u 123"', '"\\u1_23"'):
            self.assertEqual(brisart_loads(text), "\u0123")

    def test_J5_lone_surrogate_escape_returned(self):
        self.assertEqual(brisart_loads('"\\ud800"'), "\ud800")

    def test_J6_nan_accepted_and_emitted(self):
        self.assertNotEqual(brisart_loads("NaN"), brisart_loads("NaN"))
        self.assertEqual(brisart_dumps(float("nan")), "NaN")

    def test_J7_duplicate_keys_keep_the_last(self):
        self.assertEqual(brisart_loads('{"a":1,"a":2}'), {"a": 2})

    def test_J8_overflow_becomes_infinity(self):
        self.assertEqual(brisart_loads("1e999"), float("inf"))

    def test_J9_J12_deep_nesting_and_cycles_recurse(self):
        with self.assertRaises(RecursionError):
            brisart_loads("[" * 3000 + "]" * 3000)
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(RecursionError):
            brisart_dumps(cycle)

    def test_J10_malformed_numbers_raise_bare_value_error(self):
        for text in ("1e", "\u00b2"):
            with self.assertRaises(ValueError) as caught:
                brisart_loads(text)
            self.assertIs(type(caught.exception), ValueError)

    def test_J11_non_string_keys_are_stringified(self):
        self.assertEqual(brisart_dumps({1: 2}), '{"1": 2}')
        self.assertEqual(brisart_dumps({(1, 2): 3}), '{"(1, 2)": 3}')


if __name__ == "__main__":
    unittest.main()
