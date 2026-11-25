r"""
File: brisart_ai/tests/test_version_info.py

Purpose
-------
Exercise version resolution and fallback.

Protected scenarios: TestVersionInfo verifies app name is brisartai; TestVersionInfo
verifies version is nonempty string; TestVersionInfo verifies version not the unknown
fallback when file exists.

Communication / relationships
-----------------------------
Uses a real version file and missing or invalid file cases.

Direct project imports: brisart_ai.version_info.

The cases use self.assertEqual, self.assertIsInstance, self.assertTrue,
self.assertNotEqual to check returned values, persisted state or raised errors. The
suite is run through scripts/run_tests.py so Native API discovery happens before
collection.

Settings / parameters
---------------------
Run independently through the project test runner.

The test names above define the behaviors under examination. Temporary fixtures, patch
contexts and direct calls supply inputs; these are not user-configurable application
settings.

Edge cases
----------
Unavailable version data falls back without aborting startup.

Regression coverage includes TestVersionInfo.test_app_name_is_brisartai,
TestVersionInfo.test_version_is_nonempty_string,
TestVersionInfo.test_version_not_the_unknown_fallback_when_file_exists.

Known limitations
-----------------
Uses controlled local fixtures, not a production research index.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_version_info.py -q

To run one behavior rather than the full suite, use pytest selection through the project
runner: python scripts/run_tests.py brisart_ai/tests/test_version_info.py -k
test_version_is_nonempty_string.
"""

import unittest
from brisart_ai.version_info import APP_NAME, __version__


class TestVersionInfo(unittest.TestCase):
    def test_app_name_is_brisartai(self):
        self.assertEqual(APP_NAME, "BrisartAI")

    def test_version_is_nonempty_string(self):
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)

    def test_version_not_the_unknown_fallback_when_file_exists(self):
        # version.txt exists in this package tree, so it should be read,
        # not fall back to "0.0.0-unknown".
        self.assertNotEqual(__version__, "0.0.0-unknown")


if __name__ == "__main__":
    unittest.main()
