"""
File: brisart_security_archive.py

Purpose
-------
Brisart Secure Archive (BSA, ``.bsa``) format 1: an SQX-style multi-file
archiver built on the BSR2 v3 constructions. It provides per-file or solid
compression, encrypted file data, an independently encrypted directory (file
names, sizes, times and comments are never stored in clear), archive and file
comments, internal and external recovery records with key-free repair,
multi-volume split/join, and hardened extraction.

Layout::

    preamble (137 B)  magic | ver | flags | archive_id | KDF params | key_check | crc32
    data region       BSR-STREAM-1 blob per entry, or one solid blob
    directory         sealed v3 message (canonical JSON, padme padding)
    recovery record   BSRR-1 over [0, end of directory)          (optional)
    footer x2 (64 B)  offsets/lengths, archive_id, crc32 (two copies)

Every stream and the directory use the preamble (through key_check) as
associated data, so any preamble change fails authentication.

Communication / relationships
-----------------------------
Imports brisart_security_aead.py (directory), brisart_security_stream.py
(entry data), brisart_security_kdf.py (password mode),
brisart_security_recovery.py (repair), brisart_security_sponge.py (archive key
derivation and key check), brisart_security_entropy.py (archive id, salts), and
the standard library (``json``, ``zlib``, ``lzma``, ``os``, ``unicodedata``).
Driven by brisart_security_cli.py; covered by tests/test_archive.py.

Settings / parameters
---------------------
MAGIC b"BSA\\x00\\r\\n\\x1a\\n"; FORMAT_VERSION 1; PREAMBLE_BYTES 137; FOOTER_BYTES 64
COMPRESSION_METHODS "store", "deflate" (zlib level 9), "lzma" (xz preset 6)
DEFAULT_CHUNK_SIZE 65,536 bytes per stream chunk
MAX_ENTRIES 65,536; MAX_NAME_BYTES 1024; MAX_COMMENT_BYTES 65,536
MAX_DIRECTORY_BYTES 16 MiB; DEFAULT_MAX_UNPACKED_BYTES 4 GiB
VOLUME_MAGIC b"BSAVOL01"; VOLUME_HEADER_BYTES 44

Edge cases
----------
* Member names are validated on create and again on extract: no absolute
  paths, drive letters, ``..``/``.`` segments, backslashes, control characters,
  trailing dots/spaces, Windows reserved device names, or case-insensitive
  duplicates. Extraction also checks that every resolved path stays inside
  the destination (defeats pre-existing symlinks).
* Symlinks and special files are skipped on create and reported.
* Decompression is bounded by the authenticated declared size, so compression
  bombs stop at size+1 bytes; sizes and CRC-32 must match exactly.
* Nothing is overwritten unless ``overwrite=True``; every output file is written
  to a temporary sibling and renamed into place.
* Both footers are checked; if both are destroyed the recovery record is found
  by scanning, and ``repair_archive`` rebuilds the footers.

Known limitations
-----------------
* Archives are processed in memory; practical size is bounded by RAM and by
  pure-Python throughput (tens of KiB/s for encryption).
* Compression before encryption reveals compressed sizes; padme padding on
  the directory hides only its exact length.
* No public-key signatures: authenticity is shared-key only.
* "store"/"deflate"/"lzma" rely on the standard-library ``zlib``/``lzma``
  modules; "lzma" is unavailable on Python builds compiled without it.
* The v3 constructions underneath are unanalysed research code.

Examples
--------
>>> from brisart_security_archive import build_archive, ArchiveReader
>>> key = bytes(range(32))
>>> blob = build_archive([("notes/a.txt", b"alpha", 0, "")], key=key)
>>> reader = ArchiveReader(blob, key=key)
>>> [entry["name"] for entry in reader.entries]
['notes/a.txt']
>>> reader.read("notes/a.txt")
b'alpha'
"""
import io
import json
import os
import stat
import unicodedata
import zlib

from brisart_security_aead import BrisartSealError, seal, unseal
from brisart_security_entropy import system_entropy
from brisart_security_kdf import ENCODED_PARAMS_BYTES, BrisartKdfError, KdfParams, derive_key, new_params
from brisart_security_primitives import constant_time_equal, hex_encode
from brisart_security_recovery import (
    MAGIC as RECOVERY_MAGIC,
    BrisartRecoveryError,
    build_recovery,
    parse_recovery,
    repair as repair_bytes,
)
from brisart_security_sponge import derive_keys64, mac64
from brisart_security_stream import BrisartStreamError, decrypt_bytes, encrypt_bytes

try:
    import lzma
except ImportError:  # pragma: no cover - depends on the Python build
    lzma = None

MAGIC = b"BSA\x00\r\n\x1a\n"
FORMAT_VERSION = 1
FLAG_SOLID = 0x0001
FLAG_PASSWORD = 0x0002
KNOWN_FLAGS = FLAG_SOLID | FLAG_PASSWORD
ARCHIVE_ID_BYTES = 16
KEY_CHECK_BYTES = 32
_KEYED_PART = 8 + 2 + 2 + ARCHIVE_ID_BYTES + ENCODED_PARAMS_BYTES
PREAMBLE_AD_BYTES = _KEYED_PART + KEY_CHECK_BYTES
PREAMBLE_BYTES = PREAMBLE_AD_BYTES + 4
FOOTER_MAGIC = b"BSAFOOT1"
FOOTER_BYTES = 64
COMPRESSION_METHODS = ("store", "deflate", "lzma")
DEFAULT_COMPRESSION = "deflate"
DEFAULT_CHUNK_SIZE = 64 * 1024
MAX_ENTRIES = 65_536
MAX_NAME_BYTES = 1024
MAX_SEGMENT_BYTES = 255
MAX_COMMENT_BYTES = 65_536
MAX_DIRECTORY_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_UNPACKED_BYTES = 4 * 1024 ** 3
MIN_KEY_BYTES = 32
VOLUME_MAGIC = b"BSAVOL01"
VOLUME_HEADER_BYTES = 8 + 16 + 4 + 4 + 8 + 4
MIN_VOLUME_BYTES = 1024
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


class BrisartArchiveError(Exception):
    """Raised for archive format, authentication, safety, or I/O failures."""


# ---------------------------------------------------------------------------
# Names, comments, compression
# ---------------------------------------------------------------------------

def normalize_member_name(name: str) -> str:
    """Return the canonical archive name or raise if it is unsafe."""
    if not isinstance(name, str) or not name:
        raise BrisartArchiveError("member name must be a non-empty string")
    name = unicodedata.normalize("NFC", name)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise BrisartArchiveError(f"member name contains control characters: {name!r}")
    if "\\" in name or ":" in name:
        raise BrisartArchiveError(f"member name contains a backslash or colon: {name!r}")
    if name.startswith("/"):
        raise BrisartArchiveError(f"member name is absolute: {name!r}")
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BrisartArchiveError("member name is not valid UTF-8") from exc
    if len(encoded) > MAX_NAME_BYTES:
        raise BrisartArchiveError("member name is too long")
    for segment in name.split("/"):
        if segment in ("", ".", ".."):
            raise BrisartArchiveError(f"member name has an empty, '.' or '..' segment: {name!r}")
        if segment[-1] in " .":
            raise BrisartArchiveError(f"member name segment ends with a space or dot: {name!r}")
        if len(segment.encode("utf-8")) > MAX_SEGMENT_BYTES:
            raise BrisartArchiveError("member name segment is too long")
        if segment.split(".")[0].lower() in _WINDOWS_RESERVED:
            raise BrisartArchiveError(f"member name uses a reserved device name: {name!r}")
    return name


def _comment(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise BrisartArchiveError("comments must be strings")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BrisartArchiveError("comment is not valid UTF-8 text") from exc
    if len(encoded) > MAX_COMMENT_BYTES:
        raise BrisartArchiveError("comment exceeds the size limit")
    return value


def _compress(data: bytes, method: str) -> bytes:
    if method == "store":
        return data
    if method == "deflate":
        return zlib.compress(data, 9)
    if method == "lzma":
        if lzma is None:
            raise BrisartArchiveError("lzma compression is not available in this Python build")
        return lzma.compress(data, format=lzma.FORMAT_XZ, check=lzma.CHECK_NONE, preset=6)
    raise BrisartArchiveError(f"unknown compression method: {method!r}")


def _decompress(data: bytes, method: str, expected: int) -> bytes:
    """Decompress with a hard output bound of ``expected`` + 1 bytes."""
    if method == "store":
        output = data
    elif method == "deflate":
        engine = zlib.decompressobj()
        try:
            output = engine.decompress(data, expected + 1)
        except zlib.error as exc:
            raise BrisartArchiveError("compressed data is corrupt") from exc
        if engine.unconsumed_tail or not engine.eof or engine.unused_data:
            raise BrisartArchiveError("compressed data does not match its declared size")
    elif method == "lzma":
        if lzma is None:
            raise BrisartArchiveError("lzma compression is not available in this Python build")
        engine = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
        try:
            output = engine.decompress(data, max_length=expected + 1)
        except lzma.LZMAError as exc:
            raise BrisartArchiveError("compressed data is corrupt") from exc
        if not engine.eof or engine.unused_data:
            raise BrisartArchiveError("compressed data does not match its declared size")
    else:
        raise BrisartArchiveError(f"unknown compression method: {method!r}")
    if len(output) != expected:
        raise BrisartArchiveError("decompressed size does not match the directory")
    return output


# ---------------------------------------------------------------------------
# Keys and fixed structures
# ---------------------------------------------------------------------------

def _master_key(key, password, params: KdfParams | None, *, max_memory_blocks: int | None = None) -> bytes:
    if (key is None) == (password is None):
        raise BrisartArchiveError("supply exactly one of key or password")
    if key is not None:
        if not isinstance(key, bytes) or len(key) < MIN_KEY_BYTES:
            raise BrisartArchiveError("archive key must be at least 32 bytes")
        return key
    try:
        if max_memory_blocks is not None:
            return derive_key(password, params, 32, max_memory_blocks=max_memory_blocks)
        return derive_key(password, params, 32)
    except BrisartKdfError as exc:
        raise BrisartArchiveError(f"password key derivation failed: {exc}") from exc


def _archive_key(master: bytes, keyed_part: bytes) -> bytes:
    return derive_keys64(master, b"BSR2/v3/archive/key", keyed_part, count=1)[0]


def _key_check(archive_key: bytes, keyed_part: bytes) -> bytes:
    return mac64(archive_key, b"BSR2/v3/archive/key-check", keyed_part, output_bytes=KEY_CHECK_BYTES)


def _footer(dir_offset: int, dir_length: int, rr_offset: int, rr_length: int, archive_id: bytes) -> bytes:
    body = (
        FOOTER_MAGIC
        + dir_offset.to_bytes(8, "big")
        + dir_length.to_bytes(8, "big")
        + rr_offset.to_bytes(8, "big")
        + rr_length.to_bytes(8, "big")
        + archive_id
        + bytes(4)
    )
    return body + zlib.crc32(body).to_bytes(4, "big")


def _parse_footer(block: bytes):
    if len(block) != FOOTER_BYTES or block[:8] != FOOTER_MAGIC:
        return None
    if zlib.crc32(block[:-4]).to_bytes(4, "big") != block[-4:] or any(block[56:60]):
        return None
    return {
        "dir_offset": int.from_bytes(block[8:16], "big"),
        "dir_length": int.from_bytes(block[16:24], "big"),
        "rr_offset": int.from_bytes(block[24:32], "big"),
        "rr_length": int.from_bytes(block[32:40], "big"),
        "archive_id": block[40:56],
    }


def _recovery_aux(dir_offset: int, dir_length: int, archive_id: bytes) -> bytes:
    return b"BSA1" + dir_offset.to_bytes(8, "big") + dir_length.to_bytes(8, "big") + archive_id


def _parse_aux(aux: bytes):
    if len(aux) != 36 or aux[:4] != b"BSA1":
        raise BrisartArchiveError("recovery record does not belong to a BSA archive")
    return int.from_bytes(aux[4:12], "big"), int.from_bytes(aux[12:20], "big"), aux[20:36]


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def build_archive(
    members,
    *,
    key: bytes | None = None,
    password=None,
    kdf_params: KdfParams | None = None,
    solid: bool = False,
    compression: str = DEFAULT_COMPRESSION,
    comment: str = "",
    recovery_percent: int = 0,
    recovery_chunk_size: int = 4096,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rng=None,
    _validate_names: bool = True,
) -> bytes:
    """Build an archive in memory.

    ``members`` is an iterable of ``(name, data, mtime, comment)`` tuples, with
    an optional fifth item ``executable`` (bool).
    """
    if compression not in COMPRESSION_METHODS:
        raise BrisartArchiveError(f"compression must be one of {COMPRESSION_METHODS}")
    if type(recovery_percent) is not int or not 0 <= recovery_percent <= 50:
        raise BrisartArchiveError("recovery_percent must be between 0 and 50")
    entries = []
    seen = set()
    for item in members:
        if len(entries) >= MAX_ENTRIES:
            raise BrisartArchiveError("too many archive members")
        name, data, mtime, member_comment = item[:4]
        executable = bool(item[4]) if len(item) > 4 else False
        name = normalize_member_name(name) if _validate_names else name
        folded = name.casefold()
        if folded in seen:
            raise BrisartArchiveError(f"duplicate member name: {name!r}")
        seen.add(folded)
        if not isinstance(data, bytes):
            raise BrisartArchiveError("member data must be bytes")
        if type(mtime) is not int or mtime < 0:
            raise BrisartArchiveError("member mtime must be a non-negative integer")
        entries.append(
            {
                "name": name,
                "size": len(data),
                "mtime": mtime,
                "executable": executable,
                "crc32": zlib.crc32(data),
                "comment": _comment(member_comment),
                "data": data,
            }
        )
    comment = _comment(comment)
    flags = (FLAG_SOLID if solid else 0) | (FLAG_PASSWORD if password is not None else 0)
    archive_id = system_entropy(ARCHIVE_ID_BYTES)
    if password is not None:
        params = kdf_params if kdf_params is not None else new_params()
        if not isinstance(params, KdfParams):
            raise BrisartArchiveError("kdf_params must be a KdfParams instance")
        kdf_block = params.encode()
    else:
        params = None
        kdf_block = bytes(ENCODED_PARAMS_BYTES)
    keyed_part = MAGIC + FORMAT_VERSION.to_bytes(2, "big") + flags.to_bytes(2, "big") + archive_id + kdf_block
    archive_key = _archive_key(_master_key(key, password, params), keyed_part)
    preamble_ad = keyed_part + _key_check(archive_key, keyed_part)
    preamble = preamble_ad + zlib.crc32(preamble_ad).to_bytes(4, "big")
    id_hex = hex_encode(archive_id)

    output = bytearray(preamble)
    directory = {
        "format": "BSA-DIRECTORY",
        "version": 1,
        "comment": comment,
        "solid": solid,
        "compression": compression,
        "entries": [],
    }
    if solid:
        joined = b"".join(entry["data"] for entry in entries)
        packed = _compress(joined, compression)
        blob = encrypt_bytes(archive_key, packed, context=f"bsa:{id_hex}:solid", associated_data=preamble_ad, chunk_size=chunk_size, rng=rng)
        directory["solid_block"] = {"offset": len(output), "length": len(blob), "unpacked": len(joined)}
        output.extend(blob)
        position = 0
        for entry in entries:
            record = {k: entry[k] for k in ("name", "size", "mtime", "executable", "crc32", "comment")}
            record["solid_offset"] = position
            position += entry["size"]
            directory["entries"].append(record)
    else:
        for index, entry in enumerate(entries):
            packed = _compress(entry["data"], compression)
            method = compression
            if compression != "store" and len(packed) >= len(entry["data"]):
                packed, method = entry["data"], "store"
            blob = encrypt_bytes(archive_key, packed, context=f"bsa:{id_hex}:entry:{index}", associated_data=preamble_ad, chunk_size=chunk_size, rng=rng)
            record = {k: entry[k] for k in ("name", "size", "mtime", "executable", "crc32", "comment")}
            record.update({"compression": method, "offset": len(output), "length": len(blob)})
            directory["entries"].append(record)
            output.extend(blob)
    directory_json = json.dumps(directory, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sealed_directory = seal(archive_key, directory_json, f"bsa:{id_hex}:directory", associated_data=preamble_ad, rng=rng, padding="padme")
    dir_offset = len(output)
    output.extend(sealed_directory)
    dir_length = len(sealed_directory)
    rr_offset = len(output)
    rr_length = 0
    if recovery_percent:
        record = build_recovery(
            bytes(output),
            chunk_size=recovery_chunk_size,
            redundancy_percent=recovery_percent,
            aux=_recovery_aux(dir_offset, dir_length, archive_id),
        )
        output.extend(record)
        rr_length = len(record)
    footer = _footer(dir_offset, dir_length, rr_offset, rr_length, archive_id)
    output.extend(footer + footer)
    return bytes(output)


def _atomic_write(path: str, data: bytes, *, overwrite: bool) -> None:
    path = os.fspath(path)
    if os.path.lexists(path) and not overwrite:
        raise BrisartArchiveError(f"refusing to overwrite existing path: {path}")
    directory = os.path.dirname(os.path.abspath(path))
    temporary = os.path.join(directory, f".{os.path.basename(path)}.{hex_encode(system_entropy(6))}.partial")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise


def collect_files(inputs, *, base_dir: str | None = None):
    """Walk files/directories into (name, path) pairs; returns (pairs, skipped)."""
    pairs = []
    skipped = []
    for raw in inputs:
        root = os.path.abspath(os.fspath(raw))
        anchor = os.path.abspath(base_dir) if base_dir else os.path.dirname(root)
        if os.path.islink(root):
            skipped.append((root, "symlink"))
            continue
        if os.path.isfile(root):
            candidates = [root]
        elif os.path.isdir(root):
            candidates = []
            for current, dirs, files in os.walk(root, followlinks=False):
                dirs.sort()
                for name in sorted(files):
                    candidates.append(os.path.join(current, name))
        else:
            skipped.append((root, "not a regular file or directory"))
            continue
        for path in candidates:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                skipped.append((path, "symlink"))
                continue
            if not stat.S_ISREG(info.st_mode):
                skipped.append((path, "special file"))
                continue
            relative = os.path.relpath(path, anchor)
            if relative.startswith(".."):
                raise BrisartArchiveError(f"input {path} is outside base directory {anchor}")
            pairs.append((relative.replace(os.sep, "/"), path))
    return pairs, skipped


def create_archive(
    output_path: str,
    inputs,
    *,
    base_dir: str | None = None,
    overwrite: bool = False,
    file_comments: dict | None = None,
    **options,
) -> dict:
    """Create ``output_path`` from files and directories. Returns a summary."""
    pairs, skipped = collect_files(inputs, base_dir=base_dir)
    if not pairs:
        raise BrisartArchiveError("no regular files to archive")
    file_comments = file_comments or {}
    members = []
    for name, path in pairs:
        with open(path, "rb") as handle:
            data = handle.read()
        info = os.stat(path)
        executable = bool(info.st_mode & stat.S_IXUSR)
        members.append((name, data, int(info.st_mtime), file_comments.get(name, ""), executable))
    blob = build_archive(members, **options)
    _atomic_write(output_path, blob, overwrite=overwrite)
    return {"archive": os.fspath(output_path), "members": len(members), "bytes": len(blob), "skipped": skipped}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _locate(blob: bytes) -> dict:
    for end in (len(blob), len(blob) - FOOTER_BYTES):
        if end - FOOTER_BYTES < PREAMBLE_BYTES:
            continue
        footer = _parse_footer(blob[end - FOOTER_BYTES:end])
        if footer is not None:
            return footer
    raise BrisartArchiveError("archive footers are damaged; run repair")


def _parse_preamble(blob: bytes) -> dict:
    if len(blob) < PREAMBLE_BYTES + 2 * FOOTER_BYTES:
        raise BrisartArchiveError("file is too small to be a BSA archive")
    if blob[:8] != MAGIC:
        raise BrisartArchiveError("not a Brisart Secure Archive")
    preamble = blob[:PREAMBLE_BYTES]
    if zlib.crc32(preamble[:PREAMBLE_AD_BYTES]).to_bytes(4, "big") != preamble[PREAMBLE_AD_BYTES:]:
        raise BrisartArchiveError("archive preamble is damaged; run repair")
    version = int.from_bytes(preamble[8:10], "big")
    flags = int.from_bytes(preamble[10:12], "big")
    if version != FORMAT_VERSION:
        raise BrisartArchiveError("unsupported archive format version")
    if flags & ~KNOWN_FLAGS:
        raise BrisartArchiveError("archive uses unknown flags")
    kdf_block = preamble[28:28 + ENCODED_PARAMS_BYTES]
    return {
        "flags": flags,
        "archive_id": preamble[12:28],
        "kdf_block": kdf_block,
        "keyed_part": preamble[:_KEYED_PART],
        "key_check": preamble[_KEYED_PART:PREAMBLE_AD_BYTES],
        "preamble_ad": preamble[:PREAMBLE_AD_BYTES],
    }


def _require_int_field(record: dict, name: str, minimum: int = 0) -> int:
    value = record.get(name)
    if type(value) is not int or value < minimum:
        raise BrisartArchiveError(f"directory field {name!r} is invalid")
    return value


def _validate_directory(directory, blob_length: int, data_end: int) -> dict:
    if not isinstance(directory, dict) or directory.get("format") != "BSA-DIRECTORY" or directory.get("version") != 1:
        raise BrisartArchiveError("archive directory has an unknown format")
    if not isinstance(directory.get("solid"), bool) or directory.get("compression") not in COMPRESSION_METHODS:
        raise BrisartArchiveError("archive directory header is invalid")
    _comment(directory.get("comment"))
    entries = directory.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise BrisartArchiveError("archive directory entries are invalid")
    seen = set()
    for record in entries:
        if not isinstance(record, dict):
            raise BrisartArchiveError("archive directory entry is invalid")
        record["name"] = normalize_member_name(record.get("name"))
        if record["name"].casefold() in seen:
            raise BrisartArchiveError("archive directory contains duplicate names")
        seen.add(record["name"].casefold())
        for field in ("size", "mtime", "crc32"):
            _require_int_field(record, field)
        if not isinstance(record.get("executable"), bool):
            raise BrisartArchiveError("directory field 'executable' is invalid")
        _comment(record.get("comment"))
        if directory["solid"]:
            _require_int_field(record, "solid_offset")
        else:
            if record.get("compression") not in COMPRESSION_METHODS:
                raise BrisartArchiveError("directory entry compression is invalid")
            offset = _require_int_field(record, "offset", PREAMBLE_BYTES)
            length = _require_int_field(record, "length", 1)
            if offset + length > data_end:
                raise BrisartArchiveError("directory entry points outside the data region")
    if directory["solid"]:
        block = directory.get("solid_block")
        if not isinstance(block, dict):
            raise BrisartArchiveError("solid block descriptor is missing")
        offset = _require_int_field(block, "offset", PREAMBLE_BYTES)
        length = _require_int_field(block, "length", 1)
        unpacked = _require_int_field(block, "unpacked")
        if offset + length > data_end:
            raise BrisartArchiveError("solid block points outside the data region")
        if sum(r["size"] for r in entries) != unpacked:
            raise BrisartArchiveError("solid block size does not match its members")
        position = 0
        for record in entries:
            if record["solid_offset"] != position:
                raise BrisartArchiveError("solid member offsets are inconsistent")
            position += record["size"]
    return directory


class ArchiveReader:
    """Authenticated, read-only view of an archive held in memory."""

    def __init__(
        self,
        blob: bytes,
        *,
        key: bytes | None = None,
        password=None,
        max_unpacked_bytes: int = DEFAULT_MAX_UNPACKED_BYTES,
        max_kdf_memory_blocks: int = 1 << 20,
    ):
        if not isinstance(blob, bytes):
            raise BrisartArchiveError("archive must be bytes")
        self._blob = blob
        self._max_unpacked = max_unpacked_bytes
        header = _parse_preamble(blob)
        footer = _locate(blob)
        if footer["archive_id"] != header["archive_id"]:
            raise BrisartArchiveError("archive footer does not match the preamble")
        if header["flags"] & FLAG_PASSWORD:
            if password is None:
                raise BrisartArchiveError("this archive is password protected")
            try:
                params = KdfParams.decode(header["kdf_block"], max_memory_blocks=max_kdf_memory_blocks)
            except BrisartKdfError as exc:
                raise BrisartArchiveError(f"archive KDF parameters rejected: {exc}") from exc
            self.kdf = params
            master = _master_key(None, password, params, max_memory_blocks=max_kdf_memory_blocks)
        else:
            if key is None:
                raise BrisartArchiveError("this archive requires a key file")
            if any(header["kdf_block"]):
                raise BrisartArchiveError("archive KDF block must be empty in key mode")
            self.kdf = None
            master = _master_key(key, None, None)
        self._key = _archive_key(master, header["keyed_part"])
        if not constant_time_equal(_key_check(self._key, header["keyed_part"]), header["key_check"]):
            raise BrisartArchiveError("wrong key or password")
        self._ad = header["preamble_ad"]
        self.archive_id = header["archive_id"]
        self._id_hex = hex_encode(self.archive_id)
        self.flags = header["flags"]
        end = footer["dir_offset"] + footer["dir_length"]
        if footer["dir_offset"] < PREAMBLE_BYTES or end > len(blob) or footer["dir_length"] > MAX_DIRECTORY_BYTES:
            raise BrisartArchiveError("archive directory location is invalid")
        try:
            directory_json = unseal(
                self._key,
                blob[footer["dir_offset"]:end],
                f"bsa:{self._id_hex}:directory",
                associated_data=self._ad,
                max_plaintext_bytes=MAX_DIRECTORY_BYTES,
            )
            directory = json.loads(directory_json.decode("utf-8"))
        except BrisartSealError as exc:
            raise BrisartArchiveError("archive directory failed authentication") from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise BrisartArchiveError("archive directory is not valid JSON") from exc
        self.directory = _validate_directory(directory, len(blob), footer["dir_offset"])
        if bool(self.flags & FLAG_SOLID) != self.directory["solid"]:
            raise BrisartArchiveError("solid flag does not match the directory")
        total = sum(record["size"] for record in self.directory["entries"])
        if total > max_unpacked_bytes:
            raise BrisartArchiveError("archive exceeds the permitted unpacked size")
        self.footer = footer
        self._solid_cache: bytes | None = None

    @property
    def entries(self) -> list[dict]:
        return [dict(record) for record in self.directory["entries"]]

    @property
    def comment(self) -> str:
        return self.directory["comment"]

    def _open_stream(self, offset: int, length: int, context: str, expected: int) -> bytes:
        try:
            return decrypt_bytes(
                self._key,
                self._blob[offset:offset + length],
                context=context,
                associated_data=self._ad,
                max_plaintext_bytes=expected + 1024 + expected // 2 + 64 * 1024,
            )
        except BrisartStreamError as exc:
            raise BrisartArchiveError(f"archive data failed authentication ({context.rsplit(':', 1)[-1]})") from exc

    def _solid(self) -> bytes:
        if self._solid_cache is None:
            block = self.directory["solid_block"]
            packed = self._open_stream(block["offset"], block["length"], f"bsa:{self._id_hex}:solid", block["unpacked"])
            self._solid_cache = _decompress(packed, self.directory["compression"], block["unpacked"])
        return self._solid_cache

    def _record(self, name: str) -> tuple[int, dict]:
        for index, record in enumerate(self.directory["entries"]):
            if record["name"] == name:
                return index, record
        raise BrisartArchiveError(f"no such member: {name!r}")

    def read(self, name: str) -> bytes:
        index, record = self._record(name)
        if self.directory["solid"]:
            data = self._solid()[record["solid_offset"]:record["solid_offset"] + record["size"]]
        else:
            packed = self._open_stream(record["offset"], record["length"], f"bsa:{self._id_hex}:entry:{index}", record["size"])
            data = _decompress(packed, record["compression"], record["size"])
        if len(data) != record["size"] or zlib.crc32(data) != record["crc32"]:
            raise BrisartArchiveError(f"member {name!r} failed its size/CRC check")
        return data

    def test(self) -> dict:
        """Authenticate and decompress every member without writing anything."""
        checked = 0
        total = 0
        for record in self.directory["entries"]:
            total += len(self.read(record["name"]))
            checked += 1
        return {"members": checked, "bytes": total, "status": "OK"}

    def extract(self, destination: str, *, members=None, overwrite: bool = False) -> list[str]:
        """Extract members safely under ``destination``. Returns written paths."""
        root = os.path.realpath(os.fspath(destination))
        os.makedirs(root, exist_ok=True)
        wanted = None if members is None else set(members)
        plan = []
        for record in self.directory["entries"]:
            if wanted is not None and record["name"] not in wanted:
                continue
            name = normalize_member_name(record["name"])
            target = os.path.join(root, *name.split("/"))
            resolved = os.path.realpath(target)
            if os.path.commonpath([root, resolved]) != root or resolved == root:
                raise BrisartArchiveError(f"member escapes the destination: {name!r}")
            if os.path.lexists(target) and not overwrite:
                raise BrisartArchiveError(f"refusing to overwrite existing file: {target}")
            plan.append((record, target))
        if wanted is not None:
            missing = wanted - {record["name"] for record, _ in plan}
            if missing:
                raise BrisartArchiveError(f"no such member(s): {sorted(missing)}")
        written = []
        for record, target in plan:
            data = self.read(record["name"])
            parent = os.path.dirname(target)
            os.makedirs(parent, exist_ok=True)
            if os.path.commonpath([root, os.path.realpath(parent)]) != root:
                raise BrisartArchiveError(f"member parent escapes the destination: {record['name']!r}")
            if os.path.islink(target):
                raise BrisartArchiveError(f"refusing to write through a symlink: {target}")
            _atomic_write(target, data, overwrite=overwrite)
            if os.name == "posix":
                os.chmod(target, 0o755 if record["executable"] else 0o644)
            os.utime(target, (record["mtime"], record["mtime"]))
            written.append(target)
        return written


def open_archive(path: str, **kwargs) -> ArchiveReader:
    with open(os.fspath(path), "rb") as handle:
        return ArchiveReader(handle.read(), **kwargs)


# ---------------------------------------------------------------------------
# Recovery and repair
# ---------------------------------------------------------------------------

def _find_internal_record(blob: bytes):
    footer = None
    for end in (len(blob), len(blob) - FOOTER_BYTES):
        if end - FOOTER_BYTES >= 0:
            footer = _parse_footer(blob[end - FOOTER_BYTES:end])
            if footer is not None:
                break
    if footer is not None and footer["rr_length"]:
        start, length = footer["rr_offset"], footer["rr_length"]
        try:
            return parse_recovery(blob[start:start + length]), blob[start:start + length]
        except BrisartRecoveryError:
            pass
    position = len(blob)
    while True:
        position = blob.rfind(RECOVERY_MAGIC, 0, position)
        if position < 0:
            return None, None
        head = blob[position:position + 30]
        if len(head) == 30:
            chunk_size = int.from_bytes(head[8:12], "big")
            parity = int.from_bytes(head[12:16], "big")
            data_length = int.from_bytes(head[16:24], "big")
            aux_length = int.from_bytes(head[28:30], "big")
            if chunk_size and data_length == position:
                chunks = -(-data_length // chunk_size)
                size = 30 + aux_length + 8 * (chunks + parity) + 4 + parity * chunk_size
                candidate = blob[position:position + size]
                try:
                    return parse_recovery(candidate), candidate
                except BrisartRecoveryError:
                    pass


def create_external_record(archive_path: str, record_path: str, *, redundancy_percent: int = 10, chunk_size: int = 4096, overwrite: bool = False) -> dict:
    """Write an external ``.bsrr`` record covering the archive's protected region."""
    with open(os.fspath(archive_path), "rb") as handle:
        blob = handle.read()
    header = _parse_preamble(blob)
    footer = _locate(blob)
    region_end = footer["dir_offset"] + footer["dir_length"]
    record = build_recovery(
        blob[:region_end],
        chunk_size=chunk_size,
        redundancy_percent=redundancy_percent,
        aux=_recovery_aux(footer["dir_offset"], footer["dir_length"], header["archive_id"]),
    )
    _atomic_write(record_path, record, overwrite=overwrite)
    return {"record": os.fspath(record_path), "bytes": len(record), "protected_bytes": region_end}


def repair_archive(archive_path: str, output_path: str, *, external_record: str | None = None, overwrite: bool = False) -> dict:
    """Repair damage using an internal or external recovery record (no key needed)."""
    with open(os.fspath(archive_path), "rb") as handle:
        blob = handle.read()
    if external_record is not None:
        with open(os.fspath(external_record), "rb") as handle:
            record_blob = handle.read()
        try:
            record = parse_recovery(record_blob)
        except BrisartRecoveryError as exc:
            raise BrisartArchiveError(f"external recovery record is unusable: {exc}") from exc
        source = "external"
    else:
        record, record_blob = _find_internal_record(blob)
        if record is None:
            raise BrisartArchiveError("no usable recovery record found")
        source = "internal"
    dir_offset, dir_length, archive_id = _parse_aux(record.aux)
    try:
        region, report = repair_bytes(blob[:record.data_length], record)
    except BrisartRecoveryError as exc:
        raise BrisartArchiveError(str(exc)) from exc
    internal_blob = b""
    footer_now = None
    for end in (len(blob), len(blob) - FOOTER_BYTES):
        if end - FOOTER_BYTES >= 0 and footer_now is None:
            footer_now = _parse_footer(blob[end - FOOTER_BYTES:end])
    if source == "internal":
        internal_blob = record_blob
    elif footer_now is not None and footer_now["rr_length"]:
        candidate = blob[footer_now["rr_offset"]:footer_now["rr_offset"] + footer_now["rr_length"]]
        try:
            parse_recovery(candidate)
            internal_blob = candidate
        except BrisartRecoveryError:
            internal_blob = b""
    rr_offset = len(region)
    footer = _footer(dir_offset, dir_length, rr_offset, len(internal_blob), archive_id)
    repaired = region + internal_blob + footer + footer
    report.update({"record": source, "output": os.fspath(output_path), "bytes": len(repaired)})
    report["footers_rebuilt"] = repaired[-2 * FOOTER_BYTES:] != blob[-2 * FOOTER_BYTES:]
    _atomic_write(output_path, repaired, overwrite=overwrite)
    return report


# ---------------------------------------------------------------------------
# Multi-volume
# ---------------------------------------------------------------------------

def split_volumes(archive_path: str, volume_bytes: int, *, overwrite: bool = False) -> list[str]:
    """Split a file into ``<name>.001``, ``<name>.002`` ... volumes."""
    if type(volume_bytes) is not int or volume_bytes < MIN_VOLUME_BYTES:
        raise BrisartArchiveError("volume size must be at least 1024 bytes")
    with open(os.fspath(archive_path), "rb") as handle:
        blob = handle.read()
    payload = volume_bytes - VOLUME_HEADER_BYTES
    parts = [blob[i:i + payload] for i in range(0, len(blob), payload)] or [b""]
    if len(parts) > 999:
        raise BrisartArchiveError("too many volumes; choose a larger volume size")
    set_id = system_entropy(16)
    paths = []
    for index, part in enumerate(parts):
        header = (
            VOLUME_MAGIC
            + set_id
            + index.to_bytes(4, "big")
            + len(parts).to_bytes(4, "big")
            + len(part).to_bytes(8, "big")
            + zlib.crc32(part).to_bytes(4, "big")
        )
        path = f"{os.fspath(archive_path)}.{index + 1:03d}"
        _atomic_write(path, header + part, overwrite=overwrite)
        paths.append(path)
    return paths


def join_volumes(volume_paths, output_path: str, *, overwrite: bool = False) -> dict:
    """Validate and concatenate volumes produced by ``split_volumes``."""
    volumes = {}
    set_id = None
    count = None
    for path in volume_paths:
        with open(os.fspath(path), "rb") as handle:
            data = handle.read()
        if len(data) < VOLUME_HEADER_BYTES or data[:8] != VOLUME_MAGIC:
            raise BrisartArchiveError(f"not a BSA volume: {path}")
        this_set = data[8:24]
        index = int.from_bytes(data[24:28], "big")
        this_count = int.from_bytes(data[28:32], "big")
        length = int.from_bytes(data[32:40], "big")
        payload = data[VOLUME_HEADER_BYTES:]
        if len(payload) != length or zlib.crc32(payload).to_bytes(4, "big") != data[40:44]:
            raise BrisartArchiveError(f"volume is damaged: {path}")
        if set_id is None:
            set_id, count = this_set, this_count
        elif this_set != set_id or this_count != count:
            raise BrisartArchiveError(f"volume belongs to a different set: {path}")
        if index in volumes:
            raise BrisartArchiveError(f"duplicate volume index {index + 1}")
        volumes[index] = payload
    if count is None or sorted(volumes) != list(range(count)):
        raise BrisartArchiveError("volume set is incomplete")
    blob = b"".join(volumes[i] for i in range(count))
    _atomic_write(output_path, blob, overwrite=overwrite)
    return {"output": os.fspath(output_path), "volumes": count, "bytes": len(blob)}
