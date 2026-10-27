"""
File: tests/test_keys_and_cli.py

Purpose
-------
Tests for key files (brisart_security_keys.py) and the command-line front end
(brisart_security_cli.py): key generation and integrity checks, owner-only
permissions, every CLI command end to end in a temporary folder, password
mode through ``--password-env``, atomic outputs that never appear on failure,
overwrite refusal, and exit codes.

Communication / relationships
-----------------------------
Calls ``brisart_security_cli.main(argv)`` in-process; stdout/stderr are
captured with ``contextlib.redirect_stdout``/``redirect_stderr``.

Settings / parameters
---------------------
Password tests use ``--kdf-memory 64`` and the environment variable
BSR2_TEST_PASSWORD.

Edge cases
----------
Hand-edited key files (changed key, changed label, extra field) must be
rejected; a wrong password must leave no output file behind.

Known limitations
-----------------
``--password-prompt`` (interactive getpass) is not exercised.

Examples
--------
    python -m unittest -v tests.test_keys_and_cli
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import brisart_security_cli as cli
from brisart_security_keys import (
    BrisartKeyError,
    fingerprint,
    generate_key,
    load_keyfile,
    parse_keyfile,
    save_keyfile,
    serialize_keyfile,
)


def run(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class KeyFileTests(unittest.TestCase):
    def test_round_trip_and_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "k.key")
            key = generate_key()
            fp = save_keyfile(path, key, label="lab")
            self.assertEqual(load_keyfile(path), key)
            self.assertEqual(fp, fingerprint(key))
            if os.name == "posix":
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with self.assertRaises(BrisartKeyError):
                save_keyfile(path, key)

    def test_edited_files_are_rejected(self) -> None:
        document = json.loads(serialize_keyfile(generate_key(), label="lab"))
        edits = [
            {**document, "key": "00" + document["key"][2:]},
            {**document, "label": "other"},
            {**document, "extra": 1},
            {**document, "version": 2},
            {**document, "key": document["key"].upper()},
        ]
        for edited in edits:
            with self.assertRaises(BrisartKeyError):
                parse_keyfile(json.dumps(edited).encode())

    def test_generation_bounds(self) -> None:
        for length in (16, 129, True):
            with self.assertRaises(BrisartKeyError):
                generate_key(length)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.key = os.path.join(self.root, "lab.key")
        self.assertEqual(run("keygen", self.key, "--label", "lab")[0], 0)
        self.src = os.path.join(self.root, "src")
        os.makedirs(self.src)
        with open(os.path.join(self.src, "notes.txt"), "wb") as handle:
            handle.write(b"research notes " * 30)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def p(self, name: str) -> str:
        return os.path.join(self.root, name)

    def test_info_selftest_fingerprint_hash(self) -> None:
        self.assertEqual(run("info")[0], 0)
        code, out, _ = run("selftest")
        self.assertEqual(code, 0)
        self.assertNotIn("FAIL", out)
        self.assertEqual(run("fingerprint", self.key)[1].strip(), fingerprint(load_keyfile(self.key)))
        code, out, _ = run("hash", os.path.join(self.src, "notes.txt"))
        self.assertEqual(code, 0)
        self.assertEqual(len(out.split()[0]), 64)

    def test_encrypt_decrypt_key_file(self) -> None:
        source = os.path.join(self.src, "notes.txt")
        self.assertEqual(run("encrypt", source, self.p("n.bsrs"), "--key-file", self.key)[0], 0)
        self.assertEqual(run("decrypt", self.p("n.bsrs"), self.p("n.out"), "--key-file", self.key)[0], 0)
        with open(self.p("n.out"), "rb") as a, open(source, "rb") as b:
            self.assertEqual(a.read(), b.read())
        code, _, err = run("encrypt", source, self.p("n.bsrs"), "--key-file", self.key)
        self.assertEqual(code, 1)
        self.assertIn("refusing to overwrite", err)

    def test_password_mode_and_atomic_failure(self) -> None:
        source = os.path.join(self.src, "notes.txt")
        with patch.dict(os.environ, {"BSR2_TEST_PASSWORD": "correct"}):
            self.assertEqual(
                run("encrypt", source, self.p("n.pw"), "--password-env", "BSR2_TEST_PASSWORD", "--kdf-memory", "64")[0], 0
            )
            self.assertEqual(run("decrypt", self.p("n.pw"), self.p("ok.out"), "--password-env", "BSR2_TEST_PASSWORD")[0], 0)
        with patch.dict(os.environ, {"BSR2_TEST_PASSWORD": "wrong"}):
            code, _, err = run("decrypt", self.p("n.pw"), self.p("bad.out"), "--password-env", "BSR2_TEST_PASSWORD")
        self.assertEqual(code, 1)
        self.assertIn("authentication failed", err)
        self.assertFalse(os.path.exists(self.p("bad.out")))
        self.assertFalse([name for name in os.listdir(self.root) if name.endswith(".partial")])

    def test_kdf_downgrade_in_file_header_fails(self) -> None:
        source = os.path.join(self.src, "notes.txt")
        with patch.dict(os.environ, {"BSR2_TEST_PASSWORD": "pw"}):
            run("encrypt", source, self.p("n.pw"), "--password-env", "BSR2_TEST_PASSWORD", "--kdf-memory", "128")
            with open(self.p("n.pw"), "r+b") as handle:
                handle.seek(8 + 4)
                handle.write((64).to_bytes(4, "big"))
            code, _, _ = run("decrypt", self.p("n.pw"), self.p("x.out"), "--password-env", "BSR2_TEST_PASSWORD")
        self.assertEqual(code, 1)

    def test_seal_unseal_armor(self) -> None:
        source = os.path.join(self.src, "notes.txt")
        self.assertEqual(run("seal", source, self.p("s.txt"), "--key-file", self.key, "--armor")[0], 0)
        with open(self.p("s.txt"), "rb") as handle:
            self.assertTrue(handle.read().startswith(b"-----BEGIN BSR2 SEALED MESSAGE-----"))
        self.assertEqual(run("unseal", self.p("s.txt"), self.p("s.out"), "--key-file", self.key)[0], 0)

    def test_archive_commands(self) -> None:
        archive = self.p("a.bsa")
        self.assertEqual(run("archive", "create", archive, self.src, "--key-file", self.key, "--comment", "cli", "--solid")[0], 0)
        code, out, _ = run("archive", "list", archive, "--key-file", self.key)
        self.assertEqual(code, 0)
        self.assertIn("src/notes.txt", out)
        self.assertIn("comment: cli", out)
        self.assertEqual(run("archive", "test", archive, "--key-file", self.key)[0], 0)
        self.assertEqual(run("archive", "extract", archive, self.p("out"), "--key-file", self.key)[0], 0)
        self.assertTrue(os.path.exists(os.path.join(self.p("out"), "src", "notes.txt")))
        self.assertEqual(run("archive", "rr", archive, self.p("a.bsrr"))[0], 0)
        with open(archive, "r+b") as handle:
            handle.seek(200)
            value = handle.read(1)
            handle.seek(200)
            handle.write(bytes([value[0] ^ 0xFF]))
        self.assertEqual(run("archive", "test", archive, "--key-file", self.key)[0], 1)
        self.assertEqual(run("archive", "repair", archive, self.p("fixed.bsa"), "--external", self.p("a.bsrr"))[0], 0)
        self.assertEqual(run("archive", "test", self.p("fixed.bsa"), "--key-file", self.key)[0], 0)
        code, out, _ = run("archive", "split", self.p("fixed.bsa"), "--size", "1024")
        volumes = [line.split()[-1] for line in out.splitlines()]
        self.assertEqual(run("archive", "join", self.p("joined.bsa"), *volumes)[0], 0)
        self.assertEqual(run("archive", "test", self.p("joined.bsa"), "--key-file", self.key)[0], 0)

    def test_usage_errors_exit_2(self) -> None:
        with self.assertRaises(SystemExit) as captured, contextlib.redirect_stderr(io.StringIO()):
            cli.main(["encrypt", "a", "b"])
        self.assertEqual(captured.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
