r"""
File: brisartos/common/names.py

Purpose
-------
Validate BrisartOS identifiers with one ASCII naming rule, returning either a
boolean decision or the unchanged validated name.

Public interface:
- is_valid_name(name) -- Return True when name is text of 1 to MAX_NAME_CHARS
  characters that starts with an ASCII letter and continues with ASCII letters,
  digits, underscore or hyphen. Ordinary non-string inputs return False.
- require_name(name, what='name') -- Return name unchanged if it is valid,
  otherwise raise ValueError that spells out the rule; what labels the kind of
  name in the message.

Design notes:

The validator checks type and length before indexing the first character. The
remaining characters are checked individually, so separators, dots and
whitespace are rejected rather than normalized. require_name delegates to that
same predicate and adds a caller-supplied label to its ValueError.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/kernel/kernel.py
- brisartos/modules/api.py
- brisartos/modules/registry.py
- brisartos/services/registry.py
Covered by tests: brisartos/common/tests/test_names.py.

Settings / parameters
---------------------
- MAX_NAME_CHARS = 64 -- Longest accepted name, in characters.

Edge cases
----------
is_valid_name treats any non-text value (None, numbers, bytes) as invalid
instead of raising. require_name raises ValueError for every invalid value,
including non-text.

- require_name() raises ValueError: "invalid {...}: {...} (start with a letter;
  letters, digits, _ and - only; max {...} characters)"

Known limitations
-----------------
- Names are case-sensitive here, but case-insensitive filesystems treat Notes
  and notes as the same folder, so two modules whose names differ only by case
  would share files there. This has not been tested on those systems.
- The rule validates shape only. It does not check that a name is meaningful or
  unused.

Examples
--------
Run from the repository root.

::

    from brisartos.common.names import is_valid_name, require_name

    assert is_valid_name('field_notes')
    assert not is_valid_name('../escape')
    try:
        require_name('a/b', 'module name')
    except ValueError as error:
        assert 'invalid module name' in str(error)
"""

MAX_NAME_CHARS = 64


def is_valid_name(name):
    if not isinstance(name, str) or not 0 < len(name) <= MAX_NAME_CHARS:
        return False
    if not (name[0].isascii() and name[0].isalpha()):
        return False
    return all(char.isascii() and (char.isalnum() or char in '_-') for char in name)


def require_name(name, what='name'):
    if not is_valid_name(name):
        raise ValueError('invalid ' + what + ': ' + repr(name)
                         + ' (start with a letter; letters, digits, _ and - only; max '
                         + str(MAX_NAME_CHARS) + ' characters)')
    return name
