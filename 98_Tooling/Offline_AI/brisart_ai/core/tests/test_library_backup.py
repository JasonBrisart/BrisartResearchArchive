"""Purpose
-------
Exercise encrypted library snapshots against the real Official archive API.

Communication / relationships
-----------------------------
Uses an isolated SQLite WAL database and the configured Official module tree.

Settings / parameters
---------------------
BRISART_ENCRYPTION selects the implementation. All credentials are test values.

Edge cases
----------
Covers WAL snapshots, restored files, rejected archives and write cleanup.

Known limitations
-----------------
Does not validate Windows filesystems or audit the cryptographic construction.

Examples
--------
python -m pytest brisart_ai/core/tests/test_library_backup.py
"""

from contextlib import closing
import sqlite3

import pytest

from brisart_ai.core.library_backup import BackupError, _archive_api, create_backup, restore_backup, verify_backup
from brisart_ai.state import INDEX_FILENAME, SETTINGS_FILENAME


def test_library_round_trip_and_rejections(tmp_path):
    try:
        _archive_api()
    except BackupError as exc:
        import os
        if os.environ.get("BRISART_ENCRYPTION"):
            raise
        pytest.skip(str(exc))
    db = tmp_path / "live.sqlite3"
    settings = tmp_path / "settings.json"
    output = tmp_path / "test.bsa"
    password = "integration fixture not a production credential"
    settings.write_text('{"fixture":"private-settings"}', encoding="utf-8")
    with closing(sqlite3.connect(db)) as source:
        source.execute("PRAGMA journal_mode=WAL")
        source.executescript("CREATE TABLE sources(text); CREATE TABLE terms(term);"
                             "CREATE TABLE notes(body); CREATE TABLE turns(query);")
        source.execute("INSERT INTO sources VALUES ('private-source')")
        source.execute("INSERT INTO notes VALUES ('private-note')")
        source.execute("INSERT INTO turns VALUES ('private-query')")
        source.commit()
        create_backup(db, settings, output, password)
        assert source.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert source.execute("SELECT text FROM sources").fetchone() == ("private-source",)
    verify_backup(output, password)
    blob = output.read_bytes()
    assert b"private-source" not in blob and b"private-settings" not in blob
    recovery = tmp_path / "recovered"
    restore_backup(output, recovery, password)
    assert (recovery / SETTINGS_FILENAME).read_bytes() == settings.read_bytes()
    assert {p.name for p in recovery.iterdir()} == {INDEX_FILENAME, SETTINGS_FILENAME}
    with closing(sqlite3.connect((recovery / INDEX_FILENAME).as_uri() + "?mode=ro", uri=True)) as restored:
        assert restored.execute("SELECT text FROM sources").fetchone() == ("private-source",)
        assert restored.execute("SELECT body FROM notes").fetchone() == ("private-note",)
        assert restored.execute("SELECT query FROM turns").fetchone() == ("private-query",)
    before = (recovery / INDEX_FILENAME).read_bytes()
    with pytest.raises(BackupError, match="restore destination already exists"):
        restore_backup(output, recovery, password)
    assert (recovery / INDEX_FILENAME).read_bytes() == before
    with pytest.raises(BackupError, match="destination already exists"):
        create_backup(db, settings, output, password)
    assert output.read_bytes() == blob
    with pytest.raises(BackupError, match="authenticate"):
        restore_backup(output, tmp_path / "rejected", "wrong passphrase")
    assert not (tmp_path / "rejected").exists()
    output.write_bytes(blob[:-1])
    with pytest.raises(BackupError, match="authenticate"):
        restore_backup(output, tmp_path / "rejected", password)
    assert not (tmp_path / "rejected").exists()
    with pytest.raises(sqlite3.OperationalError):
        create_backup(tmp_path / "missing.db", settings, tmp_path / "absent.bsa", password)
    assert not (tmp_path / "missing.db").exists()
    assert not (tmp_path / "absent.bsa").exists()



def test_restore_cleans_up_after_second_member_cannot_sync(tmp_path, monkeypatch):
    from brisart_ai.core import library_backup as backup

    monkeypatch.setattr(backup, "_read_backup", lambda *args: {
        INDEX_FILENAME: b"fixture database", SETTINGS_FILENAME: b"{}",
    })
    flushed = []

    def fail_second_sync(fd):
        flushed.append(fd)
        if len(flushed) == 2:
            raise OSError("simulated write failure")

    monkeypatch.setattr(backup.os, "fsync", fail_second_sync)
    dest = tmp_path / "recovery"
    with pytest.raises(OSError, match="simulated write failure"):
        restore_backup(tmp_path / "backup.bsa", dest, "fixture")
    assert not dest.exists()
