"""Purpose
-------
Verify encrypted-library migration, automatic unlock, checkpoints and recovery.

Communication / relationships
-----------------------------
Uses the real SQLite index with an injected deterministic archive facade and
key protector. Production continues to call 97_Encryption/v4 and DPAPI.

Settings / parameters
---------------------
All work is isolated under pytest temporary directories.

Edge cases
----------
Covers new imports after migration and interrupted migration rollback.

Known limitations
-----------------
Does not validate the external cryptography or Windows DPAPI implementation.

Examples
--------
python -m pytest -q brisart_ai/core/tests/test_encrypted_library.py
"""

import hashlib
import hmac
import json
from pathlib import Path
import types
import zlib

import pytest

from brisart_ai.core.encrypted_library import EncryptedLibrary, EncryptedLibraryError
from brisart_ai.knowledge.index import Index


class FakeReader:
    def __init__(self, blob, password, **_):
        payload, tag = blob[:-32], blob[-32:]
        key = hashlib.sha256(password.encode()).digest()
        if not hmac.compare_digest(tag, hmac.new(key, payload, hashlib.sha256).digest()):
            raise ValueError("bad authentication")
        self.members = json.loads(zlib.decompress(bytes(b ^ key[i % len(key)] for i, b in enumerate(payload))))

    def read(self, name):
        return bytes.fromhex(self.members[name])


class FakeApi:
    ArchiveReader = FakeReader
    KdfParams = lambda self=None: types.SimpleNamespace(memory_blocks=1)

    @staticmethod
    def build_archive(members, password, compression):
        key = hashlib.sha256(password.encode()).digest()
        raw = zlib.compress(json.dumps({name: data.hex() for name, data, _, _ in members}).encode())
        payload = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return payload + hmac.new(key, payload, hashlib.sha256).digest()


def manager(path):
    return EncryptedLibrary(path, api=FakeApi(), protect=lambda b: b[::-1], unprotect=lambda b: b[::-1])


def test_migrate_unlock_and_encrypt_future_imports(tmp_path):
    db = tmp_path / "library.sqlite3"
    with Index(str(db)) as index:
        index.add_source("file", "before.txt", "Before", "existing indexed text")
    stages = []
    vault = manager(db)
    working = vault.migrate(lambda *event: stages.append(event))
    assert not db.exists()
    assert vault.container.is_file() and vault.key_file.is_file()
    assert stages[-1] == ("complete", 4, 4)
    with Index(working) as index:
        index.add_source("file", "after.txt", "After", "new encrypted import")
    vault.checkpoint()
    first_ciphertext = vault.container.read_bytes()
    assert b"new encrypted import" not in first_ciphertext
    vault.close()
    assert not Path(working).exists()

    reopened = manager(db)
    unlocked = reopened.unlock()
    with Index(unlocked) as index:
        locations = {row[3] for row in index.list_sources()}
    assert locations == {"before.txt", "after.txt"}
    reopened.close()


def test_interrupted_migration_restores_plaintext(tmp_path):
    db = tmp_path / "library.sqlite3"
    with Index(str(db)) as index:
        index.add_source("file", "safe.txt", "Safe", "recover me")
    vault = manager(db)
    db.replace(vault.recovery)
    vault.marker.write_text("migrating")
    with pytest.raises(EncryptedLibraryError, match="rolled back"):
        vault.unlock()
    assert db.is_file() and not vault.recovery.exists() and not vault.marker.exists()
    with Index(str(db)) as index:
        assert index.source_count() == 1


def test_snapshot_accepts_database_larger_than_legacy_backup_cap(tmp_path, monkeypatch):
    from brisart_ai.core import encrypted_library as encrypted

    db = tmp_path / "large.sqlite3"
    db.write_bytes(b"not opened because snapshot is intercepted")
    seen = []
    monkeypatch.setattr(encrypted, "_snapshot", lambda path, *, max_bytes: seen.append(max_bytes) or b"sqlite image")
    vault = EncryptedLibrary(db, api=FakeApi(), protect=lambda b: b[::-1], unprotect=lambda b: b[::-1])
    monkeypatch.setattr(vault, "_build", lambda image, secret: b"encrypted")
    monkeypatch.setattr(vault, "unlock", lambda progress: "working.sqlite3")
    vault.migrate()
    assert seen == [encrypted.LIVE_LIBRARY_LIMIT]
    assert encrypted.LIVE_LIBRARY_LIMIT == 5 * 1024**3

