"""
File: v2/tests/test_v1_lineage.py

Purpose
-------
Hold v2 to every v1 defect it fixed: each of the 49 probes in
v1_probe.py must reproduce on v1 (so the probe is still meaningful) and
must not reproduce on v2.

Communication / relationships
-----------------------------
Standard library: unittest, plus support.py and v1_probe.py in this
folder.
Verifies: v2/ against v1/. Skipped if v1/ is absent.

Settings / parameters
---------------------
- BRISART_SKIP_SLOW (environment variable) -- When set to 1, skips the
  timing probe M8, which takes about ten seconds on v1.

Edge cases
----------
Each probe runs as its own subTest, so one regression does not hide the
others.

Known limitations
-----------------
A probe demonstrates one input per defect, not the defect's full extent;
the per-module tests cover the rest.

Examples
--------
::

    python -B -m unittest discover -s v2/tests -p test_v1_lineage.py
"""

import os
import unittest

import support
import v1_probe

V1 = support.V2.parent / "v1"


@unittest.skipUnless(V1.is_dir(), "v1/ folder not present")
class V1LineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = v1_probe.load_v1(V1)
        cls.v2 = v1_probe.load_version(support.V2, "lineage_v2")
        cls.checks = v1_probe.build_checks(slow=os.environ.get("BRISART_SKIP_SLOW") != "1")

    def test_every_v1_defect_still_reproduces_on_v1(self):
        for ident, claim, predicate in self.checks:
            with self.subTest(probe=ident):
                self.assertTrue(v1_probe.shows(predicate, self.v1), "%s no longer shows on v1: %s" % (ident, claim))

    def test_no_v1_defect_reproduces_on_v2(self):
        for ident, claim, predicate in self.checks:
            with self.subTest(probe=ident):
                self.assertFalse(v1_probe.shows(predicate, self.v2), "%s regressed in v2: %s" % (ident, claim))

    def test_the_probe_list_is_complete(self):
        idents = [ident for ident, _, _ in v1_probe.build_checks(slow=True)]
        self.assertEqual(len(idents), 49)
        self.assertEqual(len(set(idents)), 49)


if __name__ == "__main__":
    unittest.main()
