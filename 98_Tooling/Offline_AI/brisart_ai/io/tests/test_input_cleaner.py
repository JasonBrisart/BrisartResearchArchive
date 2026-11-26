"""
File: brisart_ai/io/tests/test_input_cleaner.py

Purpose
-------
Exercise quoted and shell-like input normalization.

Protected scenarios: TestNormalizeShellishInput verifies trims whitespace;
TestNormalizeShellishInput verifies strips matching double quotes;
TestNormalizeShellishInput verifies strips matching single quotes;
TestNormalizeShellishInput verifies mismatched quotes not stripped;
TestNormalizeShellishInput verifies inner quotes not touched.

Protected scenarios: TestNormalizeShellishInput verifies all whitespace returns empty;
TestNormalizeShellishInput verifies empty string returns empty;
TestNormalizeShellishInput verifies plain text unchanged.

Communication / relationships
-----------------------------
Uses literal strings without invoking a shell.

Direct project imports: brisart_ai.io.input_cleaner.

The cases use self.assertEqual to check returned values, persisted state or raised
errors. The suite is run through scripts/run_tests.py so Native API discovery happens
before collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Recognized wrappers and ordinary unwrapped questions.

Regression coverage includes
TestNormalizeShellishInput.test_strips_matching_single_quotes,
TestNormalizeShellishInput.test_mismatched_quotes_not_stripped,
TestNormalizeShellishInput.test_inner_quotes_not_touched,
TestNormalizeShellishInput.test_all_whitespace_returns_empty,
TestNormalizeShellishInput.test_empty_string_returns_empty,
TestNormalizeShellishInput.test_plain_text_unchanged.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python scripts/run_tests.py brisart_ai/io/tests/test_input_cleaner.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/io/tests/test_input_cleaner.py -k
test_strips_matching_double_quotes.
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
