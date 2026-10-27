"""
File: v1/tests/test_csv.py

Purpose
-------
Verify v1/brisart_csv.py: reading agrees with csv.reader(strict=True) on
everything csv.writer produces and on randomly generated text (with
strict_quotes=False); writing matches csv.writer byte for byte;
documented strictness (bare quotes, text after a closing quote,
unterminated fields), error positions, limits, value types, formula
escaping, and linear time.

Communication / relationships
-----------------------------
Standard library: unittest, csv, io (reference only), plus support.py in
this folder.
Verifies: v1/brisart_csv.py.

Settings / parameters
---------------------
Fuzz volume follows BRISART_FUZZ_SCALE and BRISART_SEED.

Edge cases
----------
Fields containing delimiters, quotes, CR, LF and CRLF; empty fields,
empty rows and lone empty fields; documents with no line break, no
delimiter or no quote at all.

Known limitations
-----------------
Only the comma/double-quote dialect and a few alternative single-
character delimiters are compared with the csv module.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_csv.py
"""

import csv
import io
import unittest

import support
from brisart_csv import BrisartCSVError, brisart_csv_dumps, brisart_csv_loads, brisart_csv_reader

POOL = ["a", "b", "", " x ", "\u00e9", "1,2", 'q"z', "l\nm", "\r", "c\r\nd", "\x00", "\t"]


def reference(text, **kw):
    try:
        return list(csv.reader(io.StringIO(text, newline=""), strict=True, **kw))
    except csv.Error:
        return "ERR"


def ours(text, **kw):
    try:
        return brisart_csv_loads(text, **kw)
    except BrisartCSVError:
        return "ERR"


class DifferentialTests(unittest.TestCase):
    def test_reads_and_writes_exactly_like_csv(self):
        r = support.rng("csv-diff")
        for _ in range(support.scaled(5000)):
            rows = [[r.choice(POOL) for _ in range(r.randint(0, 4))] for _ in range(r.randint(0, 4))]
            for terminator in ("\r\n", "\n"):
                buffer = io.StringIO()
                csv.writer(buffer, lineterminator=terminator).writerows(rows)
                text = buffer.getvalue()
                self.assertEqual(brisart_csv_dumps(rows, lineterminator=terminator), text, rows)
                self.assertEqual(ours(text), reference(text), repr(text))

    def test_random_text_gets_csvs_verdict_when_bare_quotes_are_allowed(self):
        r = support.rng("csv-fuzz")
        for _ in range(support.scaled(10000)):
            text = "".join(r.choice(',"\r\nab ;') for _ in range(r.randint(0, 14)))
            self.assertEqual(ours(text, strict_quotes=False), reference(text), repr(text))
            self.assertEqual(ours(text, delimiter=";", strict_quotes=False), reference(text, delimiter=";"), repr(text))

    def test_other_writer_options_match_csv(self):
        rows = [["a", "b c", 'q"'], ["", "x"], [1, 2.5, None, True]]
        buffer = io.StringIO()
        csv.writer(buffer, quoting=csv.QUOTE_ALL, delimiter=";", lineterminator="\n").writerows(rows)
        self.assertEqual(brisart_csv_dumps(rows, quote_all=True, delimiter=";", lineterminator="\n"), buffer.getvalue())


class StrictnessTests(unittest.TestCase):
    def test_documented_rejections(self):
        for text, where in (('a,b"c,d', (1, 4)), ('"a"b,c', (1, 4)), ('x\n"abc', (2, 1)), ('a\r\n"b"x', (2, 4))):
            with self.assertRaises(BrisartCSVError) as caught:
                brisart_csv_loads(text)
            self.assertEqual((caught.exception.line, caught.exception.column), where, text)
        self.assertEqual(reference('a,b"c,d'), [["a", 'b"c', "d"]])          # the leniency strict_quotes avoids
        self.assertEqual(brisart_csv_loads('a,b"c,d', strict_quotes=False), [["a", 'b"c', "d"]])

    def test_shapes(self):
        self.assertEqual(brisart_csv_loads(""), [])
        self.assertEqual(brisart_csv_loads("\n"), [[]])
        self.assertEqual(brisart_csv_loads("a,"), [["a", ""]])
        self.assertEqual(brisart_csv_loads('"a\r\nb",c\rd'), [["a\r\nb", "c"], ["d"]])
        self.assertEqual(brisart_csv_dumps([[""]]), '""\r\n')
        self.assertEqual(brisart_csv_dumps([[]]), "\r\n")

    def test_limits(self):
        with self.assertRaises(BrisartCSVError):
            brisart_csv_loads("x" * 200_000)
        self.assertEqual(len(brisart_csv_loads("x" * 200_000, max_field_size=None)[0][0]), 200_000)
        with self.assertRaises(BrisartCSVError):
            brisart_csv_loads("a\nb\nc", max_rows=2)
        self.assertEqual(len(brisart_csv_loads("a\nb", max_rows=2)), 2)
        reader = brisart_csv_reader("a\nb\nc", max_rows=2)
        self.assertEqual(next(reader), ["a"])

    def test_argument_and_value_validation(self):
        for kw in ({"delimiter": ",,"}, {"delimiter": "\n"}, {"delimiter": '"'}, {"quotechar": ""}):
            with self.assertRaises((TypeError, ValueError)):
                brisart_csv_loads("a", **kw)
        with self.assertRaises(TypeError):
            brisart_csv_loads(b"a,b")
        for bad in ([object()], [b"x"], [[1, 2]], "ab"):
            with self.assertRaises(TypeError):
                brisart_csv_dumps([bad] if bad != "ab" else ["ab"])
        with self.assertRaises(ValueError):
            brisart_csv_dumps([["a"]], lineterminator="\r\r")

    def test_formula_escaping(self):
        rows = [["=1+1", "+x", "-x", "@x", "\tx", "\rx", "ok", "a=b"]]
        self.assertEqual(brisart_csv_loads(brisart_csv_dumps(rows, escape_formulas=True)),
                         [["'=1+1", "'+x", "'-x", "'@x", "'\tx", "'\rx", "ok", "a=b"]])
        self.assertEqual(brisart_csv_loads(brisart_csv_dumps(rows)), rows)


class ResourceTests(unittest.TestCase):
    def test_linear_time(self):
        support.assert_roughly_linear(self, lambda k: "a,b,c\r\n" * (30_000 * k), brisart_csv_loads)
        support.assert_roughly_linear(self, lambda k: "abcdefgh\n" * (30_000 * k), brisart_csv_loads)
        support.assert_roughly_linear(self, lambda k: "a," * (50_000 * k), brisart_csv_loads)
        support.assert_roughly_linear(self, lambda k: '"' + 'x""' * (30_000 * k) + '"', lambda t: brisart_csv_loads(t, max_field_size=None))
        support.assert_roughly_linear(self, lambda k: [["a,b", 'q"', "z"]] * (20_000 * k), brisart_csv_dumps)


if __name__ == "__main__":
    unittest.main()
