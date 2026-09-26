"""
File: services/updater/archive_safety.py

Purpose:
Validate downloaded ZIP archives (signature bytes, path traversal,
zip-bomb limits, integrity) and compute SHA-256 file hashes.

Communication / relationships:
- services/updater/download.py calls validate_zip_archive() and
  sha256_of_file().
- Limits come from services/updater/constants.py.

Settings / parameters:
- MAX_DOWNLOAD_BYTES 250 MiB; MAX_ZIP_MEMBERS 25,000;
  MAX_UNCOMPRESSED_ZIP_BYTES 2 GiB; MAX_COMPRESSION_RATIO 250.

Edge cases:
- Rejects member names that are empty, absolute, contain "..", start
  with a drive letter, or contain NUL.
- Rejects entries that claim data but have a compressed size of zero.
- Runs zipfile.testzip() to catch corrupted members.

Known limitations:
- Hashing reads the file in 1 MiB chunks; very large files take time.

Examples:
- validate_zip_archive(path)
- sha256_of_file(path)
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from services.updater.constants import (
    MAX_COMPRESSION_RATIO,
    MAX_DOWNLOAD_BYTES,
    MAX_UNCOMPRESSED_ZIP_BYTES,
    MAX_ZIP_MEMBERS,
)


def file_has_zip_signature(path: Path) -> bool:
    path = Path(path)
    try:
        with open(path, "rb") as file:
            signature = file.read(4)
    except OSError:
        return False
    return signature in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}


def zip_member_is_safe(member_name: str) -> bool:
    normalized = str(member_name).replace("\\", "/")
    if not normalized or normalized.startswith("/") or "\x00" in normalized:
        return False
    path_parts = [part for part in normalized.split("/") if part]
    if not path_parts or any(part in {".", ".."} for part in path_parts):
        return False
    first_part = path_parts[0]
    if len(first_part) >= 2 and first_part[1] == ":":
        return False
    return True


def validate_zip_archive(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ZIP file was not found: {path}")
    file_size = path.stat().st_size
    if file_size < 1:
        raise ValueError("The downloaded update was empty.")
    if file_size > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"The downloaded update exceeds the maximum allowed size of {MAX_DOWNLOAD_BYTES:,} bytes.")
    if not file_has_zip_signature(path):
        raise ValueError("The downloaded file does not have a valid ZIP signature.")
    if not zipfile.is_zipfile(path):
        raise ValueError("The downloaded file is not a readable ZIP archive.")
    with zipfile.ZipFile(path, "r") as archive:
        members = archive.infolist()
        if not members:
            raise ValueError("The downloaded ZIP contains no files.")
        if len(members) > MAX_ZIP_MEMBERS:
            raise ValueError(f"The downloaded ZIP contains too many entries: {len(members):,}")
        total_uncompressed_bytes = 0
        for member in members:
            if not zip_member_is_safe(member.filename):
                raise ValueError(f"The downloaded ZIP contains an unsafe path: {member.filename!r}")
            total_uncompressed_bytes += member.file_size
            if total_uncompressed_bytes > MAX_UNCOMPRESSED_ZIP_BYTES:
                raise ValueError("The downloaded ZIP expands beyond the allowed uncompressed-size limit.")
            if member.file_size > 0 and member.compress_size == 0 and not member.is_dir():
                raise ValueError(f"The downloaded ZIP contains an invalid compressed entry: {member.filename!r}")
            if member.compress_size > 0 and member.file_size > 0:
                ratio = member.file_size / member.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError(f"The downloaded ZIP contains an entry with an excessive compression ratio: {member.filename!r}")
        corrupted_member = archive.testzip()
        if corrupted_member is not None:
            raise ValueError(f"ZIP integrity validation failed for: {corrupted_member}")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
