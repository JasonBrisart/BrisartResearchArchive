"""
File: entitle/encryption.py

Purpose
-------
Be Entitle's only link to BSR2, the archive's shared encryption in 97_Encryption/Official.
  Entitle ships no cryptography of its own: this file finds that folder, checks it, imports it
  once, and hands the modules to the one caller that seals and opens entitlement files. When the
  library is missing or unsuitable, Entitle still starts and reports "Encryption not found"
  instead of falling back to anything weaker.

Communication / relationships
-----------------------------
Imports entitle/common.py (EntitleError) and the standard library. Links, on first use, these
  97_Encryption/Official modules: brisart_security_aead (the current sealed format),
  brisart_security_envelope (the previous format, read only), brisart_security_drbg,
  brisart_security_version, and the three they import, brisart_security_primitives,
  brisart_security_sponge and brisart_security_entropy. Imported by entitle/entitlements.py
  (require, which is the only place the library is used) and cli.py (status, for --version).
  Covered by tests/test_encryption.py.

Settings / parameters
---------------------
ARCHIVE_ROOT is the folder holding 98_Tooling (three levels above this file) and
  ENCRYPTION_DIR is ARCHIVE_ROOT/97_Encryption/Official. The only requirement is that
  98_Tooling and 97_Encryption sit in the same folder, wherever that is; there is no override
  and no absolute path. REQUIRED_MODULES maps each require() attribute (primitives, sponge,
  entropy, drbg, envelope, aead, version) to its module, in import order. REQUIRED_FORMATS
  lists the constants a linked library must carry: aead suite BSR2-S64-SIV format 3, and the
  envelope BSR2-ARX-SPONGE-ETM version 2 used to read files written before Entitle 0.5.0.

Edge cases
----------
Resolution is lazy and cached for the life of the process: nothing from 97_Encryption is
  imported until status() or require() is first called, so every Entitle module imports
  without it, and installing it while Entitle runs needs a restart. status() never raises.
  require() raises EncryptionNotFoundError with the one-line reason. The link is unavailable
  when the folder is missing (the message says to keep 98_Tooling and 97_Encryption together),
  a module file is missing, a module fails to import, a brisart_security_* module was already
  imported from somewhere other than ENCRYPTION_DIR (Entitle never runs against an unlinked
  copy), or a required format constant differs. An Entitle folder placed so close to the top of
  a drive that there is no folder three levels up (directly under the drive root) has
  ARCHIVE_ROOT at the top of the drive and reports the same "was not found" message instead of
  failing to import.
  Every message names paths relative to the archive and never this machine's absolute location,
  including paths quoted inside an exception's repr, where Windows backslashes are doubled.
  ENCRYPTION_DIR is put on sys.path once, here, because BSR2's modules import each other by flat
  name.

Known limitations
-----------------
The release is not pinned: any BSR2 release that still provides the required formats links.
  The location is fixed relative to this file, so a copy of the Entitle folder moved away from
  97_Encryption always reports Encryption not found. BSR2 is experimental research cryptography
  with no independent review; linking it does not make it audited.

Examples
--------
From the directory containing run.py:

    from entitle import encryption

    print(encryption.status().describe())
    # Encryption: BSR2 Alpha 4 (0.4.0-alpha), from 97_Encryption/Official
    bsr2 = encryption.require()
    assert bsr2.aead.SUITE_NAME == "BSR2-S64-SIV"
"""

import importlib
import sys
import types
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePath
from typing import Optional

from .common import EntitleError


def _archive_root(this_file: PurePath) -> PurePath:
    """The folder holding 98_Tooling, given this file's resolved location.

    entitle/ -> Entitle/ -> 98_Tooling/ -> the archive folder. A copy placed so shallowly that
    there is no third parent gets the top of the drive, which is simply "not the archive".
    """
    parents = this_file.parents
    return parents[3] if len(parents) > 3 else parents[len(parents) - 1]


ARCHIVE_ROOT = Path(_archive_root(Path(__file__).resolve()))
ENCRYPTION_DIR = ARCHIVE_ROOT / "97_Encryption" / "Official"
_KEEP_TOGETHER = "Keep the 98_Tooling and 97_Encryption folders together in the same folder."

# require() attribute -> BSR2 module. Ordered so each module's own flat imports resolve first.
REQUIRED_MODULES = {
    "primitives": "brisart_security_primitives",
    "sponge": "brisart_security_sponge",
    "entropy": "brisart_security_entropy",
    "drbg": "brisart_security_drbg",
    "envelope": "brisart_security_envelope",
    "aead": "brisart_security_aead",
    "version": "brisart_security_version",
}

# (require() attribute, constant, required value) checks.
REQUIRED_FORMATS = (
    ("envelope", "ALGORITHM", "BSR2-ARX-SPONGE-ETM"),
    ("envelope", "VERSION", 2),
    ("aead", "SUITE_NAME", "BSR2-S64-SIV"),
    ("aead", "FORMAT_VERSION", 3),
)


class EncryptionNotFoundError(EntitleError):
    """Raised when the link to 97_Encryption/Official is unavailable."""


@dataclass(frozen=True)
class EncryptionLink:
    """How the link to BSR2 resolved in this process."""

    available: bool
    location: Path
    release: Optional[str] = None
    problem: Optional[str] = None
    library: Optional[types.SimpleNamespace] = field(default=None, repr=False, compare=False)

    def describe(self) -> str:
        if self.available:
            return f"Encryption: {self.release}, from {_shown(self.location)}"
        return f"Encryption not found: {self.problem}"


def _shown(path) -> str:
    """``path`` as the user should see it: relative to ARCHIVE_ROOT, never absolute."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ARCHIVE_ROOT).as_posix()
    except ValueError:
        return f"a copy outside this archive ({resolved.name})"


def _without_location(text: str, root: PurePath) -> str:
    """``text`` with every spelling of ``root`` removed, so no message names this machine.

    An exception's repr doubles Windows backslashes (C:\\\\Users\\\\...), so the plain, forward-slash
    and escaped spellings are all removed. A root with no name is the top of a drive; removing "C:\\"
    or "/" would mangle the text, so it is left alone.
    """
    if not root.name:
        return text
    spellings = {str(root), root.as_posix(), str(root).replace("\\", "\\\\")}
    for spelling in sorted(spellings, key=len, reverse=True):
        for separator in ("\\\\", "\\", "/"):
            text = text.replace(spelling + separator, "")
        text = text.replace(spelling, ".")
    return text


def _unavailable(problem: str) -> EncryptionLink:
    return EncryptionLink(
        available=False, location=ENCRYPTION_DIR, problem=_without_location(problem, ARCHIVE_ROOT)
    )


def _resolve(directory: Path) -> EncryptionLink:
    if not directory.is_dir():
        return _unavailable(f"{_shown(directory)} was not found. {_KEEP_TOGETHER}")
    for name in REQUIRED_MODULES.values():
        if not (directory / f"{name}.py").is_file():
            return _unavailable(f"{_shown(directory)} is missing {name}.py.")
    path_entry = str(directory)
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)
    modules = {}
    for attribute, name in REQUIRED_MODULES.items():
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # any failure means the link is unusable
            return _unavailable(f"{name} failed to import: {exc!r}.")
        origin = Path(getattr(module, "__file__", "") or "").resolve()
        if origin.parent != directory.resolve():
            return _unavailable(f"{name} was loaded from {_shown(origin)}, not from {_shown(directory)}.")
        modules[attribute] = module
    for attribute, constant, required in REQUIRED_FORMATS:
        found = getattr(modules[attribute], constant, None)
        if found != required:
            return _unavailable(
                f"linked {REQUIRED_MODULES[attribute]}.{constant} is {found!r}; Entitle requires {required!r}."
            )
    version = modules["version"]
    return EncryptionLink(
        available=True,
        location=directory,
        release=f"{version.RELEASE_NAME} ({version.PROJECT_RELEASE})",
        library=types.SimpleNamespace(**modules),
    )


@lru_cache(maxsize=1)
def status() -> EncryptionLink:
    """Resolve the link to BSR2 once per process and report the result. Never raises."""
    return _resolve(ENCRYPTION_DIR)


def require() -> types.SimpleNamespace:
    """Return the linked BSR2 library, or raise EncryptionNotFoundError."""
    link = status()
    if not link.available:
        raise EncryptionNotFoundError(link.describe())
    return link.library
