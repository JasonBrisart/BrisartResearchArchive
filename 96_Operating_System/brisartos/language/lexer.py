r"""
File: brisartos/language/lexer.py

Purpose
-------
Convert one source line into typed tokens for literals, names and operators,
ending every token sequence with an explicit end marker.

Public interface:
- class LanguageError(ValueError) -- The single error type for the whole
  language; a ValueError.
- tokens(text) -- Return the list of (kind, value) tokens for a line, ending
  with the marker (end, "").

Design notes:

The scanner advances through the line without importing a parsing library. It
handles quoted strings before comments, so a hash inside a string remains text.
Numeric literals are decimal integers; identifiers use ASCII letters, digits
and underscores. Unsupported characters and malformed string escapes raise
LanguageError.

Communication / relationships
-----------------------------
Standard library: none.
Imported by:
- brisartos/language/interpreter.py
- brisartos/language/parser.py
Covered by tests: brisartos/language/tests/test_language.py,
brisartos/language/tests/test_rom.py.

Settings / parameters
---------------------
No module-level settings. The operator and escape tables are in the function.

Edge cases
----------
An unfinished or unknown escape, an unterminated string and any unsupported
character raise LanguageError.

- tokens() raises LanguageError: "unfinished escape"
- tokens() raises LanguageError: "unsupported escape"
- tokens() raises LanguageError: "unterminated string"
- tokens() raises LanguageError: "unsupported character: {...}"

Known limitations
-----------------
- Integers only: there are no float literals, so 1.5 is rejected at the dot.
- The lexer works on one line at a time; indentation is handled by the parser.

Examples
--------
Run from the repository root.

::

    from brisartos.language.lexer import LanguageError, tokens

    assert tokens('x = 1') == [('name', 'x'), ('op', '='), ('value', 1), ('end', '')]
    try:
        tokens('x = 1.5')
    except LanguageError:
        pass
    else:
        raise AssertionError('float literals must be refused')
"""

class LanguageError(ValueError):
    pass


def tokens(text):
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == '#':
            break
        elif c in ('"', "'"):
            quote = c
            i += 1
            value = ''
            while i < len(text) and text[i] != quote:
                if text[i] == '\\':
                    i += 1
                    if i >= len(text):
                        raise LanguageError('unfinished escape')
                    escapes = {'n': '\n', 't': '\t', '\\': '\\', '"': '"', "'": "'"}
                    if text[i] not in escapes:
                        raise LanguageError('unsupported escape')
                    value += escapes[text[i]]
                else:
                    value += text[i]
                i += 1
            if i >= len(text):
                raise LanguageError('unterminated string')
            i += 1
            result.append(('value', value))
        elif c.isascii() and c.isdigit():
            start = i
            while i < len(text) and text[i].isascii() and text[i].isdigit():
                i += 1
            result.append(('value', int(text[start:i])))
        elif c.isascii() and (c.isalpha() or c == '_'):
            start = i
            while i < len(text) and text[i].isascii() and (text[i].isalnum() or text[i] == '_'):
                i += 1
            name = text[start:i]
            if name in ('True', 'False', 'None'):
                result.append(('value', {'True': True, 'False': False, 'None': None}[name]))
            else:
                result.append(('name', name))
        else:
            pair = text[i:i+2]
            if pair in ('==', '!=', '<=', '>=', '//'):
                result.append(('op', pair))
                i += 2
            elif c in '+-*/%<>()=,':
                result.append(('op', c))
                i += 1
            else:
                raise LanguageError('unsupported character: ' + c)
    result.append(('end', ''))
    return result
