r"""
File: brisartos/language/tests/test_language.py

Purpose
-------
Exercise language evaluation, lexer tokens, parser nodes, rejected syntax,
interpreter reuse and selected resource-growth limits.

Verifies: brisartos/language/interpreter.py, brisartos/language/lexer.py,
brisartos/language/parser.py.

Contains 38 test case(s) across 4 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.language.interpreter (brisartos/language/interpreter.py)
- brisartos.language.lexer (brisartos/language/lexer.py)
- brisartos.language.parser (brisartos/language/parser.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/language/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
Rejected syntax must raise LanguageError; an arithmetic fault such as division
by zero must pass through as the Python error it is. Huge strings and integers
must be refused before they are built.

LanguageTests:
- Arithmetic.
- Parentheses.
- Assignment.
- While.
- If else.
- Nested.
- Boolean short circuit.
- Not precedence.
- Unary.
- Division.
- Comparisons.
- String escape.
- Blank print.
- Comments.
- String hash.
- Undefined.
- Budget.
- Reject import.
- Reject call.
- Reject attribute.
- Reject chained comparison.
- Missing body.
- Orphan else.
- Top indent.
- Bad expression.
- Reserved assignment.
- Reuse resets state.
ResourceLimitTests:
- Huge string repeat is refused before it is built.
- String growth by addition is capped.
- Integer growth is capped.
- Ordinary large values still work.
- Limits do not touch small or mixed arithmetic.
LexerTests:
- Tokens end with an end marker.
- Comment stops the line but not inside a string.
- Bad characters and escapes are language errors.
ParserTests:
- Parse returns statement nodes.
- Block structure is kept.
- Source must be text.

Known limitations
-----------------
- Inputs are hand-picked examples, not a fuzz test, so unusual programs may
  behave in ways these tests do not cover.
- Passing proves only the 38 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/language/tests -p test_language.py
"""

import unittest

from brisartos.language.interpreter import MAX_INT_BITS, MAX_STRING_CHARS, Interpreter
from brisartos.language.lexer import LanguageError, tokens
from brisartos.language.parser import parse


class LanguageTests(unittest.TestCase):
    def output(self, source):
        return Interpreter().run(source)['output']

    def test_arithmetic(self):
        self.assertEqual(self.output('print(2 + 3 * 4)'), ['14'])

    def test_parentheses(self):
        self.assertEqual(self.output('print((2 + 3) * 4)'), ['20'])

    def test_assignment(self):
        self.assertEqual(Interpreter().run('x = 4\nx = x + 1')['variables']['x'], 5)

    def test_while(self):
        self.assertEqual(self.output('x = 0\nwhile x < 3:\n    print(x)\n    x = x + 1'), ['0', '1', '2'])

    def test_if_else(self):
        self.assertEqual(self.output('if False:\n    print(1)\nelse:\n    print(2)'), ['2'])

    def test_nested(self):
        self.assertEqual(self.output('x = 0\nwhile x < 3:\n    if x == 1:\n        print(x)\n    x = x + 1'), ['1'])

    def test_boolean_short_circuit(self):
        self.assertEqual(self.output('print(False and missing)\nprint(True or missing)'), ['False', 'True'])

    def test_not_precedence(self):
        self.assertEqual(self.output('print(not 1 == 2)'), ['True'])

    def test_unary(self):
        self.assertEqual(self.output('print(-2 * +3)'), ['-6'])

    def test_division(self):
        self.assertEqual(self.output('print(7 // 2)\nprint(7 % 2)\nprint(7 / 2)'), ['3', '1', '3.5'])

    def test_comparisons(self):
        self.assertEqual(self.output('print(2 <= 2)\nprint(2 >= 3)\nprint(2 != 3)'), ['True', 'False', 'True'])

    def test_string_escape(self):
        self.assertEqual(self.output('print("a\\nb")'), ['a\nb'])

    def test_blank_print(self):
        self.assertEqual(self.output('print()'), [''])

    def test_comments(self):
        self.assertEqual(self.output('# comment\nx = 3 # inline\nprint(x)'), ['3'])

    def test_string_hash(self):
        self.assertEqual(self.output('print("#")'), ['#'])

    def test_undefined(self):
        with self.assertRaises(LanguageError): self.output('print(missing)')

    def test_budget(self):
        with self.assertRaises(LanguageError): Interpreter(30).run('while True:\n    pass')

    def test_reject_import(self):
        with self.assertRaises(LanguageError): self.output('import os')

    def test_reject_call(self):
        with self.assertRaises(LanguageError): self.output('x = dangerous()')

    def test_reject_attribute(self):
        with self.assertRaises(LanguageError): self.output('x = a.b')

    def test_reject_chained_comparison(self):
        with self.assertRaises(LanguageError): self.output('print(1 < 2 < 3)')

    def test_missing_body(self):
        with self.assertRaises(LanguageError): parse('if True:')

    def test_orphan_else(self):
        with self.assertRaises(LanguageError): parse('else:\n    pass')

    def test_top_indent(self):
        with self.assertRaises(LanguageError): parse('  x = 1')

    def test_bad_expression(self):
        for source in ('x =', 'print(1 +)', 'print((1)', 'print("unterminated)'):
            with self.subTest(source=source):
                with self.assertRaises(LanguageError): self.output(source)

    def test_reserved_assignment(self):
        with self.assertRaises(LanguageError): self.output('import = 1')

    def test_reuse_resets_state(self):
        interpreter = Interpreter()
        interpreter.run('x = 3')
        self.assertEqual(interpreter.run('print(1)')['variables'], {})


class ResourceLimitTests(unittest.TestCase):
    def run_source(self, source):
        return Interpreter(max_steps=100000).run(source)['output']

    def test_huge_string_repeat_is_refused_before_it_is_built(self):
        for source in ('print("a" * 99999999)', 'print(99999999 * "a")', 'x = "ab"\nprint(x * 1000000)'):
            with self.assertRaises(LanguageError) as caught:
                self.run_source(source)
            self.assertIn('string too large', str(caught.exception))

    def test_string_growth_by_addition_is_capped(self):
        source = 'x = "a" * ' + str(MAX_STRING_CHARS) + '\nprint(x + "b")'
        with self.assertRaises(LanguageError):
            self.run_source(source)
        source = 'x = "ab"\nn = 0\nwhile n < 40:\n    x = x + x\n    n = n + 1'
        with self.assertRaises(LanguageError):
            self.run_source(source)

    def test_integer_growth_is_capped(self):
        source = 'x = 3\nn = 0\nwhile n < 40:\n    x = x * x\n    n = n + 1'
        with self.assertRaises(LanguageError) as caught:
            self.run_source(source)
        self.assertIn('integer too large', str(caught.exception))
        with self.assertRaises(LanguageError):
            self.run_source('x = 1\nn = 0\nwhile n < ' + str(MAX_INT_BITS + 10) + ':\n    x = x + x\n    n = n + 1')

    def test_ordinary_large_values_still_work(self):
        self.assertEqual(self.run_source('print("ab" * 1000 == "ab" * 1000)'), ['True'])
        source = 'x = 1\nn = 0\nwhile n < 200:\n    x = x * 2\n    n = n + 1\nprint(x)'
        self.assertEqual(self.run_source(source), [str(2 ** 200)])

    def test_limits_do_not_touch_small_or_mixed_arithmetic(self):
        self.assertEqual(self.run_source('print(True + 1)\nprint(2 * (7 / 2))\nprint(-3 * "ab")'), ['2', '7.0', ''])


class LexerTests(unittest.TestCase):
    def test_tokens_end_with_an_end_marker(self):
        self.assertEqual(tokens('x = 1')[-1], ('end', ''))
        self.assertEqual(tokens('x = 1')[:3], [('name', 'x'), ('op', '='), ('value', 1)])

    def test_comment_stops_the_line_but_not_inside_a_string(self):
        self.assertEqual(tokens('x # note'), [('name', 'x'), ('end', '')])
        self.assertEqual(tokens('"#"'), [('value', '#'), ('end', '')])

    def test_bad_characters_and_escapes_are_language_errors(self):
        for source in ('x = $', 'x = 1.5', '"\\q"', '"open'):
            with self.assertRaises(LanguageError):
                tokens(source)


class ParserTests(unittest.TestCase):
    def test_parse_returns_statement_nodes(self):
        nodes = parse('x = 1\nprint(x)')
        self.assertEqual([node[0] for node in nodes], ['assign', 'print'])

    def test_block_structure_is_kept(self):
        nodes = parse('if True:\n    pass\nelse:\n    pass')
        self.assertEqual(nodes[0][0], 'if')
        self.assertEqual(len(nodes[0][2]), 1)
        self.assertEqual(len(nodes[0][3]), 1)

    def test_source_must_be_text(self):
        with self.assertRaises(TypeError):
            parse(b'x = 1')


if __name__ == '__main__':
    unittest.main()
