"""
File: packages/tests/test_demo.py

Purpose
-------
Tests for packages.demo: the shared demo really creates, re-wraps, opens, and
validates a package through the linked BSR2.

Verifies: packages/demo.py.
Contains 1 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- packages.demo (packages/demo.py)
Standard library: unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
None.

Edge cases
----------
DemoTests:
- run_demo() completes the full cycle: Bob reads Alice's payload and the
  custody chain ends intact.

Known limitations
-----------------
- Passing proves only the scenario listed above.

Examples
--------
::

    python -m unittest packages.tests.test_demo -v
"""

import unittest

from packages.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_full_cycle_completes(self):
        result = run_demo()
        transcript = "\n".join(result["transcript"])
        self.assertTrue(result["package_id"].startswith("demo-"))
        self.assertIn("hello from the demo package", transcript)
        self.assertTrue(result["transcript"][-1].startswith("demo complete"))


if __name__ == "__main__":
    unittest.main()
