"""
File: crypto/tests/test_encryption_link.py

Purpose
-------
Tests for the link between Identity Tools and BSR2
(crypto/encryption.py): that every BSR2 library module is linked
from 97_Encryption/Official, that legacy data sealed by Identity Tools 1.9.2
still opens through the link, and that without BSR2 the
program starts and reports
"Encryption not found" instead of encrypting anything.

Verifies: crypto/encryption.py, crypto/envelope.py, crypto/factors.py,
crypto/rng.py, cli.py, packages/main.py.
Contains 13 test case(s) across 3 TestCase class(es).

Design notes:

The missing-encryption scenario runs in a subprocess against a copy of this
application tree placed where no 97_Encryption sibling exists, because the
link is resolved once per process and this test process is already linked.

The compatibility fixtures were sealed by Identity Tools 1.9.2 using its last
vendored copy of BSR2 (0.3.0-alpha), with a deterministic test generator so
the bytes are reproducible.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.encryption (crypto/encryption.py)
- crypto.envelope (crypto/envelope.py)
- crypto.errors (crypto/errors.py)
- crypto.factors (crypto/factors.py)
- crypto.rng (crypto/rng.py)
Standard library: os, pathlib, shutil, subprocess, sys,
tempfile, unittest.
Discovered and run by tests/run_tests.py (and by ``python -m unittest``);
nothing imports it.

Settings / parameters
---------------------
- _APP_ROOT -- this application tree (the directory holding cli.py).
- _MASTER_KEY = bytes(range(32)) -- key the fixtures were sealed under.
- _SEALED_JSON, _SEALED_BYTES, _BOUND_FACTOR -- 1.9.2 fixtures.

Edge cases
----------
LinkedEncryptionTests:
- The link is available and located at 97_Encryption/Official.
- The status line names 97_Encryption/Official relative to the archive and
  never this machine's absolute path; 95_Identity_Tools and 97_Encryption
  share one parent folder.
- Every linked module comes from the linked directory.
- Every brisart_security_* module 97_Encryption/Official ships is linked.
- The application tree contains no copy of any brisart_security_* module.
CompatibilityTests:
- A JSON payload sealed by 1.9.2 opens.
- A byte payload sealed by 1.9.2 opens.
- A factor bound by 1.9.2 verifies, and a different value does not.
- Both 1.9.2 payloads reseal to the v3 format and open to the same bytes.
- The 1.9.2 binding is recognised as legacy and re-binds to mac64.
EncryptionNotFoundTests:
- Resolving a directory that does not exist reports Encryption not found,
  says to keep the two folders together, and does not quote the path.
- Resolving a copy of BSR2 outside the linked directory is
  refused.
- Without 97_Encryption the CLI starts (version exits 0), and package demo
  exits 3 with "Encryption not found".

Known limitations
-----------------
- The subprocess test copies this tree into a temporary directory; it takes a
  few seconds.
- Legacy keyring unlock is not pinned here because one legacy derivation takes
  over a minute in pure Python; crypto/tests/test_keyring.py
  LegacyKeyringTests (slow suite) unlocks and migrates a v1 keyring.

Examples
--------
::

    python -m unittest crypto.tests.test_encryption_link -v
    python tests/run_tests.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from crypto import encryption
from crypto.envelope import SEALED_FORMAT, is_legacy, open_bytes, open_json, reseal
from crypto.factors import bind_factor, is_legacy_binding, verify_bound_factor
from crypto.rng import new_generator

_APP_ROOT = Path(__file__).resolve().parents[2]
_MASTER_KEY = bytes(range(32))

_SEALED_JSON = {
    "algorithm": "BSR2-ARX-SPONGE-ETM",
    "version": 2,
    "salt": "5d366f6bbdd90f7d6cf427c40b9f2ee550b1beae7f5c0b171d961de37f1d5695",
    "nonce": "ea32181da668dcf735ed643bf1f2090262e618767cce49b0f0d07495bd7c19de",
    "ciphertext": (
        "c9a2a5055b82d2899f8e60912a37dcce3b47dd16a771c7a02444c1a281400508"
        "d66bb0930571f2ed9cce502132f0288298fbab91e1187a18116fddc9a14c6a70"
        "fce63093ede2cc68ea95c734a78779f9669d51c2e9544a8023442c1638cd195d"
        "688eb7649145831603d513d1c66b0d044fd775ded07ffc7c8615b0938b77fd5a"
        "5e0f9e87d03f59cc1983931810ad2fe1072e1b738ef0ec182764b0173c94a795"
        "be621c428f1c7d518700fde2ee9d938355ae0216fe1612a6c367a63a1e8f5db4"
        "3504d3a8bd6fc977836f6517bb64ead52d56a7b54645be2decada2e107b683e4"
        "c5e3e5785be38250890072a29992d7e0b841cf5290fefbca7e6d10b432031b7e"
    ),
    "tag": "09b211254bb03366acdf86d7fccdfdf02ef8dc7e356abc96df6f88186a63faa1",
}

_SEALED_BYTES = {
    "algorithm": "BSR2-ARX-SPONGE-ETM",
    "version": 2,
    "salt": "a5dc1358ccd66e181fb6a5196ef1d7b2fba166ef4710c27cd849798fdd3dfbef",
    "nonce": "6fbaf3b9cf93a5afe718ec6554e4da495c8dd19aa67b00a1bf1ba93feac4df84",
    "ciphertext": (
        "b041bd89e078c08cfa5d55be9913abfc5247822b374fbec44581b53a79b15b80"
        "d1217f0461620234dcdc3bd8424f588bbdac0771bac7e8cadc06045688a6409a"
        "d536984711644b33b38801f7098b7b4c5661af94391a2ed22b5906eff9f072b2"
        "30b75d66b40767fd2337f0001909bfe346c803e3c4229a6e0cce613ce98cb57d"
        "e55575349ac9b616a7bee255fa5f4f25370c78f0c2dff39cdc293a6e03d21140"
        "0e8c2f65ea976b7417b0629cf6a57aceca3cdd0032c66d2b151f40202c15625f"
        "db37c3b2804df2c5a22c7f13fd2aaf2a4d782d95bc75d40e5d486b33dae7a79e"
        "efb6a3d5966d5cfdbdfe21e52b4b0c1f37a2f923d200f55b0b92ff6dc173663c"
    ),
    "tag": "4417d8c9c58751938c20e2c6ae8101ad02578304e3896be03a8d071f3545361d",
}

_BOUND_FACTOR = (
    "bsr2$keyed_mac$device$ad4ff6a68908e85336"
    "f97be59df93e57183576a812fd4ffb47bf4aa41b688a75"
)


class LinkedEncryptionTests(unittest.TestCase):
    def test_link_is_available_at_97_encryption_official(self):
        link = encryption.status()
        self.assertTrue(link.available, link.describe())
        self.assertEqual(link.location, encryption.ENCRYPTION_DIR)
        self.assertEqual(link.location.parts[-2:], ("97_Encryption", "Official"))

    def test_status_names_the_folder_relative_to_the_archive_only(self):
        # The status line must never show where the archive lives on this
        # machine, only that encryption comes from 97_Encryption/Official.
        text = encryption.status().describe()
        self.assertTrue(text.endswith(", from 97_Encryption/Official"), text)
        self.assertNotIn(str(encryption.ARCHIVE_ROOT), text)
        self.assertEqual(
            encryption.ENCRYPTION_DIR.parent.parent, _APP_ROOT.parent.parent
        )

    def test_every_bsr2_module_is_loaded_from_the_linked_directory(self):
        library = encryption.require()
        for attribute, name in encryption.REQUIRED_MODULES.items():
            origin = Path(getattr(library, attribute).__file__).resolve()
            self.assertEqual(origin.parent, encryption.ENCRYPTION_DIR.resolve(), name)

    def test_every_library_module_in_97_encryption_is_linked(self):
        shipped = sorted(
            path.stem
            for path in encryption.ENCRYPTION_DIR.glob("brisart_security_*.py")
        )
        self.assertEqual(shipped, sorted(encryption.REQUIRED_MODULES.values()))

    def test_application_tree_holds_no_copy_of_brisart_encryption(self):
        copies = sorted(
            str(path.relative_to(_APP_ROOT))
            for path in _APP_ROOT.rglob("brisart_security_*.py")
        )
        self.assertEqual(copies, [])


class CompatibilityTests(unittest.TestCase):
    def test_json_sealed_by_1_9_2_opens(self):
        payload = open_json(_MASTER_KEY, _SEALED_JSON, "record:compat")
        self.assertEqual(
            payload, {"label": "compat", "value": "BrisartIdentityTools 1.9.2"}
        )

    def test_bytes_sealed_by_1_9_2_open(self):
        plaintext = open_bytes(_MASTER_KEY, _SEALED_BYTES, "attachment:compat")
        self.assertEqual(plaintext, b"sealed by vendored BSR2 Alpha 3")

    def test_payloads_sealed_by_1_9_2_migrate_to_the_current_format(self):
        rng = new_generator("link-test")
        for sealed, context in ((_SEALED_JSON, "record:compat"), (_SEALED_BYTES, "attachment:compat")):
            self.assertTrue(is_legacy(sealed))
            migrated = reseal(_MASTER_KEY, sealed, context, rng)
            self.assertEqual(migrated["format"], SEALED_FORMAT)
            self.assertFalse(is_legacy(migrated))
            self.assertEqual(
                open_bytes(_MASTER_KEY, migrated, context), open_bytes(_MASTER_KEY, sealed, context)
            )

    def test_factor_bound_by_1_9_2_rebinds_to_the_current_construction(self):
        self.assertTrue(is_legacy_binding(_BOUND_FACTOR))
        rebound = bind_factor(_MASTER_KEY, "device", "fixture-device")
        self.assertFalse(is_legacy_binding(rebound))
        self.assertTrue(verify_bound_factor(_MASTER_KEY, "device", "fixture-device", rebound))

    def test_factor_bound_by_1_9_2_verifies(self):
        self.assertTrue(
            verify_bound_factor(_MASTER_KEY, "device", "fixture-device", _BOUND_FACTOR)
        )
        self.assertFalse(
            verify_bound_factor(_MASTER_KEY, "device", "other-device", _BOUND_FACTOR)
        )


class EncryptionNotFoundTests(unittest.TestCase):
    def test_missing_directory_reports_encryption_not_found(self):
        with tempfile.TemporaryDirectory() as temporary:
            link = encryption._resolve(Path(temporary) / "97_Encryption" / "Official")
        self.assertFalse(link.available)
        self.assertTrue(link.describe().startswith("Encryption not found: "))
        self.assertIn("together in the same folder", link.problem)
        self.assertNotIn(temporary, link.problem)

    def test_copy_outside_the_linked_directory_is_refused(self):
        encryption.require()
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary)
            for name in encryption.REQUIRED_MODULES.values():
                shutil.copy2(encryption.ENCRYPTION_DIR / f"{name}.py", copy)
            try:
                link = encryption._resolve(copy)
            finally:
                if str(copy) in sys.path:
                    sys.path.remove(str(copy))
        self.assertFalse(link.available)
        self.assertIn("loaded from 97_Encryption/Official/", link.problem)
        self.assertIn("not from a copy outside this archive", link.problem)
        self.assertNotIn(str(encryption.ARCHIVE_ROOT), link.problem)

    def test_cli_without_brisart_encryption_reports_encryption_not_found(self):
        with tempfile.TemporaryDirectory() as temporary:
            app_root = Path(temporary) / "95_Identity_Tools" / _APP_ROOT.name
            shutil.copytree(
                _APP_ROOT,
                app_root,
                ignore=shutil.ignore_patterns("__pycache__", "data"),
            )
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            env.pop("PYTHONPATH", None)

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-S", "cli.py", *args],
                    cwd=app_root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            version = run("version")
            demo = run("package", "demo")
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertEqual(demo.returncode, 3, demo.stdout + demo.stderr)
        self.assertIn("Encryption not found: ", demo.stderr)


if __name__ == "__main__":
    unittest.main()
