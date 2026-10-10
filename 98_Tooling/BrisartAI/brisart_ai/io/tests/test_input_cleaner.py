"""
File: brisart_ai/io/tests/test_input_cleaner.py

Purpose
-------
Tests for brisart_ai/io/input_cleaner.py.

Communication / relationships
-----------------------------
Direct module imports: unittest, brisart_ai.io.input_cleaner.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Run this test file with the project-scoped test runner.
"""

import unittest
from brisart_ai.io.input_cleaner import normalize_shellish_input


class TestNormalizeShellishInput(unittest.TestCase):
    def test_trims_whitespace(self):
        self.assertEqual(normalize_shellish_input("  hello  "), "hello")

    def test_strips_matching_double_quotes(self):
        self.assertEqual(normalize_shellish_input('"hello world"'), "hello world")

    def test_strips_matching_single_quotes(self):
        self.assertEqual(normalize_shellish_input("'hello world'"), "hello world")

    def test_mismatched_quotes_not_stripped(self):
        self.assertEqual(normalize_shellish_input("\"hello world'"), "\"hello world'")

    def test_inner_quotes_not_touched(self):
        # Only a single outer layer is stripped; quotes about quoted text
        # inside the string are untouched.
        result = normalize_shellish_input('say "hi" please')
        self.assertEqual(result, 'say "hi" please')

    def test_all_whitespace_returns_empty(self):
        self.assertEqual(normalize_shellish_input("   "), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(normalize_shellish_input(""), "")

    def test_plain_text_unchanged(self):
        self.assertEqual(normalize_shellish_input("stats"), "stats")


if __name__ == "__main__":
    unittest.main()

