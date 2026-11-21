"""
File: export/snapshot.py

Purpose
-------
Write PROJECT_SNAPSHOT.zip: the four generated files first, then every captured project
  file under project_files/. Every member is split into 1 MiB blocks that are deflated in
  parallel on the export's capture threads and joined into one valid DEFLATE stream (the
  pigz technique), then written in order by a small standard-library ZIP writer. Python's
  zipfile compresses one member at a time on one core, which made the ZIP the slowest part
  of a large export; this uses every core, even for one large PROJECT_CONTEXT.md.

Communication / relationships
-----------------------------
Imports export/scan.py (ScanResult). Imported only by export/pipeline.py, which passes the
  thread count the scan used. The archives it writes are read back by zipfile in
  tests/test_export.py.

Settings / parameters
---------------------
Members use DEFLATE at level 6 (zipfile's default). BLOCK_BYTES (1 MiB) is the unit of
  parallel work; each block is primed with the previous 32 KiB (DICTIONARY_BYTES) so
  matches can reach back across block edges, and ends with a sync flush, which keeps the
  archive within about 0.1% of zipfile's size. Blocks are queued while the raw bytes in
  flight stay under IN_FLIGHT_BYTES (256 MB), so memory stays bounded for any file size.
  ZIP64 records are written when any size, offset, or the member count passes the classic
  limits (ZIP64_LIMIT, ZIP64_COUNT_LIMIT); a member is given a ZIP64 local header when its
  size is within 5% of the limit, as zipfile does.

Edge cases
----------
Member names use forward slashes and set the UTF-8 flag when not ASCII. Project files take
  the modification time of their staged copy, which export/scan.py sets to the original
  file's time; the four generated files carry the export time. Times are clamped to the
  1980-2107 range ZIP can store, and a time the operating system cannot convert (before 1970
  on Windows) becomes 1980-01-01 instead of failing the export. Permission bits are kept, as zipfile does.
  Each local header is written first and patched with the CRC and sizes once its data is
  written, so the output must be a seekable file. A read error stops the write and raises
  OSError; the pipeline then deletes the staging folder.

Known limitations
-----------------
No encryption, comments, or data descriptors. Compressed bytes differ from zipfile's
  (contents, names, and CRCs are identical), so archive hashes are not comparable across
  versions.

Examples
--------
Usage from the directory containing run.py:
    from pathlib import Path
    from export.snapshot import write_zip
    write_zip(Path("out.zip"), [(Path("a.txt"), "a.txt")], workers=4)
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import os
import struct
import time
import zlib

from export.scan import ScanResult

COMPRESS_LEVEL = 6
BLOCK_BYTES = 1 << 20
DICTIONARY_BYTES = 1 << 15
IN_FLIGHT_BYTES = 256_000_000
ZIP64_LIMIT = 0xFFFFFFFF
ZIP64_COUNT_LIMIT = 0xFFFF
_FULL32 = 0xFFFFFFFF
_FULL16 = 0xFFFF
_CREATE_SYSTEM = 0 if os.name == "nt" else 3


def _field32(value: int) -> int:
    """A classic 32-bit field: the value, or all ones when it lives in the ZIP64 record."""
    return value if value < ZIP64_LIMIT else _FULL32


def _field16(value: int) -> int:
    return value if value <= ZIP64_COUNT_LIMIT else _FULL16


def deflate_block(block: bytes, dictionary: bytes, final: bool) -> bytes:
    """Raw DEFLATE for one block; non-final blocks end byte-aligned so blocks can be joined."""
    if dictionary:
        compressor = zlib.compressobj(COMPRESS_LEVEL, zlib.DEFLATED, -15, zdict=dictionary)
    else:
        compressor = zlib.compressobj(COMPRESS_LEVEL, zlib.DEFLATED, -15)
    return compressor.compress(block) + compressor.flush(zlib.Z_FINISH if final else zlib.Z_SYNC_FLUSH)


def _dos_time(timestamp: float) -> tuple[int, int]:
    try:
        year, month, day, hour, minute, second = time.localtime(timestamp)[:6]
    except (OSError, OverflowError, ValueError):
        # Windows cannot convert times before 1970 (some extracted archives carry 1601 dates),
        # and absurd values overflow; either way the earliest ZIP date is the honest answer.
        year, month, day, hour, minute, second = 1980, 1, 1, 0, 0, 0
    if year < 1980:
        year, month, day, hour, minute, second = 1980, 1, 1, 0, 0, 0
    elif year > 2107:
        year, month, day, hour, minute, second = 2107, 12, 31, 23, 59, 58
    return (hour << 11) | (minute << 5) | (second // 2), ((year - 1980) << 9) | (month << 5) | day


@dataclass(slots=True)
class _Member:
    name: bytes
    flags: int
    mode: int
    dos_time: int
    dos_date: int
    zip64: bool
    crc: int = 0
    size: int = 0
    compressed: int = 0
    offset: int = -1
    version: int = 20


class _Writer:
    """Sequential ZIP output: local headers patched in place, then the central directory."""

    def __init__(self, handle) -> None:
        self.handle = handle
        self.offset = 0
        self.members: list[_Member] = []
        self.open_member: _Member | None = None

    def _write(self, data: bytes) -> None:
        self.handle.write(data)
        self.offset += len(data)

    def start(self, member: _Member) -> None:
        self.finish_member()
        member.offset = self.offset
        member.version = 45 if member.zip64 or member.offset >= ZIP64_LIMIT else 20
        extra = struct.pack("<HHQQ", 1, 16, 0, 0) if member.zip64 else b""
        self._write(struct.pack(
            "<IHHHHHIIIHH", 0x04034B50, member.version, member.flags, 8, member.dos_time, member.dos_date,
            0, 0, 0, len(member.name), len(extra),
        ) + member.name + extra)
        self.members.append(member)
        self.open_member = member

    def data(self, piece: bytes) -> None:
        self.open_member.compressed += len(piece)
        self._write(piece)

    def finish_member(self) -> None:
        member, self.open_member = self.open_member, None
        if member is None:
            return
        if not member.zip64 and (member.size >= ZIP64_LIMIT or member.compressed >= ZIP64_LIMIT):
            raise OSError(f"{member.name.decode('utf-8')} grew past 4 GB while it was being archived.")
        self.handle.seek(member.offset + 14)
        if member.zip64:
            self.handle.write(struct.pack("<III", member.crc, _FULL32, _FULL32))
            self.handle.seek(member.offset + 30 + len(member.name) + 4)
            self.handle.write(struct.pack("<QQ", member.size, member.compressed))
        else:
            self.handle.write(struct.pack("<III", member.crc, member.compressed, member.size))
        self.handle.seek(self.offset)

    def close(self) -> None:
        self.finish_member()
        start = self.offset
        for m in self.members:
            large = [value for value in (m.size, m.compressed, m.offset) if value >= ZIP64_LIMIT]
            extra = struct.pack(f"<HH{len(large)}Q", 1, 8 * len(large), *large) if large else b""
            self._write(struct.pack(
                "<IBBHHHHHIIIHHHHHII", 0x02014B50, m.version, _CREATE_SYSTEM, m.version, m.flags, 8,
                m.dos_time, m.dos_date, m.crc, _field32(m.compressed), _field32(m.size),
                len(m.name), len(extra), 0, 0, 0, (m.mode & 0xFFFF) << 16, _field32(m.offset),
            ) + m.name + extra)
        count, length = len(self.members), self.offset - start
        if count > ZIP64_COUNT_LIMIT or length >= ZIP64_LIMIT or start >= ZIP64_LIMIT:
            end64 = self.offset
            self._write(struct.pack("<IQHHIIQQQQ", 0x06064B50, 44, 45, 45, 0, 0, count, count, length, start))
            self._write(struct.pack("<IIQI", 0x07064B50, 0, end64, 1))
        self._write(struct.pack(
            "<IHHHHIIH", 0x06054B50, 0, 0, _field16(count), _field16(count), _field32(length), _field32(start), 0,
        ))


def write_zip(zip_path: Path, members: list[tuple[Path, str]], workers: int) -> None:
    """Deflate every block on `workers` threads (zlib releases the GIL) and write in order."""
    with open(zip_path, "wb") as handle, ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="pch-zip") as pool:
        writer = _Writer(handle)
        queue: deque[tuple[_Member, bool, Future, int]] = deque()
        in_flight = 0

        def write_oldest() -> None:
            nonlocal in_flight
            member, first, future, raw = queue.popleft()
            if first:
                writer.start(member)
            writer.data(future.result())
            in_flight -= raw

        for source, name in members:
            info = os.stat(source)
            dos_time, dos_date = _dos_time(info.st_mtime)
            member = _Member(
                name=name.encode("utf-8"), flags=0 if name.isascii() else 0x800, mode=info.st_mode,
                dos_time=dos_time, dos_date=dos_date, zip64=info.st_size * 1.05 > ZIP64_LIMIT,
            )
            first, dictionary = True, b""
            with open(source, "rb") as reader:
                block = reader.read(BLOCK_BYTES)
                while True:
                    following = reader.read(BLOCK_BYTES) if block else b""
                    member.crc = zlib.crc32(block, member.crc)
                    member.size += len(block)
                    while queue and in_flight + len(block) > IN_FLIGHT_BYTES:
                        write_oldest()
                    queue.append((member, first, pool.submit(deflate_block, block, dictionary, not following), len(block)))
                    in_flight += len(block)
                    if not following:
                        break
                    first, dictionary, block = False, block[-DICTIONARY_BYTES:], following
        while queue:
            write_oldest()
        writer.close()


def create_snapshot_zip(zip_path: Path, generated: list[Path], scan: ScanResult, root: Path, workers: int) -> None:
    members = [(path, path.name) for path in generated]
    sources = scan.captured_paths or scan.included_paths
    for path, source in zip(scan.included_paths, sources):
        members.append((source, f"project_files/{path.relative_to(root).as_posix()}"))
    write_zip(zip_path, members, workers)
