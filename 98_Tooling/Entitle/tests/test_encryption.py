"""
File: tests/test_encryption.py

Purpose
-------
Verify entitle/encryption.py, Entitle's link to BSR2 in 97_Encryption/Official: that it resolves
  to the archive's own 97_Encryption/Official and nowhere else, that every linked module comes
  from that folder, that Entitle keeps no copy of any brisart_security_* module, that a missing,
  incomplete, foreign or incompatible library is reported as "Encryption not found" with a
  reason that never shows this machine's path (including Windows paths, whose backslashes an
  exception's repr doubles), that an Entitle folder too close to the top of a drive still starts
  and reports the same message, and that without 97_Encryption Entitle still runs every command
  that needs no encryption.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError) and entitle/encryption.py, and uses tests/support.py
  (identity, key, LEGACY_ENTITLEMENT, ENTITLE_ROOT, run_entitle). The last test copies the
  Entitle folder into a temporary 98_Tooling with no 97_Encryption beside it and runs run.py
  there as real processes. Sealing and opening files are tested in tests/test_entitlements.py.
  Run by pytest; nothing imports it.

Settings / parameters
---------------------
Library-resolution tests call encryption._resolve with a folder of their choosing; the one that
  imports a copy of the library restores sys.path afterwards. The location tests use pure
  (Posix and Windows) paths, so they need no particular operating system. The process test has a
  120-second limit per command.

Edge cases
----------
Covers a missing folder, a folder missing a module file, a copy of the library outside the
  archive (refused even when its files are identical), a required format constant that does not
  match, require() raising EncryptionNotFoundError, the archive root of Posix and Windows paths
  of every depth (including directly under the drive root), a root with no name left alone when
  scrubbing messages, and, in the process test, issue, verify, migrate and track deploy failing
  with one "Encryption not found" line and no traceback while track fork, revoke and report
  succeed.

Known limitations
-----------------
Does not test BSR2 itself; its tests live in 97_Encryption/Official/tests. Linking a different
  BSR2 release is covered only through the format checks, not by running another release. The
  process test takes a few seconds. An Entitle folder directly under a drive root is tested
  through the root calculation, not by installing there.

Examples
--------
From the directory containing run.py:

    python -m pytest tests/test_encryption.py
"""

import shutil
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from entitle import encryption
from entitle.common import EntitleError
from entitle.encryption import EncryptionNotFoundError
from support import ENTITLE_ROOT, ISSUER, LEGACY_ENTITLEMENT, MASTER_KEY, PRODUCT, SUBJECT, run_entitle


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


class TestWhereTheArchiveIs:
    def test_the_archive_is_three_levels_above_this_file(self):
        assert encryption._archive_root(PurePosixPath("/data/archive/98_Tooling/Entitle/entitle/encryption.py")) == (
            PurePosixPath("/data/archive")
        )
        assert encryption._archive_root(PureWindowsPath(r"C:\Users\Jason\Archive\98_Tooling\Entitle\entitle\encryption.py")) == (
            PureWindowsPath(r"C:\Users\Jason\Archive")
        )

    @pytest.mark.parametrize("location,top", [
        (PurePosixPath("/Entitle/entitle/encryption.py"), PurePosixPath("/")),
        (PurePosixPath("/opt/Entitle/entitle/encryption.py"), PurePosixPath("/")),
        (PureWindowsPath(r"C:\Entitle\entitle\encryption.py"), PureWindowsPath("C:/")),
        (PureWindowsPath(r"C:\Tools\Entitle\entitle\encryption.py"), PureWindowsPath("C:/")),
    ])
    def test_an_entitle_folder_near_the_top_of_a_drive_gets_the_drive_root_not_an_index_error(self, location, top):
        # Before 0.6.0 this was parents[3], an IndexError at import for C:\Entitle (three parents),
        # so every command crashed with a traceback instead of saying "Encryption not found".
        assert encryption._archive_root(location) == top

    def test_a_drive_root_archive_reports_not_found_with_the_fix(self, monkeypatch):
        monkeypatch.setattr(encryption, "ARCHIVE_ROOT", Path("/"))
        monkeypatch.setattr(encryption, "ENCRYPTION_DIR", Path("/97_Encryption_that_does_not_exist/Official"))
        link = encryption._resolve(encryption.ENCRYPTION_DIR)
        assert not link.available and "was not found. Keep the 98_Tooling and 97_Encryption folders together" in link.problem
        assert link.problem.startswith("97_Encryption_that_does_not_exist/Official")


class TestMessagesNeverNameThisMachine:
    WINDOWS_ROOT = PureWindowsPath(r"C:\Users\Jason\OneDrive\Documents\GitHub\BrisartResearchArchive")

    def test_a_windows_path_inside_an_exceptions_repr_is_removed(self):
        # repr() doubles every backslash, which the old scrubbing (single backslashes) never matched.
        located = str(self.WINDOWS_ROOT) + r"\97_Encryption\Official\brisart_security_aead.py"
        text = f"brisart_security_aead failed to import: {SyntaxError('invalid syntax', (located, 12, 5, 'x = (', 12, 6))!r}."
        assert "Jason" in text and "OneDrive" in text  # the repr really does carry the path
        cleaned = encryption._without_location(text, self.WINDOWS_ROOT)
        assert "Jason" not in cleaned and "OneDrive" not in cleaned and "C:" not in cleaned
        assert r"97_Encryption\\Official\\brisart_security_aead.py" in cleaned

    def test_plain_and_forward_slash_spellings_are_removed_too(self):
        plain = str(self.WINDOWS_ROOT) + r"\97_Encryption\Official"
        slashes = self.WINDOWS_ROOT.as_posix() + "/97_Encryption/Official"
        assert encryption._without_location(f"missing {plain}", self.WINDOWS_ROOT) == r"missing 97_Encryption\Official"
        assert encryption._without_location(f"missing {slashes}", self.WINDOWS_ROOT) == "missing 97_Encryption/Official"

    def test_a_posix_path_is_removed_and_a_bare_root_becomes_a_dot(self):
        root = PurePosixPath("/home/jason/archive")
        assert encryption._without_location("no module in /home/jason/archive/97_Encryption", root) == "no module in 97_Encryption"
        assert encryption._without_location("under /home/jason/archive now", root) == "under . now"

    def test_a_drive_root_is_left_alone_rather_than_mangling_every_slash(self):
        assert encryption._without_location("a/b and /c", PurePosixPath("/")) == "a/b and /c"
        assert encryption._without_location(r"C:\x and D:\y", PureWindowsPath("C:/")) == r"C:\x and D:\y"

    def test_unavailable_reasons_never_contain_this_machines_archive_path(self):
        located = str(encryption.ARCHIVE_ROOT / "97_Encryption" / "Official" / "brisart_security_aead.py")
        link = encryption._unavailable(f"failed: {SyntaxError('bad', (located, 1, 1, 'x'))!r}")
        assert str(encryption.ARCHIVE_ROOT) not in link.problem and "97_Encryption" in link.problem


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
            return run_entitle(*args, cwd=tmp_path, root=lonely)

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
