r"""
File: brisart_ai/tests/test_version_info.py

Purpose
-------
Check version info behavior through 1 unittest test group.

Communication / relationships
-----------------------------
Direct module imports: unittest, brisart_ai.version_info.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined
in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing
implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or
security validation.

Examples
--------
python scripts/run_tests.py brisart_ai/tests/test_version_info.py
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
