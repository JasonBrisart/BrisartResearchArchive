# Restricted Source Language

A lexer, parser and interpreter execute a small source language; a fourth file wraps execution in a source-ROM lifecycle model.

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

## `rom.py`: a lifecycle around parsed source

`SourceROMMachine(source=DEFAULT_ROM, max_steps=10000, max_source_chars=65536)` validates source and limits, then parses once. Its source property is read-only.

- `boot()` requires reset state, creates a fresh interpreter and increments the attempt count.
- Successful execution leaves the machine halted.
- A caught execution exception leaves it faulted, records the exception text and is re-raised.
- Partial variables, output and step count are captured even after failure.
- `reset()` clears results and faults, preserves source and attempt count, and refuses running state.
- `snapshot()` copies result containers and reports fixed false flags for hardware boot, full-language execution and self-hosting.

```python
from brisartos.language.rom import SourceROMMachine

machine = SourceROMMachine("print(4)")
assert machine.boot()["output"] == ["4"]
machine.reset()
assert machine.boot()["boot_attempts"] == 2
```

The file's `main()` executes `DEFAULT_ROM` and prints a report. This is a lifecycle model, not firmware.

## Tests in this directory

`tests/test_language.py` checks tokens, nodes, evaluation, rejected syntax, reuse and selected growth limits. `tests/test_rom.py` checks lifecycle transitions, limits, faults, copied snapshots and independent instances. Inputs are selected examples rather than grammar fuzzing.
