"""
File: v3/tests/test_v1_lineage.py

Purpose
-------
Carry every v1 fix forward: none of the 49 v1 defects reproduced by
v2/tests/v1_probe.py may reappear in v3. Together with test_v2_compat.py
(which holds v3 to v2's behaviour) this ties v3 to both earlier versions.

Communication / relationships
-----------------------------
Standard library: unittest, importlib.util, os, plus support.py in this
folder.
Verifies: v3/ and explicitly v2 markup against v1/, using the probe file in v2/tests/. Skipped if
v1/ or v2/tests/v1_probe.py is absent.

Settings / parameters
---------------------
- BRISART_SKIP_SLOW (environment variable) -- When set to 1, skips the
  timing probe M8.

Edge cases
----------
The probe is loaded from v2/tests by file path, not imported by name, so
it cannot collide with modules in this folder.

Known limitations
-----------------
A probe demonstrates one input per defect, not the defect's full extent.

Examples
--------
::

    python -B -m unittest discover -s v3/tests -p test_v1_lineage.py
"""

import importlib.util
import os
import types
import unittest

import support

REPO = support.V3.parent
PROBE = REPO / "v2" / "tests" / "v1_probe.py"


@unittest.skipUnless((REPO / "v1").is_dir() and PROBE.is_file(), "v1/ or v2/tests/v1_probe.py not present")
class V1LineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("v3_lineage_v1_probe", PROBE)
        cls.probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.probe)
        cls.v3 = types.SimpleNamespace(**{
            name: cls.probe._load_file(
                "lineage_latest_" + name,
                (REPO / "v2" if name == "markup" else support.V3) / ("brisart_%s.py" % name))
            for name in cls.probe.NAMES})
        cls.checks = cls.probe.build_checks(slow=os.environ.get("BRISART_SKIP_SLOW") != "1")

    def test_no_v1_defect_reproduces_on_v3(self):
        for ident, claim, predicate in self.checks:
            with self.subTest(probe=ident):
                self.assertFalse(self.probe.shows(predicate, self.v3), "%s reappeared in v3: %s" % (ident, claim))


if __name__ == "__main__":
    unittest.main()
