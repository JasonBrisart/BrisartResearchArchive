r"""
File: brisartos/language/interpreter.py

Purpose
-------
Evaluate parsed BrisartOS language nodes with per-run variables, captured print
output, a step budget and selected arithmetic growth checks.

Public interface:
- class Interpreter -- Executes statement nodes with a step budget and growth
  limits.
- Interpreter(max_steps=10000) -- Create an interpreter with a positive step
  budget.
- Interpreter.tick() -- Spend one step and raise LanguageError when the budget
  is exhausted.
- Interpreter.check_sum(left, right) -- Refuse a string or integer addition
  whose result would exceed the limits.
- Interpreter.check_product(left, right) -- Refuse a string or integer
  multiplication whose result would exceed the limits.
- Interpreter.value(node) -- Evaluate an expression node, spending one step per
  node.
- Interpreter.execute(nodes) -- Run a list of statement nodes.
- Interpreter.run(source) -- Parse source, reset state, execute it and return
  the variables, the printed lines and the steps used.

Design notes:

run parses before resetting execution state, then executes the resulting nodes.
Each expression and statement consumes steps, and while iterations consume an
additional step. Addition and multiplication have string or integer guards;
other operators use their operand behavior directly. These checks are not a
total-memory, wall-clock or arbitrary-code isolation guarantee.

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.language.lexer (brisartos/language/lexer.py)
- brisartos.language.parser (brisartos/language/parser.py)
Standard library: none.
Imported by:
- brisartos/kernel/composition.py
- brisartos/machine/machine.py
Covered by tests: brisartos/language/tests/test_language.py.

Settings / parameters
---------------------
- MAX_STRING_CHARS = 100000 -- Longest string, in characters, that + or * may
  produce.
- MAX_INT_BITS = 4096 -- Largest integer, in bits, that + or * may produce.

Edge cases
----------
Ordinary Python errors from the operands, such as ZeroDivisionError or
TypeError, pass through unchanged and are not LanguageError.

- Interpreter.__init__() raises ValueError: "max_steps must be a positive
  integer"
- Interpreter.tick() raises LanguageError: "execution step budget exhausted"
- Interpreter.check_sum() raises LanguageError: "string too large"
- Interpreter.check_sum() raises LanguageError: "integer too large"
- Interpreter.check_product() raises LanguageError: "string too large"
- Interpreter.check_product() raises LanguageError: "integer too large"
- Interpreter.value() raises LanguageError: "undefined name: {...}"
- Interpreter.value() raises LanguageError: "unsupported operator"

Known limitations
-----------------
- The budget limits steps and growth, not wall-clock time or the total memory a
  program holds in variables.
- The language has no call, import or attribute, which is why a program cannot
  reach the machine; nothing here sandboxes anything.
- Growth guards cover addition and multiplication, not subtraction or total
  output accumulation. Parsing occurs before the execution budget applies.

Examples
--------
Run from the repository root.

::

    from brisartos.language.interpreter import Interpreter

    result = Interpreter(max_steps=100).run('x = 4\nprint(x + 1)')
    assert result['output'] == ['5']
    assert result['variables'] == {'x': 4}
"""

from .lexer import LanguageError
from .parser import parse

MAX_STRING_CHARS = 100_000
MAX_INT_BITS = 4_096


class Interpreter:
    def __init__(self, max_steps=10000):
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError('max_steps must be a positive integer')
        self.max_steps = max_steps
        self.steps = 0
        self.variables = {}
        self.output = []

    def tick(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise LanguageError('execution step budget exhausted')

    def check_sum(self, left, right):
        if isinstance(left, str) and isinstance(right, str):
            if len(left) + len(right) > MAX_STRING_CHARS:
                raise LanguageError('string too large')
        elif isinstance(left, int) and isinstance(right, int):
            if max(left.bit_length(), right.bit_length()) + 1 > MAX_INT_BITS:
                raise LanguageError('integer too large')

    def check_product(self, left, right):
        if isinstance(left, str) and isinstance(right, int):
            left, right = right, left
        if isinstance(left, int) and isinstance(right, str):
            if abs(left) * len(right) > MAX_STRING_CHARS:
                raise LanguageError('string too large')
        elif isinstance(left, int) and isinstance(right, int):
            if left.bit_length() + right.bit_length() > MAX_INT_BITS:
                raise LanguageError('integer too large')

    def value(self, node):
        self.tick()
        kind = node[0]
        if kind == 'value':
            return node[1]
        if kind == 'name':
            if node[1] not in self.variables:
                raise LanguageError('undefined name: ' + node[1])
            return self.variables[node[1]]
        if kind == 'unary':
            value = self.value(node[2])
            if node[1] == 'not':
                return not value
            return +value if node[1] == '+' else -value
        op = node[1]
        left = self.value(node[2])
        if op == 'and':
            return self.value(node[3]) if left else left
        if op == 'or':
            return left if left else self.value(node[3])
        right = self.value(node[3])
        if op == '+':
            self.check_sum(left, right)
            return left + right
        if op == '-': return left - right
        if op == '*':
            self.check_product(left, right)
            return left * right
        if op == '/': return left / right
        if op == '//': return left // right
        if op == '%': return left % right
        if op == '==': return left == right
        if op == '!=': return left != right
        if op == '<': return left < right
        if op == '>': return left > right
        if op == '<=': return left <= right
        if op == '>=': return left >= right
        raise LanguageError('unsupported operator')

    def execute(self, nodes):
        for node in nodes:
            self.tick()
            kind = node[0]
            if kind == 'assign':
                self.variables[node[1]] = self.value(node[2])
            elif kind == 'print':
                self.output.append(str(self.value(node[1])))
            elif kind == 'expression':
                self.value(node[1])
            elif kind == 'if':
                self.execute(node[2] if self.value(node[1]) else node[3])
            elif kind == 'while':
                while self.value(node[1]):
                    self.tick()
                    self.execute(node[2])

    def run(self, source):
        nodes = parse(source)
        self.steps = 0
        self.variables = {}
        self.output = []
        self.execute(nodes)
        return {'variables': dict(self.variables), 'output': list(self.output), 'steps': self.steps}
