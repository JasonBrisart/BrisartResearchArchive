# Restricted Source Language

A lexer, parser and interpreter execute a deliberately restricted source language.

## Source becomes results

`lexer.py` defines `LanguageError` and `tokens(text)`. It scans one line into `(kind, value)` pairs ending in `("end", "")`. Strings support newline, tab, backslash and quote escapes. A hash begins a comment only outside a string. Numbers are decimal integers; names use ASCII letters, digits and underscores.

`parser.py` defines `Expression` and `parse(source)`. Expression parsing uses precedence climbing; program parsing groups indentation-defined blocks into tuple nodes. The supported statements are assignment, print, if/else, while, pass and expression statements. Blank and comment-only lines are ignored. Tabs in indentation and nonzero initial indentation are rejected.

`interpreter.py` defines `Interpreter(max_steps=10000)`. `run(source)` parses, resets variables/output/step count, executes nodes and returns `variables`, `output` and `steps`. Parsing happens before reset, so a parse failure does not clear a previous run's state.

```python
from brisartos.language.interpreter import Interpreter

source = "n = 0\nwhile n < 3:\n    print(n)\n    n = n + 1"
result = Interpreter().run(source)
assert result["output"] == ["0", "1", "2"]
assert result["variables"]["n"] == 3
```

## Operators and syntax boundaries

Binary precedence, from weakest to strongest, is `or`, `and`, comparisons, addition/subtraction, then multiplication/division/floor-division/remainder. Unary `not` binds below arithmetic and comparisons; unary plus and minus bind more tightly. Parentheses group expressions. Chained comparisons are rejected.

Literals include integers, strings, `True`, `False` and `None`. Division may produce a float even though float literals are not recognized. Boolean operators short-circuit and return operand values.

There are no general function calls, imports, attributes, list/dictionary literals, function definitions, `for`, `elif`, `break` or `return`. Print is parsed as a statement accepting one expression or none, not as a general callable.

## Budgets are specific, not comprehensive

Each statement and expression consumes a step, and each while iteration consumes an additional step. Exceeding `max_steps` raises `LanguageError`.

Addition and multiplication check selected string/integer growth against `MAX_STRING_CHARS` (100,000) and `MAX_INT_BITS` (4,096). Integer checks are conservative estimates, not exact result-size calculations. Subtraction has no equivalent growth guard. Source parsing, total retained variables, accumulated output and elapsed time are not comprehensively bounded.

Language rejection raises `LanguageError`, a `ValueError`. Operand failures such as division by zero or incompatible addition propagate as their ordinary exception types. The implementation is not a sandbox for arbitrary Python.

## Separate machine lifecycle

The source-ROM lifecycle wrapper now lives in [../machine/](../machine/README.md), above the language layer. The lexer, parser and interpreter remain here.

## Tests in this directory

`tests/test_language.py` checks tokens, nodes, evaluation, rejected syntax, reuse and selected growth limits. Machine lifecycle tests live in `../machine/tests/test_machine.py`. Inputs are selected examples rather than grammar fuzzing.
