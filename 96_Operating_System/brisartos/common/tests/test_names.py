r"""
File: brisartos/common/tests/test_names.py

Purpose
-------
Exercise accepted and rejected identifier shapes and the return value and error
wording of require_name.

Verifies: brisartos/common/names.py.

Contains 4 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- brisartos.common.names (brisartos/common/names.py)
Standard library: unittest.
Discovered and run by run.py test (and by python -m unittest discover -s
brisartos/common/tests); nothing imports it.

Settings / parameters
---------------------
No module-level configuration is defined.

Inputs and component instances are created inside the individual test methods;
this file defines no shared setUp or tearDown method.

Edge cases
----------
Refused shapes include path-traversal names such as ../x and a/b, names with
spaces or dots, leading digits, non-ASCII letters, overlong names and non-text
values.

NameTests:
- Accepts plain names.
- Rejects unsafe or odd names.
- Require name returns the name.
- Require name explains the rule.

Known limitations
-----------------
- The inputs are hand-picked examples, not an exhaustive search of the name
  space.
- Passing proves only the 4 scenario(s) listed under Edge cases; behaviour
  outside them is not asserted here.

Examples
--------
Run from the repository root.

::

    python -B -m unittest discover -s brisartos/common/tests -p test_names.py
"""

import unittest

from brisartos.common.names import MAX_NAME_CHARS, is_valid_name, require_name


class NameTests(unittest.TestCase):
    def test_accepts_plain_names(self):
        for name in ('hello_lab', 'a', 'Kernel', 'x-1', 'a' * MAX_NAME_CHARS):
            self.assertTrue(is_valid_name(name), name)

    def test_rejects_unsafe_or_odd_names(self):
        too_long = 'a' * (MAX_NAME_CHARS + 1)
        for name in ('', '1abc', '_x', '-x', 'a b', 'a/b', '../x', 'a.b', 'caf\u00e9', too_long, None, 5, b'abc'):
            self.assertFalse(is_valid_name(name), repr(name))

    def test_require_name_returns_the_name(self):
        self.assertEqual(require_name('field_notes'), 'field_notes')

    def test_require_name_explains_the_rule(self):
        with self.assertRaises(ValueError) as caught:
            require_name('a/b', 'module name')
        self.assertIn('invalid module name', str(caught.exception))
        self.assertIn('letters, digits', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
