"""Purpose
-------
Own the encrypted-at-rest BrisartAI SQLite library lifecycle.

The Official 97_Encryption archive API encrypts the database image. A temporary
private working database is unlocked only while BrisartAI is running.

Communication / relationships
-----------------------------
Desktop startup decides whether to migrate. BrisartService calls checkpoint
after mutations and closes the vault after closing every SQLite connection.

Windows DPAPI protects the generated archive passphrase for automatic unlock.
The passphrase is never stored in settings or in the encrypted container.

Settings / parameters
---------------------
The encrypted container is the database path plus `.bsa`; the DPAPI key is the
same path plus `.key`. BRISART_ENCRYPTION locates 97_Encryption/v4.

The live database has a 5 GiB process-safety ceiling, separate from the
smaller limits used for portable backup exports. Migration and persistence
accept progress callbacks. Runtime callers use the
working_path property and do not handle archive internals.

Edge cases
----------
Migration verifies encrypted output before removing plaintext. A recovery copy
and marker survive interruption and are reconciled on the next launch.

An archive or key without its counterpart is an error. Replacing the encrypted
container is atomic on the same filesystem.

Known limitations
-----------------
Automatic unlock is Windows-only because it relies on CurrentUser DPAPI. While
running, a plaintext SQLite working copy exists in a private temporary folder.

97_Encryption remains an external dependency. This layer does not encrypt the
original imported files; it encrypts their indexed copies, notes and history.

Examples
--------
manager = EncryptedLibrary(path)
working = manager.unlock()
manager.checkpoint()
manager.close()
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import secrets
import shutil
import tempfile
import threading

from brisart_ai.core.library_backup import (_archive_api, _check_index, _snapshot,
                                             INDEX_FILENAME)


LIVE_LIBRARY_LIMIT = 5 * 1024**3


class EncryptedLibraryError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise EncryptedLibraryError("Automatic vault unlock requires Windows DPAPI.")
    source_buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _Blob()
    function = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    args = ((ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)) if decrypt else
            (ctypes.byref(source), "BrisartAI encrypted library", None, None, None, 0, ctypes.byref(target)))
    if not function(*args):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


class EncryptedLibrary:
    def __init__(self, database, *, api=None, protect=None, unprotect=None):
        self.database = Path(database).resolve()
        self.container = self.database.with_suffix(self.database.suffix + ".bsa")
        self.key_file = self.database.with_suffix(self.database.suffix + ".key")
        self.marker = self.database.with_suffix(self.database.suffix + ".migration")
        self.recovery = self.database.with_suffix(self.database.suffix + ".migration-recovery")
        self.api = api
        self.protect = protect or (lambda value: _dpapi(value))
        self.unprotect = unprotect or (lambda value: _dpapi(value, True))
        self._secret = None
        self._temporary = None
        self._lock = threading.RLock()

    @property
    def enabled(self):
        return self.container.is_file() and self.key_file.is_file()

    @property
    def working_path(self):
        return str(self._temporary / INDEX_FILENAME) if self._temporary else str(self.database)

    def estimate_seconds(self):
        size = self.database.stat().st_size if self.database.exists() else 0
        # Published BSR-STREAM-1 release-machine benchmark: approximately 27 KiB/s.
        # Archive compression and verification make this a reference projection,
        # not a measured ETA for the archive API or the user's hardware.
        return int(size / (27 * 1024)) if size else 0

    def _backend(self):
        return self.api or _archive_api()

    def _read_secret(self):
        if not self.key_file.is_file():
            raise EncryptedLibraryError("The encrypted library key is missing.")
        return self.unprotect(base64.b64decode(self.key_file.read_bytes())).decode("ascii")

    def _build(self, image, secret):
        api = self._backend()
        blob = api.build_archive([(INDEX_FILENAME, image, 0, "")], password=secret,
                                 compression="deflate")
        reader = api.ArchiveReader(blob, password=secret, max_unpacked_bytes=LIVE_LIBRARY_LIMIT,
                                   max_kdf_memory_blocks=api.KdfParams().memory_blocks)
        checked = reader.read(INDEX_FILENAME)
        if checked != image:
            raise EncryptedLibraryError("Encrypted library verification did not reproduce the snapshot.")
        return blob

    def _publish(self, blob, progress=None):
        self.container.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".brisart-vault-", dir=self.container.parent,
                                         delete=False) as stream:
            staged = Path(stream.name)
            if progress is None:
                stream.write(blob)
            else:
                total = len(blob)
                written = 0
                for offset in range(0, total, 1024 * 1024):
                    part = blob[offset:offset + 1024 * 1024]
                    stream.write(part)
                    written += len(part)
                    progress("publish_bytes", written, total)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(staged, self.container)

    def migrate(self, progress=lambda stage, completed, total: None):
        with self._lock:
            if self.enabled:
                return self.unlock(progress)
            if not self.database.is_file():
                raise EncryptedLibraryError("The plaintext library does not exist.")
            if self.container.exists() or self.key_file.exists():
                raise EncryptedLibraryError("Incomplete encrypted-library files require recovery.")
            progress("snapshot", 0, 4)
            image = _snapshot(self.database, max_bytes=LIVE_LIBRARY_LIMIT)
            progress("snapshot_bytes", len(image), len(image))
            secret = secrets.token_urlsafe(48)
            progress("encrypt", 1, 4)
            progress("encrypt_bytes", 0, len(image))
            blob = self._build(image, secret)
            progress("encrypt_bytes", len(image), len(image))
            protected = base64.b64encode(self.protect(secret.encode("ascii")))
            self.marker.write_text("migrating", encoding="ascii")
            self.recovery.unlink(missing_ok=True)
            os.replace(self.database, self.recovery)
            try:
                progress("publish", 2, 4)
                self._publish(blob, progress)
                self.key_file.write_bytes(protected)
                os.chmod(self.key_file, 0o600)
                self._secret = secret
                progress("unlock", 3, 4)
                path = self.unlock(progress)
            except BaseException:
                if not self.database.exists() and self.recovery.exists():
                    os.replace(self.recovery, self.database)
                self.container.unlink(missing_ok=True); self.key_file.unlink(missing_ok=True)
                self.marker.unlink(missing_ok=True)
                raise
            self.recovery.unlink(missing_ok=True); self.marker.unlink(missing_ok=True)
            progress("complete", 4, 4)
            return path

    def unlock(self, progress=lambda stage, completed, total: None):
        with self._lock:
            if self.marker.exists() and self.recovery.exists() and not self.enabled:
                os.replace(self.recovery, self.database); self.marker.unlink(missing_ok=True)
                raise EncryptedLibraryError("Interrupted migration was rolled back; start encryption again.")
            if not self.enabled:
                raise EncryptedLibraryError("Encrypted library and protected key are both required.")
            secret = self._secret or self._read_secret()
            api = self._backend(); blob = self.container.read_bytes()
            reader = api.ArchiveReader(blob, password=secret, max_unpacked_bytes=LIVE_LIBRARY_LIMIT,
                                       max_kdf_memory_blocks=api.KdfParams().memory_blocks)
            image = reader.read(INDEX_FILENAME)
            temporary = Path(tempfile.mkdtemp(prefix="BrisartAI-unlocked-"))
            os.chmod(temporary, 0o700)
            path = temporary / INDEX_FILENAME
            path.write_bytes(image); os.chmod(path, 0o600)
            import sqlite3
            with sqlite3.connect(path) as connection:
                _check_index(connection)
            self._secret, self._temporary = secret, temporary
            progress("unlocked", 1, 1)
            return str(path)

    def checkpoint(self):
        with self._lock:
            if not self._temporary:
                return
            self._publish(self._build(_snapshot(self.working_path, max_bytes=LIVE_LIBRARY_LIMIT), self._secret))

    def close(self):
        with self._lock:
            if self._temporary:
                self.checkpoint()
                shutil.rmtree(self._temporary, ignore_errors=True)
                self._temporary = None
            self._secret = None

