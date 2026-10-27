"""
File: brisart_security_cli.py

Purpose
-------
Command-line front end for the Brisart Research Archive 97_Encryption toolkit.
One entry point (``python brisart_security_cli.py <command>``) exposes key
management, file encryption, sealed messages, hashing, the Brisart Secure
Archive (create, list, test, extract, repair, external recovery records,
split, join), a KDF benchmark, and a fast end-to-end self-test.

Communication / relationships
-----------------------------
Thin layer over brisart_security_keys.py, brisart_security_stream.py,
brisart_security_aead.py, brisart_security_kdf.py,
brisart_security_archive.py, brisart_security_sponge.py and
brisart_security_version.py. ``main(argv)`` is importable so
tests/test_keys_and_cli.py can drive it in-process.

Settings / parameters
---------------------
Key source (exactly one per command that needs a key):
  --key-file PATH          BSR2-KEYFILE written by ``keygen``
  --password-env NAME      read the password from an environment variable
  --password-prompt        prompt on the terminal (confirmation when creating)
Passwords are never accepted as command-line arguments.
DEFAULT_FILE_CONTEXT "bsr2-cli:file"; PASSWORD_FILE_MAGIC b"BSRPW001"
--kdf-memory BLOCKS (power of two, default 8192 = 1 MiB) for new password data.

Edge cases
----------
* No command overwrites an existing output unless ``--overwrite`` is given.
* ``decrypt`` and ``unseal`` write to a temporary file and only rename it into
  place after the whole input authenticates.
* Password-protected files bind their KDF parameter block as associated data,
  so downgrading the parameters fails authentication.
* All failures print ``error: ...`` to stderr and exit with status 1; usage
  errors exit with status 2.

Known limitations
-----------------
* Throughput is that of pure-Python BSR2 (tens of KiB/s); large files take
  minutes.
* ``--password-env`` exposes the password to anything that can read the
  process environment; prefer ``--password-prompt`` interactively.

Examples
--------
    python brisart_security_cli.py keygen lab.key --label "lab key"
    python brisart_security_cli.py encrypt notes.txt notes.bsrs --key-file lab.key
    python brisart_security_cli.py archive create out.bsa docs/ --key-file lab.key --recovery 5
    python brisart_security_cli.py archive extract out.bsa restored/ --key-file lab.key
    python brisart_security_cli.py selftest
"""
import argparse
import getpass
import io
import os
import sys
import time

import brisart_security_archive as archive
from brisart_security_aead import BrisartSealError, armor, dearmor, inspect_sealed, seal, unseal
from brisart_security_entropy import system_entropy
from brisart_security_kdf import DEFAULT_MEMORY_BLOCKS, ENCODED_PARAMS_BYTES, BrisartKdfError, KdfParams, derive_key, new_params
from brisart_security_keys import BrisartKeyError, fingerprint, generate_key, load_keyfile, permission_warning, save_keyfile
from brisart_security_primitives import hex_encode
from brisart_security_sponge import Sponge64
from brisart_security_stream import BrisartStreamError, decrypt_stream, encrypt_stream
from brisart_security_version import (
    ARCHIVE_FORMAT_VERSION,
    PROJECT_RELEASE,
    RELEASE_NAME,
    SEALED_FORMAT_VERSION,
    STREAM_FORMAT_VERSION,
)

DEFAULT_FILE_CONTEXT = "bsr2-cli:file"
PASSWORD_FILE_MAGIC = b"BSRPW001"


class CliError(Exception):
    pass


def _out(message: str) -> None:
    print(message)


# ---------------------------------------------------------------------------
# Key sources
# ---------------------------------------------------------------------------

def _add_key_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--key-file", help="BSR2 key file created by keygen")
    group.add_argument("--password-env", metavar="NAME", help="read the password from environment variable NAME")
    group.add_argument("--password-prompt", action="store_true", help="prompt for the password")


def _password(args, *, confirm: bool) -> str:
    if args.password_env:
        value = os.environ.get(args.password_env)
        if not value:
            raise CliError(f"environment variable {args.password_env} is empty or unset")
        return value
    first = getpass.getpass("Password: ")
    if not first:
        raise CliError("empty password")
    if confirm and getpass.getpass("Confirm password: ") != first:
        raise CliError("passwords do not match")
    return first


def _key_from_file(path: str) -> bytes:
    warning = permission_warning(path)
    if warning:
        print(f"warning: {warning}", file=sys.stderr)
    return load_keyfile(path)


def _atomic_output(path: str, overwrite: bool):
    if os.path.lexists(path) and not overwrite:
        raise CliError(f"refusing to overwrite {path} (use --overwrite)")
    temporary = f"{path}.{hex_encode(system_entropy(6))}.partial"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    return temporary, os.fdopen(fd, "wb")


def _finish(temporary: str, handle, path: str, ok: bool) -> None:
    handle.close()
    if ok:
        os.replace(temporary, path)
    elif os.path.exists(temporary):
        os.remove(temporary)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_info(args) -> int:
    _out(f"BrisartSecurityResearch {PROJECT_RELEASE} ({RELEASE_NAME})")
    _out(f"  sealed message format v{SEALED_FORMAT_VERSION} (BSR2-S64-SIV)")
    _out(f"  stream format v{STREAM_FORMAT_VERSION} (BSR-STREAM-1)")
    _out(f"  archive format v{ARCHIVE_FORMAT_VERSION} (BSA)")
    _out("  legacy envelope v2 (BSR2-ARX-SPONGE-ETM) supported")
    _out("  EXPERIMENTAL RESEARCH SOFTWARE - not independently reviewed")
    return 0


def cmd_keygen(args) -> int:
    key = generate_key(args.bytes)
    fp = save_keyfile(args.output, key, label=args.label, overwrite=args.overwrite)
    _out(f"wrote {args.output}")
    _out(f"fingerprint {fp}")
    return 0


def cmd_fingerprint(args) -> int:
    _out(fingerprint(_key_from_file(args.keyfile)))
    return 0


def cmd_encrypt(args) -> int:
    temporary, handle = _atomic_output(args.output, args.overwrite)
    ok = False
    try:
        with open(args.input, "rb") as source:
            if args.key_file:
                key = _key_from_file(args.key_file)
                total = encrypt_stream(key, source, handle, context=args.context, chunk_size=args.chunk_size)
            else:
                params = new_params(memory_blocks=args.kdf_memory)
                block = params.encode()
                key = derive_key(_password(args, confirm=True), params)
                handle.write(PASSWORD_FILE_MAGIC + block)
                total = encrypt_stream(
                    key, source, handle,
                    context=args.context,
                    associated_data=PASSWORD_FILE_MAGIC + block,
                    chunk_size=args.chunk_size,
                )
        ok = True
    finally:
        _finish(temporary, handle, args.output, ok)
    _out(f"encrypted {total} bytes -> {args.output}")
    return 0


def cmd_decrypt(args) -> int:
    temporary, handle = _atomic_output(args.output, args.overwrite)
    ok = False
    try:
        with open(args.input, "rb") as source:
            head = source.read(len(PASSWORD_FILE_MAGIC))
            if head == PASSWORD_FILE_MAGIC:
                if args.key_file:
                    raise CliError("this file is password protected")
                block = source.read(ENCODED_PARAMS_BYTES)
                params = KdfParams.decode(block, max_memory_blocks=args.max_kdf_memory)
                key = derive_key(_password(args, confirm=False), params, max_memory_blocks=args.max_kdf_memory)
                ad = PASSWORD_FILE_MAGIC + block
            else:
                if not args.key_file:
                    raise CliError("this file was encrypted with a key file")
                source.seek(0)
                key = _key_from_file(args.key_file)
                ad = b""
            total = decrypt_stream(key, source, handle, context=args.context, associated_data=ad)
        ok = True
    finally:
        _finish(temporary, handle, args.output, ok)
    _out(f"decrypted {total} bytes -> {args.output}")
    return 0


def cmd_seal(args) -> int:
    key = _key_from_file(args.key_file)
    with open(args.input, "rb") as handle:
        plaintext = handle.read()
    blob = seal(key, plaintext, args.context, padding=args.padding)
    data = armor(blob).encode("ascii") if args.armor else blob
    temporary, handle = _atomic_output(args.output, args.overwrite)
    ok = False
    try:
        handle.write(data)
        ok = True
    finally:
        _finish(temporary, handle, args.output, ok)
    _out(f"sealed {len(plaintext)} bytes -> {args.output}")
    return 0


def cmd_unseal(args) -> int:
    key = _key_from_file(args.key_file)
    with open(args.input, "rb") as handle:
        data = handle.read()
    if data.startswith(b"-----BEGIN"):
        data = dearmor(data.decode("ascii"))
    plaintext = unseal(key, data, args.context)
    temporary, handle = _atomic_output(args.output, args.overwrite)
    ok = False
    try:
        handle.write(plaintext)
        ok = True
    finally:
        _finish(temporary, handle, args.output, ok)
    _out(f"unsealed {len(plaintext)} bytes -> {args.output}")
    return 0


def cmd_hash(args) -> int:
    for path in args.files:
        sponge = Sponge64(b"BSR2/v3/file-hash")
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 16), b""):
                sponge.absorb(block)
        _out(f"{hex_encode(sponge.squeeze(args.length))}  {path}")
    return 0


def _archive_credentials(args, *, creating: bool) -> dict:
    if args.key_file:
        return {"key": _key_from_file(args.key_file)}
    return {"password": _password(args, confirm=creating)}


def cmd_archive_create(args) -> int:
    credentials = _archive_credentials(args, creating=True)
    options = {
        "solid": args.solid,
        "compression": args.compression,
        "comment": args.comment or "",
        "recovery_percent": args.recovery,
    }
    if "password" in credentials:
        options["kdf_params"] = new_params(memory_blocks=args.kdf_memory)
    result = archive.create_archive(
        args.output, args.inputs, base_dir=args.base_dir, overwrite=args.overwrite, **credentials, **options
    )
    for path, reason in result["skipped"]:
        print(f"skipped {path}: {reason}", file=sys.stderr)
    _out(f"created {result['archive']}: {result['members']} member(s), {result['bytes']} bytes")
    return 0


def _reader(args):
    credentials = _archive_credentials(args, creating=False)
    return archive.open_archive(args.archive, max_kdf_memory_blocks=args.max_kdf_memory, **credentials)


def cmd_archive_list(args) -> int:
    reader = _reader(args)
    mode = "solid" if reader.directory["solid"] else "per-file"
    _out(f"archive {hex_encode(reader.archive_id)} ({mode}, {len(reader.entries)} member(s))")
    if reader.kdf is not None:
        _out(f"  key derivation: {reader.kdf.describe()}")
    if reader.comment:
        _out(f"  comment: {reader.comment}")
    for entry in reader.entries:
        stamp = time.strftime("%Y-%m-%d %H:%M", time.gmtime(entry["mtime"]))
        method = entry.get("compression", reader.directory["compression"])
        _out(f"  {entry['size']:>12}  {stamp}  {method:<7}  {entry['name']}")
        if entry["comment"]:
            _out(f"                {entry['comment']}")
    return 0


def cmd_archive_test(args) -> int:
    result = _reader(args).test()
    _out(f"OK: {result['members']} member(s), {result['bytes']} bytes authenticated")
    return 0


def cmd_archive_extract(args) -> int:
    written = _reader(args).extract(args.destination, members=args.member, overwrite=args.overwrite)
    for path in written:
        _out(f"extracted {path}")
    return 0


def cmd_archive_repair(args) -> int:
    report = archive.repair_archive(args.archive, args.output, external_record=args.external, overwrite=args.overwrite)
    _out(
        f"repaired {len(report['repaired_chunks'])} of {len(report['damaged_chunks'])} damaged chunk(s) "
        f"using the {report['record']} record -> {report['output']}"
    )
    return 0


def cmd_archive_rr(args) -> int:
    result = archive.create_external_record(args.archive, args.output, redundancy_percent=args.percent, overwrite=args.overwrite)
    _out(f"wrote {result['record']} ({result['bytes']} bytes protecting {result['protected_bytes']} bytes)")
    return 0


def cmd_archive_split(args) -> int:
    for path in archive.split_volumes(args.archive, args.size, overwrite=args.overwrite):
        _out(f"wrote {path}")
    return 0


def cmd_archive_join(args) -> int:
    result = archive.join_volumes(args.volumes, args.output, overwrite=args.overwrite)
    _out(f"joined {result['volumes']} volume(s) -> {result['output']} ({result['bytes']} bytes)")
    return 0


def cmd_kdf_bench(args) -> int:
    params = new_params(memory_blocks=args.memory)
    started = time.perf_counter()
    derive_key("benchmark password", params)
    elapsed = time.perf_counter() - started
    _out(f"{params.describe()}: {elapsed:.2f} s")
    return 0


def cmd_selftest(args) -> int:
    key = generate_key()
    checks = []
    blob = seal(key, b"selftest", "selftest:seal", associated_data=b"ad", padding="padme")
    checks.append(("sealed message round trip", unseal(key, blob, "selftest:seal", associated_data=b"ad") == b"selftest"))
    try:
        unseal(key, blob[:-1] + bytes([blob[-1] ^ 1]), "selftest:seal", associated_data=b"ad")
        checks.append(("sealed message tamper rejection", False))
    except BrisartSealError:
        checks.append(("sealed message tamper rejection", True))
    stream_out = io.BytesIO()
    encrypt_stream(key, io.BytesIO(b"s" * 300), stream_out, context="selftest:stream", chunk_size=64)
    plain = io.BytesIO()
    decrypt_stream(key, io.BytesIO(stream_out.getvalue()), plain, context="selftest:stream")
    checks.append(("stream round trip", plain.getvalue() == b"s" * 300))
    try:
        truncated = stream_out.getvalue()[:-96]
        decrypt_stream(key, io.BytesIO(truncated), io.BytesIO(), context="selftest:stream")
        checks.append(("stream truncation rejection", False))
    except BrisartStreamError:
        checks.append(("stream truncation rejection", True))
    params = KdfParams(memory_blocks=64, passes=1, salt=bytes(range(32)))
    checks.append(("KDF determinism", derive_key("pw", params) == derive_key("pw", params)))
    members = [("selftest/a.txt", b"alpha" * 50, 0, "first"), ("selftest/b.bin", bytes(range(256)), 0, "")]
    bsa = archive.build_archive(members, key=key, recovery_percent=10, recovery_chunk_size=128)
    reader = archive.ArchiveReader(bsa, key=key)
    checks.append(("archive round trip", reader.read("selftest/a.txt") == b"alpha" * 50))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        _out(f"[{'PASS' if ok else 'FAIL'}] {name}")
    return 1 if failed else 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brisart_security_cli", description="BSR2 research toolkit (experimental).")
    parser.add_argument("--version", action="version", version=f"%(prog)s {PROJECT_RELEASE}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("info", help="show release and format versions").set_defaults(func=cmd_info)

    p = commands.add_parser("keygen", help="create a key file")
    p.add_argument("output")
    p.add_argument("--label", default="")
    p.add_argument("--bytes", type=int, default=32)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_keygen)

    p = commands.add_parser("fingerprint", help="print a key file fingerprint")
    p.add_argument("keyfile")
    p.set_defaults(func=cmd_fingerprint)

    for name, func, help_text in (
        ("encrypt", cmd_encrypt, "encrypt a file (BSR-STREAM-1)"),
        ("decrypt", cmd_decrypt, "decrypt a file (BSR-STREAM-1)"),
    ):
        p = commands.add_parser(name, help=help_text)
        p.add_argument("input")
        p.add_argument("output")
        _add_key_options(p)
        p.add_argument("--context", default=DEFAULT_FILE_CONTEXT)
        p.add_argument("--chunk-size", type=int, default=64 * 1024)
        p.add_argument("--kdf-memory", type=int, default=DEFAULT_MEMORY_BLOCKS)
        p.add_argument("--max-kdf-memory", type=int, default=1 << 20)
        p.add_argument("--overwrite", action="store_true")
        p.set_defaults(func=func)

    p = commands.add_parser("seal", help="seal a small file as a v3 sealed message")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--key-file", required=True)
    p.add_argument("--context", default="bsr2-cli:sealed")
    p.add_argument("--padding", choices=("none", "padme", "block"), default="padme")
    p.add_argument("--armor", action="store_true", help="write armored hex text")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_seal)

    p = commands.add_parser("unseal", help="open a v3 sealed message (binary or armored)")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--key-file", required=True)
    p.add_argument("--context", default="bsr2-cli:sealed")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_unseal)

    p = commands.add_parser("hash", help="BSR2-S64 file hash")
    p.add_argument("files", nargs="+")
    p.add_argument("--length", type=int, default=32)
    p.set_defaults(func=cmd_hash)

    p = commands.add_parser("kdf-bench", help="time BSR2-MHF-1 at a memory setting")
    p.add_argument("--memory", type=int, default=DEFAULT_MEMORY_BLOCKS)
    p.set_defaults(func=cmd_kdf_bench)

    commands.add_parser("selftest", help="fast end-to-end self-test").set_defaults(func=cmd_selftest)

    a = commands.add_parser("archive", help="Brisart Secure Archive operations")
    acts = a.add_subparsers(dest="action", required=True)

    p = acts.add_parser("create", help="create an archive")
    p.add_argument("output")
    p.add_argument("inputs", nargs="+")
    _add_key_options(p)
    p.add_argument("--solid", action="store_true")
    p.add_argument("--compression", choices=archive.COMPRESSION_METHODS, default=archive.DEFAULT_COMPRESSION)
    p.add_argument("--comment")
    p.add_argument("--recovery", type=int, default=5, help="internal recovery record percent (0 disables)")
    p.add_argument("--base-dir")
    p.add_argument("--kdf-memory", type=int, default=DEFAULT_MEMORY_BLOCKS)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_create)

    for name, func in (("list", cmd_archive_list), ("test", cmd_archive_test)):
        p = acts.add_parser(name)
        p.add_argument("archive")
        _add_key_options(p)
        p.add_argument("--max-kdf-memory", type=int, default=1 << 20)
        p.set_defaults(func=func)

    p = acts.add_parser("extract")
    p.add_argument("archive")
    p.add_argument("destination")
    _add_key_options(p)
    p.add_argument("--member", action="append")
    p.add_argument("--max-kdf-memory", type=int, default=1 << 20)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_extract)

    p = acts.add_parser("repair", help="repair damage without the key")
    p.add_argument("archive")
    p.add_argument("output")
    p.add_argument("--external", help="external .bsrr recovery record")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_repair)

    p = acts.add_parser("rr", help="write an external recovery record")
    p.add_argument("archive")
    p.add_argument("output")
    p.add_argument("--percent", type=int, default=10)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_rr)

    p = acts.add_parser("split", help="split into volumes")
    p.add_argument("archive")
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_split)

    p = acts.add_parser("join", help="join volumes")
    p.add_argument("output")
    p.add_argument("volumes", nargs="+")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_archive_join)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        CliError,
        BrisartKeyError,
        BrisartKdfError,
        BrisartSealError,
        BrisartStreamError,
        archive.BrisartArchiveError,
        OSError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
