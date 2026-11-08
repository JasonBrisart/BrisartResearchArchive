"""
File: packages/tests/test_demo.py

Purpose
-------
Tests for packages.demo: the shared demo really creates, re-wraps, opens, and
validates a package through the linked Brisart Encryption.

Verifies: packages/demo.py.
Contains 2 test case(s) across 1 TestCase class(es).

Communication / relationships
-----------------------------
Depends on (project modules):
- packages.ciphers (packages/ciphers.py)
- packages.demo (packages/demo.py)
- packages.package (packages/package.py)
Standard library: json, pathlib, tempfile, unittest.
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
- run_demo(save_to_disk=True) writes the package, both passphrases, the
  custody summary, and a README, and the saved package opens as Bob.

Known limitations
-----------------
- Passing proves only the scenario listed above.

Examples
--------
::

    python -m unittest packages.tests.test_demo -v
"""

import json
import tempfile
import unittest
from pathlib import Path

from packages import ciphers
from packages import package as ibp_package
from packages.demo import run_demo


class DemoTests(unittest.TestCase):
    def test_full_cycle_completes(self):
        result = run_demo()
        transcript = "\n".join(result["transcript"])
        self.assertTrue(result["package_id"].startswith("demo-"))
        self.assertIn("hello from the demo package", transcript)
        self.assertTrue(result["transcript"][-1].startswith("demo complete"))
        self.assertIsNone(result["folder"])

    def test_saved_demo_writes_an_openable_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = run_demo(save_to_disk=True, output_root=temporary)["folder"]
            names = sorted(path.name for path in Path(folder).iterdir())
            self.assertEqual(names, [
                "README.txt", "alice_passphrase.txt", "bob_passphrase.txt",
                "custody_chain.txt", "package.json",
            ])
            state = json.loads((folder / "package.json").read_text())
            bob_key = ciphers.text_master_key((folder / "bob_passphrase.txt").read_text())
            payload, _state = ibp_package.open_package(state, "bob", bob_key)
        self.assertEqual(payload, {"message": "hello from the demo package"})


if __name__ == "__main__":
    unittest.main()
