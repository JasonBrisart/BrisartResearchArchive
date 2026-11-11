"""
File: tests/test_encryption.py

Purpose
-------
Verify entitle/encryption.py, Entitle's link to BSR2 in 97_Encryption/Official: that it resolves
  to the archive's own 97_Encryption/Official and nowhere else, that every linked module comes
  from that folder, that Entitle keeps no copy of any brisart_security_* module, that a missing,
  incomplete, foreign or incompatible library is reported as "Encryption not found" with a
  reason that never shows this machine's path, and that without 97_Encryption Entitle still
  runs every command that needs no encryption.

Communication / relationships
-----------------------------
Imports the entitle package root (EntitleError) and entitle/encryption.py, and uses
  tests/support.py (identity, key, LEGACY_ENTITLEMENT, ENTITLE_ROOT). The last test copies the
  Entitle folder into a temporary 98_Tooling with no 97_Encryption beside it and runs main.py
  there as real processes. Sealing and opening files are tested in tests/test_entitlements.py.
  Run by pytest; nothing imports it.

Settings / parameters
---------------------
Library-resolution tests call encryption._resolve with a folder of their choosing; the one that
  imports a copy of the library restores sys.path afterwards. The process test has a 120-second
  limit per command.

Edge cases
----------
Covers a missing folder, a folder missing a module file, a copy of the library outside the
  archive (refused even when its files are identical), a required format constant that does not
  match, require() raising EncryptionNotFoundError, and, in the process test, issue, verify,
  migrate and track deploy failing with one "Encryption not found" line and no traceback while
  track fork, revoke and report succeed.

Known limitations
-----------------
Does not test BSR2 itself; its tests live in 97_Encryption/Official/tests. Linking a different
  BSR2 release is covered only through the format checks, not by running another release. The
  process test takes a few seconds.

Examples
--------
From the directory containing main.py:

    python -m pytest tests/test_encryption.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from entitle import EntitleError, encryption
from entitle.encryption import EncryptionNotFoundError
from support import ENTITLE_ROOT, ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PRODUCT, SUBJECT


class TestTheLinkToTheArchive:
    def test_the_link_resolves_to_97_encryption_official_beside_98_tooling(self):
        link = encryption.status()
        assert link.available, link.problem
        assert link.location.parts[-2:] == ("97_Encryption", "Official")
        assert encryption.ENCRYPTION_DIR.parent.parent == ENTITLE_ROOT.parent.parent
        assert ENTITLE_ROOT.parent.name == "98_Tooling"

    def test_the_status_line_names_the_archive_folder_not_this_machine(self):
        text = encryption.status().describe()
        assert text.startswith("Encryption: BSR2 Alpha")
        assert text.endswith(", from 97_Encryption/Official")
        assert str(ENTITLE_ROOT.parent.parent) not in text

    def test_every_module_entitle_imports_comes_from_the_linked_folder(self):
        library = encryption.require()
        assert set(vars(library)) == set(encryption.REQUIRED_MODULES)
        for module in vars(library).values():
            assert Path(module.__file__).resolve().parent == encryption.ENCRYPTION_DIR.resolve()

    def test_the_required_modules_are_the_ones_the_current_and_previous_formats_need(self):
        modules = set(encryption.REQUIRED_MODULES.values())
        assert {"brisart_security_aead", "brisart_security_envelope", "brisart_security_drbg"} <= modules
        for name in modules:
            assert (encryption.ENCRYPTION_DIR / f"{name}.py").is_file()

    def test_entitle_holds_no_copy_of_any_brisart_encryption_module(self):
        assert not (ENTITLE_ROOT / "vendor").exists()
        found = [p for p in ENTITLE_ROOT.rglob("brisart_security_*") if "__pycache__" not in p.parts]
        assert found == []


class TestEncryptionNotFound:
    def test_a_missing_folder_is_reported_with_the_fix_and_no_absolute_path(self, tmp_path):
        link = encryption._resolve(tmp_path / "97_Encryption" / "Official")
        assert not link.available
        assert "Keep the 98_Tooling and 97_Encryption folders together" in link.problem
        assert link.describe().startswith("Encryption not found: ")

    def test_a_missing_module_file_is_named(self, tmp_path):
        folder = tmp_path / "Official"
        folder.mkdir()
        link = encryption._resolve(folder)
        assert not link.available and "is missing brisart_security_primitives.py" in link.problem

    def test_a_copy_outside_the_linked_folder_is_refused(self, tmp_path, monkeypatch):
        encryption.require()  # link the real library first, so this test does not depend on test order
        monkeypatch.setattr(sys, "path", list(sys.path))
        copy = tmp_path / "Official"
        copy.mkdir()
        for name in encryption.REQUIRED_MODULES.values():
            shutil.copy(encryption.ENCRYPTION_DIR / f"{name}.py", copy)
        link = encryption._resolve(copy)
        assert not link.available
        assert link.problem == (
            "brisart_security_primitives was loaded from 97_Encryption/Official/brisart_security_primitives.py, "
            "not from a copy outside this archive (Official)."
        )
        assert str(tmp_path) not in link.problem

    def test_a_library_without_the_required_formats_is_refused(self, monkeypatch):
        monkeypatch.setattr(encryption, "REQUIRED_FORMATS", (("aead", "SUITE_NAME", "SOME-OTHER-SUITE"),))
        link = encryption._resolve(encryption.ENCRYPTION_DIR)
        assert not link.available
        assert "brisart_security_aead.SUITE_NAME is 'BSR2-S64-SIV'" in link.problem
        assert "requires 'SOME-OTHER-SUITE'" in link.problem

    def test_require_raises_encryption_not_found_error_with_the_reason(self, monkeypatch):
        unavailable = encryption.EncryptionLink(available=False, location=encryption.ENCRYPTION_DIR, problem="gone")
        monkeypatch.setattr(encryption, "status", lambda: unavailable)
        with pytest.raises(EncryptionNotFoundError, match="^Encryption not found: gone$") as caught:
            encryption.require()
        assert isinstance(caught.value, EntitleError)

    def test_without_97_encryption_commands_that_need_none_still_work(self, tmp_path):
        lonely = tmp_path / "98_Tooling" / "Entitle"
        shutil.copytree(ENTITLE_ROOT, lonely, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))

        def run(*args):
            return subprocess.run(
                [sys.executable, str(lonely / "main.py"), *args], capture_output=True, text=True, timeout=120, cwd=tmp_path
            )

        version = run("--version")
        assert version.returncode == 0
        assert version.stdout.splitlines()[1].startswith("Encryption not found: 97_Encryption/Official was not found.")
        issued = run("issue", "--issuer", ISSUER, "--subject", SUBJECT, "--product", PRODUCT, "--entitlement-id", "e",
                     "--master-key", MASTER_KEY, "--output", "x.entitle")
        assert issued.returncode == 1 and issued.stdout == ""
        assert issued.stderr.startswith("Error: Encryption not found: ") and "Traceback" not in issued.stderr
        verified = run("verify", "--issuer", ISSUER, "--subject", SUBJECT, "--product", PRODUCT,
                       "--master-key", MASTER_KEY, "--file", str(LEGACY_ENTITLEMENT))
        assert verified.returncode == 1 and "DENIED" not in verified.stdout
        assert verified.stderr.startswith("Error: Encryption not found: ")
        identity = ["--issuer", ISSUER, "--subject", SUBJECT, "--product", PRODUCT, "--master-key", MASTER_KEY]
        migrated = run("migrate", *identity, "--file", str(LEGACY_ENTITLEMENT))
        assert migrated.returncode == 1 and migrated.stderr.startswith("Error: Encryption not found: ")
        deployed = run("track", "deploy", *identity, "--entitlement", str(LEGACY_ENTITLEMENT), "--host", "n1",
                       "--store", str(tmp_path / "deploy.log"))
        assert deployed.returncode == 1 and deployed.stderr.startswith("Error: Encryption not found: ")
        assert not (tmp_path / "deploy.log").exists()
        store = str(tmp_path / "records" / "r.log")
        assert run("track", "fork", "--product", "P", "--source-version", "1", "--fork-name", "f",
                   "--maintainer", "m", "--store", store).returncode == 0
        assert run("revoke", "revoke", "--entitlement-id", "e", "--store", store).returncode == 0
        report = run("report", "--store", store)
        assert report.returncode == 0 and "VERIFIED: hash chain intact across 2 records." in report.stdout
