"""
File: tests/test_archive.py

Purpose
-------
End-to-end tests for the Brisart Secure Archive (brisart_security_archive.py):
per-file and solid modes with every compression method, key-file and password
modes, encrypted directory and comments, tamper and wrong-credential
rejection, extraction safety (path traversal, reserved names, duplicates,
symlinks, overwrite refusal), compression-bomb bounding, internal and external
recovery with footer reconstruction, and multi-volume split/join.

Communication / relationships
-----------------------------
Imports brisart_security_archive.py and brisart_security_kdf.py; writes only
inside ``tempfile.TemporaryDirectory`` folders.

Settings / parameters
---------------------
KEY = bytes(range(32)); FAST_KDF = 64-block BSR2-MHF-1 parameters; small
recovery chunks (128 bytes) so damage tests stay fast.

Edge cases
----------
Malicious directories are produced with the private ``_validate_names=False``
builder hook so the extract-side checks are exercised independently of the
create-side checks.

Known limitations
-----------------
In-memory archives of a few KiB; large-archive performance is not measured.

Examples
--------
    python -m unittest -v tests.test_archive
"""
import os
import tempfile
import unittest
import zlib
from unittest.mock import patch

import brisart_security_archive as archive_module
from brisart_security_archive import (
    COMPRESSION_METHODS,
    ArchiveReader,
    BrisartArchiveError,
    build_archive,
    create_archive,
    create_external_record,
    join_volumes,
    normalize_member_name,
    open_archive,
    repair_archive,
    split_volumes,
)
from brisart_security_kdf import KdfParams

KEY = bytes(range(32))
FAST_KDF = KdfParams(memory_blocks=64, passes=1, salt=bytes(range(32)))
MEMBERS = [
    ("docs/readme.txt", b"Brisart archive test " * 40, 1_700_000_000, "the readme", False),
    ("bin/tool.sh", b"#!/bin/sh\necho hi\n", 1_700_000_100, "", True),
    ("data/random.bin", bytes(range(256)) * 3, 1_700_000_200, "", False),
    ("empty.txt", b"", 0, "", False),
]


class ArchiveFormatTests(unittest.TestCase):
    def test_round_trip_all_modes(self) -> None:
        for solid in (False, True):
            for compression in COMPRESSION_METHODS:
                with self.subTest(solid=solid, compression=compression):
                    blob = build_archive(MEMBERS, key=KEY, solid=solid, compression=compression, comment="archive note")
                    reader = ArchiveReader(blob, key=KEY)
                    self.assertEqual(reader.comment, "archive note")
                    self.assertEqual([e["name"] for e in reader.entries], [m[0] for m in MEMBERS])
                    for name, data, *_ in MEMBERS:
                        self.assertEqual(reader.read(name), data)
                    self.assertEqual(reader.test()["members"], len(MEMBERS))

    def test_directory_is_encrypted(self) -> None:
        blob = build_archive(MEMBERS, key=KEY, compression="store")
        for name, *_ in MEMBERS:
            self.assertNotIn(name.encode(), blob)
        self.assertNotIn(b"the readme", blob)
        self.assertNotIn(b"Brisart archive test", blob)

    def test_password_mode(self) -> None:
        blob = build_archive(MEMBERS, password="lab password", kdf_params=FAST_KDF)
        reader = ArchiveReader(blob, password="lab password")
        self.assertEqual(reader.read("bin/tool.sh"), MEMBERS[1][1])
        for kwargs in ({"password": "wrong"}, {"key": KEY}, {}):
            with self.subTest(kwargs=list(kwargs)):
                with self.assertRaises(BrisartArchiveError):
                    ArchiveReader(blob, **kwargs)

    def test_hostile_kdf_header_is_bounded(self) -> None:
        heavy = KdfParams(memory_blocks=1 << 20, passes=1, salt=bytes(32))
        with patch.object(archive_module, "derive_key", return_value=bytes(32)):
            blob = build_archive(MEMBERS[:1], password="pw", kdf_params=heavy)
        with self.assertRaises(BrisartArchiveError):
            ArchiveReader(blob, password="pw", max_kdf_memory_blocks=1 << 12)

    def test_wrong_key_and_tamper(self) -> None:
        blob = build_archive(MEMBERS, key=KEY)
        with self.assertRaises(BrisartArchiveError):
            ArchiveReader(blob, key=bytes(reversed(KEY)))
        footer = archive_module._locate(blob)
        for position in (archive_module.PREAMBLE_BYTES + 50, footer["dir_offset"] + 120):
            changed = bytearray(blob)
            changed[position] ^= 1
            with self.subTest(position=position):
                with self.assertRaises(BrisartArchiveError):
                    ArchiveReader(bytes(changed), key=KEY).test()

    def test_preamble_change_breaks_authentication_even_with_fixed_crc(self) -> None:
        blob = bytearray(build_archive(MEMBERS, key=KEY))
        blob[11] ^= archive_module.FLAG_SOLID
        ad_end = archive_module.PREAMBLE_AD_BYTES
        blob[ad_end:ad_end + 4] = zlib.crc32(bytes(blob[:ad_end])).to_bytes(4, "big")
        with self.assertRaises(BrisartArchiveError):
            ArchiveReader(bytes(blob), key=KEY)

    def test_member_name_validation(self) -> None:
        bad = [
            "", "/etc/passwd", "../escape", "a/../../b", "a//b", "./a", "a\\b", "C:/x", "a:stream",
            "con", "dir/NUL.txt", "trailing.", "trailing ", "tab\tname", "a/" + "x" * 300,
        ]
        for name in bad:
            with self.subTest(name=name):
                with self.assertRaises(BrisartArchiveError):
                    normalize_member_name(name)
        self.assertEqual(normalize_member_name("cafe\u0301/ok.txt"), "caf\u00e9/ok.txt")

    def test_duplicate_names_including_case(self) -> None:
        with self.assertRaises(BrisartArchiveError):
            build_archive([("A.txt", b"1", 0, ""), ("a.txt", b"2", 0, "")], key=KEY)

    def test_extract_rejects_malicious_directory(self) -> None:
        for evil in ("../escape.txt", "/abs.txt", "ok/../../x"):
            blob = build_archive([(evil, b"pwn", 0, "")], key=KEY, _validate_names=False)
            with self.subTest(name=evil), tempfile.TemporaryDirectory() as target:
                with self.assertRaises(BrisartArchiveError):
                    ArchiveReader(blob, key=KEY)
                self.assertEqual(os.listdir(target), [])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_extract_refuses_symlinked_parent(self) -> None:
        blob = build_archive([("link/file.txt", b"data", 0, "")], key=KEY)
        with tempfile.TemporaryDirectory() as target, tempfile.TemporaryDirectory() as outside:
            try:
                os.symlink(outside, os.path.join(target, "link"))
            except OSError:
                self.skipTest("cannot create symlinks here")
            with self.assertRaises(BrisartArchiveError):
                ArchiveReader(blob, key=KEY).extract(target)
            self.assertEqual(os.listdir(outside), [])

    def test_extract_overwrite_rules_and_metadata(self) -> None:
        blob = build_archive(MEMBERS, key=KEY)
        reader = ArchiveReader(blob, key=KEY)
        with tempfile.TemporaryDirectory() as target:
            written = reader.extract(target)
            self.assertEqual(len(written), len(MEMBERS))
            path = os.path.join(target, "docs", "readme.txt")
            self.assertEqual(int(os.stat(path).st_mtime), MEMBERS[0][2])
            if os.name == "posix":
                self.assertTrue(os.stat(os.path.join(target, "bin", "tool.sh")).st_mode & 0o100)
            with self.assertRaises(BrisartArchiveError):
                reader.extract(target)
            reader.extract(target, overwrite=True, members=["empty.txt"])
            with self.assertRaises(BrisartArchiveError):
                reader.extract(target, overwrite=True, members=["missing.txt"])

    def test_compression_bomb_is_bounded(self) -> None:
        bomb = zlib.compress(b"\x00" * 5_000_000, 9)
        with self.assertRaises(BrisartArchiveError):
            archive_module._decompress(bomb, "deflate", 1000)

    def test_unpacked_size_ceiling(self) -> None:
        blob = build_archive(MEMBERS, key=KEY)
        with self.assertRaises(BrisartArchiveError):
            ArchiveReader(blob, key=KEY, max_unpacked_bytes=100)


class ArchiveFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        source = os.path.join(self.root, "src")
        os.makedirs(os.path.join(source, "nested"))
        with open(os.path.join(source, "a.txt"), "wb") as handle:
            handle.write(b"alpha " * 500)
        with open(os.path.join(source, "nested", "b.bin"), "wb") as handle:
            handle.write(bytes(range(256)) * 8)
        self.source = source
        self.archive = os.path.join(self.root, "test.bsa")
        create_archive(self.archive, [source], key=KEY, recovery_percent=10, recovery_chunk_size=128, comment="file test")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_create_refuses_overwrite(self) -> None:
        with self.assertRaises(BrisartArchiveError):
            create_archive(self.archive, [self.source], key=KEY)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlinks_are_skipped(self) -> None:
        try:
            os.symlink(os.path.join(self.source, "a.txt"), os.path.join(self.source, "link.txt"))
        except OSError:
            self.skipTest("cannot create symlinks here")
        result = create_archive(os.path.join(self.root, "s.bsa"), [self.source], key=KEY)
        self.assertTrue(any(reason == "symlink" for _, reason in result["skipped"]))
        names = [e["name"] for e in open_archive(os.path.join(self.root, "s.bsa"), key=KEY).entries]
        self.assertNotIn("src/link.txt", names)

    def _damage(self, positions) -> str:
        with open(self.archive, "rb") as handle:
            data = bytearray(handle.read())
        for position in positions:
            data[position] ^= 0xFF
        damaged = os.path.join(self.root, "damaged.bsa")
        with open(damaged, "wb") as handle:
            handle.write(data)
        return damaged

    def test_internal_repair_including_footers(self) -> None:
        damaged = self._damage([10, 150, -5, -69])
        with self.assertRaises(BrisartArchiveError):
            open_archive(damaged, key=KEY)
        fixed = os.path.join(self.root, "fixed.bsa")
        report = repair_archive(damaged, fixed)
        self.assertTrue(report["footers_rebuilt"])
        with open(fixed, "rb") as a, open(self.archive, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(open_archive(fixed, key=KEY).test()["status"], "OK")

    def test_external_record_repair(self) -> None:
        record = os.path.join(self.root, "test.bsrr")
        create_external_record(self.archive, record, redundancy_percent=20, chunk_size=128)
        damaged = self._damage([300])
        fixed = os.path.join(self.root, "fixed_ext.bsa")
        report = repair_archive(damaged, fixed, external_record=record)
        self.assertEqual(report["record"], "external")
        self.assertEqual(open_archive(fixed, key=KEY).test()["status"], "OK")

    def test_unrepairable_damage_is_reported(self) -> None:
        damaged = self._damage(range(200, 200 + 128 * 3, 128))
        with self.assertRaises(BrisartArchiveError):
            repair_archive(damaged, os.path.join(self.root, "never.bsa"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "never.bsa")))

    def test_split_and_join(self) -> None:
        volumes = split_volumes(self.archive, 1024)
        self.assertGreater(len(volumes), 1)
        joined = os.path.join(self.root, "joined.bsa")
        join_volumes(list(reversed(volumes)), joined)
        self.assertEqual(open_archive(joined, key=KEY).comment, "file test")
        with self.assertRaises(BrisartArchiveError):
            join_volumes(volumes[:-1], os.path.join(self.root, "partial.bsa"))
        with open(volumes[0], "r+b") as handle:
            handle.seek(60)
            byte = handle.read(1)
            handle.seek(60)
            handle.write(bytes([byte[0] ^ 1]))
        with self.assertRaises(BrisartArchiveError):
            join_volumes(volumes, os.path.join(self.root, "bad.bsa"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
