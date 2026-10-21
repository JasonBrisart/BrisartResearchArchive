r"""
File: brisartos/language/parser.py

Purpose
-------
Build tuple-based expression and statement nodes from source text using
operator precedence and indentation-defined blocks.

Public interface:
- class Expression -- A precedence-climbing expression parser over one line of
  tokens.
- Expression(text) -- Tokenize one expression.
- Expression.take() -- Return the next token and advance.
- Expression.parse() -- Parse a complete expression and return its node;
  leftover tokens are an error.
- Expression.expression(minimum) -- Parse operators at or above a minimum
  precedence.
- parse(source) -- Turn program text into a list of statement nodes, handling
  indentation, if/else, while, print, pass and assignment.

Design notes:

Expression consumes a token list with precedence climbing and rejects leftover
tokens and chained comparisons. parse removes blank and comment-only lines,
records indentation and recursively assembles if, else and while bodies. The
grammar is deliberately limited; the returned nodes are data and are not
executed here.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.language.lexer (brisartos/language/lexer.py)
Standard library: none.
Imported by:
- brisartos/language/interpreter.py
- brisartos/machine/machine.py
Covered by tests: brisartos/language/tests/test_language.py.

Settings / parameters
---------------------
No module-level settings. Precedence lives in Expression.PRECEDENCE.

Edge cases
----------
Source that is not text raises TypeError. Tabs in indentation, bad indentation,
a missing body or colon, an orphan else, a reserved assignment name, a missing
parenthesis and chained comparisons raise LanguageError.

- Expression.parse() raises LanguageError: "unexpected expression suffix"
- Expression.expression() raises LanguageError: "closing parenthesis required"
- Expression.expression() raises LanguageError: "expression required"
- Expression.expression() raises LanguageError: "chained comparisons are not
  supported"
- parse() raises TypeError: "source must be text"
- parse() raises LanguageError: "tabs in indentation are not supported"
- parse() raises LanguageError: "top-level indentation must be zero"
- parse() raises LanguageError: "unexpected else or indentation"
- parse.block() raises LanguageError: "unexpected indentation on line {...}"
- parse.block() raises LanguageError: "compound statement needs a colon"
- parse.block() raises LanguageError: "indented body required"
- parse.block() raises LanguageError: "indented else body required"
- parse.block() raises LanguageError: "reserved assignment name"

Known limitations
-----------------
- A deliberately small subset: no functions, imports, lists, attributes, elif,
  for, break or return.
- print accepts exactly one expression or none.

Examples
--------
Run from the repository root.

::

    from brisartos.language.parser import parse

    nodes = parse('x = 1\nif x == 1:\n    print(x)\nelse:\n    pass')
    assert [node[0] for node in nodes] == ['assign', 'if']
"""

from .lexer import LanguageError, tokens


class Expression:
    PRECEDENCE = {'or': 1, 'and': 2, '==': 3, '!=': 3, '<': 3, '>': 3,
                  '<=': 3, '>=': 3, '+': 4, '-': 4, '*': 5, '/': 5, '//': 5, '%': 5}

    def __init__(self, text):
        self.items = tokens(text)
        self.index = 0

    def take(self):
        item = self.items[self.index]
        self.index += 1
        return item

    def parse(self):
        node = self.expression(0)
        if self.items[self.index][0] != 'end':
            raise LanguageError('unexpected expression suffix')
        return node

    def expression(self, minimum):
        kind, value = self.take()
        if kind == 'value':
            left = ('value', value)
        elif value in ('+', '-', 'not'):
            left = ('unary', value, self.expression(3 if value == 'not' else 6))
        elif kind == 'name' and value not in ('and', 'or'):
            left = ('name', value)
        elif value == '(':
            left = self.expression(0)
            if self.take() != ('op', ')'):
                raise LanguageError('closing parenthesis required')
        else:
            raise LanguageError('expression required')
        comparison_seen = False
        while True:
            op = self.items[self.index][1]
            precedence = self.PRECEDENCE.get(op, -1)
            if precedence < minimum:
                break
            if precedence == 3 and comparison_seen:
                raise LanguageError('chained comparisons are not supported')
            self.take()
            right = self.expression(precedence + 1)
            left = ('binary', op, left, right)
            comparison_seen = precedence == 3
        return left


def parse(source):
    if not isinstance(source, str):
        raise TypeError('source must be text')
    lines = []
    for number, raw in enumerate(source.splitlines(), 1):
        if '\t' in raw[:len(raw) - len(raw.lstrip())]:
            raise LanguageError('tabs in indentation are not supported')
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        lines.append((indent, raw.strip(), number))
    if lines and lines[0][0] != 0:
        raise LanguageError('top-level indentation must be zero')

    def block(index, indent):
        nodes = []
        while index < len(lines):
            current, text, number = lines[index]
            if current < indent:
                break
            if current != indent:
                raise LanguageError('unexpected indentation on line ' + str(number))
            if text == 'else:':
                break
            if text.startswith(('if ', 'while ')):
                keyword, condition = text.split(' ', 1)
                if not condition.endswith(':'):
                    raise LanguageError('compound statement needs a colon')
                condition = Expression(condition[:-1]).parse()
                index += 1
                if index >= len(lines) or lines[index][0] <= indent:
                    raise LanguageError('indented body required')
                body, index = block(index, lines[index][0])
                alternative = []
                if keyword == 'if' and index < len(lines) and lines[index][0] == indent and lines[index][1] == 'else:':
                    index += 1
                    if index >= len(lines) or lines[index][0] <= indent:
                        raise LanguageError('indented else body required')
                    alternative, index = block(index, lines[index][0])
                nodes.append((keyword, condition, body, alternative))
                continue
            if text == 'pass':
                nodes.append(('pass',))
            elif text.startswith('print(') and text.endswith(')'):
                expression = text[6:-1]
                nodes.append(('print', Expression(expression).parse() if expression.strip() else ('value', '')))
            else:
                items = tokens(text)
                if len(items) > 2 and items[0][0] == 'name' and items[1] == ('op', '='):
                    name = items[0][1]
                    if name in ('if', 'else', 'while', 'and', 'or', 'not', 'print', 'pass', 'import', 'def', 'class', 'return', 'for'):
                        raise LanguageError('reserved assignment name')
                    nodes.append(('assign', name, Expression(text[text.index('=')+1:]).parse()))
                else:
                    nodes.append(('expression', Expression(text).parse()))
            index += 1
        return nodes, index

    nodes, index = block(0, 0)
    if index != len(lines):
        raise LanguageError('unexpected else or indentation')
    return nodes
