# Shared Identifier Validation

`names.py` defines the identifier shape used by BrisartOS callers that need a validated name.

## Two functions, one predicate

`is_valid_name(name)` returns a boolean. It first requires a string with between one and `MAX_NAME_CHARS` characters, then requires an ASCII letter at the start. Remaining characters may be ASCII letters, digits, `_` or `-`. `MAX_NAME_CHARS` is 64.

`require_name(name, what="name")` returns the original value when that predicate succeeds. Otherwise it raises `ValueError`, including the caller's `what` label and a description of the accepted shape.

```python
from brisartos.common.names import is_valid_name, require_name

assert is_valid_name("field_notes")
assert is_valid_name("x-1")
assert not is_valid_name("../escape")
assert not is_valid_name(None)
assert require_name("Kernel") == "Kernel"
```

Names are validated, not cleaned or rewritten. Empty strings, leading digits, spaces, dots, separators, non-ASCII characters and overlong strings are rejected. Ordinary non-string inputs return `False` from the predicate.

## What this file does not decide

Validation does not reserve a name, check uniqueness, inspect a filesystem or resolve case collisions. The predicate distinguishes uppercase and lowercase characters but does not establish how a storage backend treats them. There are no imports or host operations in this file.

## Local checks

`tests/test_names.py` checks accepted shapes, rejected inputs, unchanged return values and explanatory error text. Its examples are selected cases rather than an exhaustive search.

```bash
python -B -m unittest discover -s brisartos/common/tests -p test_names.py
```
