"""
File: crypto/encryption.py

Purpose
-------
The one link between BrisartIdentityTools and BSR2
(``97_Encryption/Official`` in the Brisart Research Archive). Identity Tools
ships no cryptography of its own: every seal, open, key derivation, MAC, random
byte, key file, and archive comes from the linked BSR2 library,
located here and nowhere else. When that library is absent or incompatible the
application still starts, reports "Encryption not found", and refuses every
operation that needs encryption instead of falling back to anything weaker.

Public interface:
- ENCRYPTION_DIR -- Where BSR2 is expected:
  ``<archive root>/97_Encryption/Official``.
- REQUIRED_MODULES -- Every BSR2 library module; all are linked.
- REQUIRED_FORMATS -- The formats Identity Tools writes or must still read.
- class EncryptionLink -- Result of resolving the link: ``available``,
  ``location``, ``release``, ``problem``, and ``describe()``, a one-line
  summary: "Encryption: <release name> (<release>), from 97_Encryption/Official",
  for example "Encryption: BSR2 Alpha 4 (0.4.0-alpha), from 97_Encryption/Official"
  or "Encryption not found: <reason>". Paths are always shown relative to the
  archive folder, never as this machine's absolute location.
- status() -> EncryptionLink -- Resolve the link once per process and report
  it. Never raises.
- MIGRATION_NOTICE -- The message every CLI and GUI shows before migrating a
  store from the previous encryption to the current one.
- require() -> types.SimpleNamespace -- The linked library, one attribute per
  module (``primitives``, ``sponge``, ``entropy``, ``drbg``, ``envelope``,
  ``aead``, ``stream``, ``kdf``, ``keys``, ``recovery``, ``archive``,
  ``cli``, ``version``), or EncryptionNotFoundError when the link is
  unavailable.

Design notes:

BSR2's modules import each other by flat name
(``from brisart_security_primitives import ...``), so its directory goes on
``sys.path`` exactly once, here, and every Identity Tools caller goes through
``require()``. Callers resolve the library at call time, never at import time,
so every module in the application imports cleanly without encryption and only
the operation that actually needs it fails.

The library is handed out as modules rather than a flat list of names: callers
write ``bsr2.aead.seal`` or ``bsr2.kdf.derive_key``, which says which
BSR2 construction is in use at every call site.

Which module does which job in Identity Tools:
- aead (sealed format v3, BSR2-S64-SIV) -- every new sealed payload up to its
  16 MiB limit, and every payload the migration reseals (crypto/envelope.py).
- stream (BSR-STREAM-1) -- sealed payloads above that limit
  (crypto/envelope.py).
- envelope (legacy v2 JSON envelope) -- read-only, so data sealed before
  the encryption migration (Official 1.10.0, LTS-2028 1.4.0) still opens and
  can be migrated (crypto/envelope.py).
- kdf (BSR2-MHF-1) -- new keyring wrappers (crypto/keyring.py).
- primitives -- the legacy iterated KDF and keyed MAC, read-only, for keyrings
  and bound factors written before the encryption migration; hex encoding and constant-time
  comparison everywhere.
- sponge (BSR2-S64) -- new bound factors and keyring check values
  (crypto/factors.py, crypto/keyring.py).
- drbg, entropy -- the managed generator (crypto/rng.py), master keys, salts,
  recovery codes (crypto/keyring.py), and package content keys
  (packages/ciphers.py).
- cli, which drives keys, archive, and recovery -- Official's
  ``python cli.py encryption`` command. LTS-2028 links these four modules (the
  link checks the whole library) but uses none of them.

Resolution is lazy and cached: the first ``status()`` or ``require()`` call
performs it, and the result holds for the life of the process. Installing
BSR2 while the application runs requires a restart.

Communication / relationships
-----------------------------
Depends on (project modules):
- crypto.errors (crypto/errors.py)
Links to (BSR2, 97_Encryption/Official): every module in
REQUIRED_MODULES.
Standard library: dataclasses, functools, importlib, os, pathlib, sys, types.
Imported by:
- crypto/envelope.py, crypto/factors.py, crypto/keyring.py, crypto/rng.py
- packages/ciphers.py (content keys and text-derived master keys)
- packages/demo.py (demo passphrases)
- vault/app.py, biometrics/app.py, packages/main.py, gui/widgets/dialogs.py
  (MIGRATION_NOTICE)
Covered by tests: crypto/tests/test_encryption_link.py.

Settings / parameters
---------------------
- ARCHIVE_ROOT = Path(__file__).resolve().parents[3] -- the folder that holds
  95_Identity_Tools, wherever it is (a desktop folder, a drive, OneDrive).
- ENCRYPTION_DIR = ARCHIVE_ROOT / "97_Encryption" / "Official". The only
  requirement is that 95_Identity_Tools and 97_Encryption are together in the
  same folder; there is no override and no absolute path.
- REQUIRED_MODULES -- attribute name on the require() namespace -> BSR2 module name, for all thirteen library modules.
- MIGRATION_NOTICE -- user-facing text, worded for both the CLI question and
  the GUI pop-up; store-specific consequences (a new recovery code for
  keyrings) and button wording are added by the caller.
- REQUIRED_FORMATS -- (module, constant, expected value) checks:
  legacy envelope ``BSR2-ARX-SPONGE-ETM`` v2 (existing data), aead suite
  ``BSR2-S64-SIV`` format 3, stream format 1, kdf ``BSR2-MHF-1``. A linked
  library that does not provide all of them is reported as unavailable rather
  than used.

Edge cases
----------
- ENCRYPTION_DIR missing: status().available is False, and the problem says
  to keep 95_Identity_Tools and 97_Encryption together in the same folder.
- Every message shows paths relative to ARCHIVE_ROOT; a copy loaded from
  outside the archive is named by file name only.
- A required module file missing: unavailable, problem names the file.
- A required module fails to import: unavailable, problem carries the error.
- A ``brisart_security_*`` module already imported from somewhere other than
  ENCRYPTION_DIR: unavailable, problem names both locations. Identity Tools
  never runs against an unlinked copy.
- A format check fails: unavailable, problem names the constant, what was
  found, and what is required.
- require() raises EncryptionNotFoundError carrying describe() whenever the
  link is unavailable.

Known limitations
-----------------
- The location is fixed relative to this file: 95_Identity_Tools moved away
  from 97_Encryption (for example a standalone copy of this application
  folder) always reports Encryption not found.
- Formats are checked, release is not pinned: any BSR2 release
  that still provides the formats above links.
- BSR2 is custom research cryptography with no independent review (see
  docs/SECURITY.md); linking it does not make it audited.

Examples
--------
::

    from crypto import encryption
    encryption.status().describe()
    bsr2 = encryption.require()
    sealed = bsr2.aead.seal(key, plaintext, context, rng=rng, padding="block")
"""

import importlib
import os
import sys
import types
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

from crypto.errors import EncryptionNotFoundError

# The folder that holds 95_Identity_Tools: crypto/ -> <line>/ -> 95_Identity_Tools/
# -> here. 97_Encryption must sit in this same folder, wherever it is.
ARCHIVE_ROOT = Path(__file__).resolve().parents[3]
ENCRYPTION_DIR = ARCHIVE_ROOT / "97_Encryption" / "Official"
_KEEP_TOGETHER = (
    "Keep the 95_Identity_Tools and 97_Encryption folders together in the "
    "same folder."
)

MIGRATION_NOTICE = (
    "This update moves to the current BSR2 encryption from 97_Encryption. "
    "This data still uses the previous encryption (BSR2 Alpha 3), which "
    "this version can still read for now but which will be removed entirely "
    "in a future update.\n\n"
    "Migrating re-encrypts every encrypted item with the new encryption and "
    "saves it in place. Migrated data cannot be opened by older versions "
    "(any LTS-2028 1.3.x release, or Official 1.9.2 and earlier), so keep a "
    "backup if you may need them.\n\n"
    "If you do not migrate now, the previous encryption keeps working and you "
    "will be asked again next time."
)

# require() attribute -> BSR2 module. Ordered so each module's
# own flat imports are already resolved when it loads.
REQUIRED_MODULES = {
    "primitives": "brisart_security_primitives",
    "sponge": "brisart_security_sponge",
    "entropy": "brisart_security_entropy",
    "drbg": "brisart_security_drbg",
    "envelope": "brisart_security_envelope",
    "aead": "brisart_security_aead",
    "stream": "brisart_security_stream",
    "kdf": "brisart_security_kdf",
    "keys": "brisart_security_keys",
    "recovery": "brisart_security_recovery",
    "archive": "brisart_security_archive",
    "cli": "brisart_security_cli",
    "version": "brisart_security_version",
}

REQUIRED_FORMATS = (
    ("envelope", "ALGORITHM", "BSR2-ARX-SPONGE-ETM"),
    ("envelope", "VERSION", 2),
    ("aead", "SUITE_NAME", "BSR2-S64-SIV"),
    ("aead", "FORMAT_VERSION", 3),
    ("stream", "FORMAT_VERSION", 1),
    ("kdf", "KDF_NAME", "BSR2-MHF-1"),
)


@dataclass(frozen=True)
class EncryptionLink:
    """How the link to BSR2 resolved in this process."""

    available: bool
    location: Path
    release: Optional[str] = None
    problem: Optional[str] = None
    library: Optional[types.SimpleNamespace] = field(
        default=None, repr=False, compare=False
    )

    def describe(self) -> str:
        if self.available:
            return f"Encryption: {self.release}, from {_shown(self.location)}"
        return f"Encryption not found: {self.problem}"


def _shown(path) -> str:
    """``path`` as the user should see it: relative to ARCHIVE_ROOT, never the
    absolute location of the archive on this machine."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ARCHIVE_ROOT).as_posix()
    except ValueError:
        return f"a copy outside this archive ({resolved.name})"


def _unavailable(problem: str) -> EncryptionLink:
    # Import errors can quote absolute paths; strip the archive's own location.
    problem = problem.replace(str(ARCHIVE_ROOT) + os.sep, "").replace(str(ARCHIVE_ROOT), ".")
    return EncryptionLink(available=False, location=ENCRYPTION_DIR, problem=problem)


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
            return _unavailable(
                f"{name} was loaded from {_shown(origin)}, not from {_shown(directory)}."
            )
        modules[attribute] = module

    for attribute, constant, required in REQUIRED_FORMATS:
        found = getattr(modules[attribute], constant, None)
        if found != required:
            return _unavailable(
                f"linked {REQUIRED_MODULES[attribute]}.{constant} is {found!r}; "
                f"Identity Tools requires {required!r}."
            )

    version = modules["version"]
    release = f"{version.RELEASE_NAME} ({version.PROJECT_RELEASE})"
    return EncryptionLink(
        available=True,
        location=directory,
        release=release,
        library=types.SimpleNamespace(**modules),
    )


@lru_cache(maxsize=1)
def status() -> EncryptionLink:
    """Resolve the link to BSR2 once and report the result."""
    return _resolve(ENCRYPTION_DIR)


def require() -> types.SimpleNamespace:
    """Return the linked BSR2 library or raise
    EncryptionNotFoundError."""
    link = status()
    if not link.available:
        raise EncryptionNotFoundError(link.describe())
    return link.library


__all__ = [
    "ENCRYPTION_DIR",
    "MIGRATION_NOTICE",
    "REQUIRED_FORMATS",
    "REQUIRED_MODULES",
    "EncryptionLink",
    "require",
    "status",
]
