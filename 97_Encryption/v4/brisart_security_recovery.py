"""
File: brisart_security_recovery.py

Purpose
-------
BSRR-1 recovery records: interleaved XOR parity that lets a damaged archive (or
any byte string) be repaired without the key, in the spirit of SQX/RAR
recovery data. Data is cut into fixed chunks; chunk *i* belongs to parity group
*i mod P*. Each group stores one parity block, so any burst of up to *P*
consecutive damaged chunks, or any pattern with at most one damaged chunk per
group, can be rebuilt. Records can live inside an archive or as an external
``.bsrr`` file.

Communication / relationships
-----------------------------
Standard library only (``zlib`` for CRC-32 and Adler-32). Used by
brisart_security_archive.py (internal records, ``repair``) and by the CLI
``rr-create`` / ``rr-repair`` commands; covered by tests/test_recovery.py.

Settings / parameters
---------------------
MAGIC b"BSRR\\x00\\x01\\r\\n"
DEFAULT_CHUNK_SIZE 4096, MIN_CHUNK_SIZE 64, MAX_CHUNK_SIZE 1 MiB
DEFAULT_REDUNDANCY_PERCENT 5  (one parity block per 20 data chunks)
MAX_AUX_BYTES 256  (caller metadata, e.g. archive directory location)
MAX_CHUNKS 2**26

Edge cases
----------
* Damage detection uses CRC-32 plus Adler-32 per chunk (8 bytes). These are
  accident detectors. Authenticity is always re-established afterwards by the
  archive MACs, so a forged "repair" cannot produce accepted plaintext.
* Truncated or over-long data is normalised to the recorded length; missing
  tail chunks are treated as damaged and repaired if their groups allow.
* A damaged parity block only matters if its group also has damaged data.
* The record header and checksum table are protected by their own CRC; a
  damaged record is reported, never trusted.

Known limitations
-----------------
* One parity block per group: two damaged chunks in the same group cannot be
  repaired. Reed-Solomon would tolerate more and is not implemented.
* Repair is in-memory; data size is limited by available RAM.

Examples
--------
>>> from brisart_security_recovery import build_recovery, repair
>>> data = bytes(range(256)) * 64
>>> record = build_recovery(data, chunk_size=256, redundancy_percent=10)
>>> damaged = bytearray(data); damaged[300] ^= 0xFF
>>> repaired, report = repair(bytes(damaged), record)
>>> repaired == data, report["repaired_chunks"]
(True, [1])
"""
import zlib
from dataclasses import dataclass

MAGIC = b"BSRR\x00\x01\r\n"
DEFAULT_CHUNK_SIZE = 4096
MIN_CHUNK_SIZE = 64
MAX_CHUNK_SIZE = 1024 * 1024
DEFAULT_REDUNDANCY_PERCENT = 5
MAX_AUX_BYTES = 256
MAX_CHUNKS = 1 << 26
_FIXED_HEADER = 8 + 4 + 4 + 8 + 4 + 2


class BrisartRecoveryError(Exception):
    """Raised when a recovery record is invalid or damage cannot be repaired."""


def _checksum(block: bytes) -> bytes:
    return zlib.crc32(block).to_bytes(4, "big") + zlib.adler32(block).to_bytes(4, "big")


@dataclass
class RecoveryRecord:
    chunk_size: int
    parity_count: int
    data_length: int
    aux: bytes
    data_checksums: list
    parity_checksums: list
    parity_blocks: list

    @property
    def chunk_count(self) -> int:
        return -(-self.data_length // self.chunk_size)


def _chunks(data: bytes, chunk_size: int) -> list[bytes]:
    return [data[i:i + chunk_size].ljust(chunk_size, b"\x00") for i in range(0, len(data), chunk_size)]


def _xor_blocks(blocks: list[bytes], size: int) -> bytes:
    value = 0
    for block in blocks:
        value ^= int.from_bytes(block, "big")
    return value.to_bytes(size, "big")


def parity_count_for(chunk_count: int, redundancy_percent: int) -> int:
    if type(redundancy_percent) is not int or not 1 <= redundancy_percent <= 50:
        raise BrisartRecoveryError("redundancy must be between 1 and 50 percent")
    if chunk_count == 0:
        return 0
    return max(1, -(-chunk_count * redundancy_percent // 100))


def build_recovery(
    data: bytes,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    redundancy_percent: int = DEFAULT_REDUNDANCY_PERCENT,
    aux: bytes = b"",
) -> bytes:
    """Build a serialized BSRR-1 recovery record for ``data``."""
    if not isinstance(data, bytes):
        raise BrisartRecoveryError("data must be bytes")
    if type(chunk_size) is not int or not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE:
        raise BrisartRecoveryError("chunk size must be between 64 bytes and 1 MiB")
    if not isinstance(aux, bytes) or len(aux) > MAX_AUX_BYTES:
        raise BrisartRecoveryError("aux data must be at most 256 bytes")
    chunks = _chunks(data, chunk_size)
    if len(chunks) > MAX_CHUNKS:
        raise BrisartRecoveryError("data has too many chunks for a recovery record")
    parity_count = parity_count_for(len(chunks), redundancy_percent)
    groups: list[list[bytes]] = [[] for _ in range(parity_count)]
    for index, chunk in enumerate(chunks):
        groups[index % parity_count].append(chunk)
    parity = [_xor_blocks(group, chunk_size) for group in groups]
    head = (
        MAGIC
        + chunk_size.to_bytes(4, "big")
        + parity_count.to_bytes(4, "big")
        + len(data).to_bytes(8, "big")
        + zlib.crc32(data).to_bytes(4, "big")
        + len(aux).to_bytes(2, "big")
        + aux
        + b"".join(_checksum(chunk) for chunk in chunks)
        + b"".join(_checksum(block) for block in parity)
    )
    return head + zlib.crc32(head).to_bytes(4, "big") + b"".join(parity)


def parse_recovery(blob: bytes) -> RecoveryRecord:
    """Parse and integrity-check a serialized recovery record."""
    if not isinstance(blob, bytes) or len(blob) < _FIXED_HEADER + 4 or blob[:8] != MAGIC:
        raise BrisartRecoveryError("not a BSRR-1 recovery record")
    chunk_size = int.from_bytes(blob[8:12], "big")
    parity_count = int.from_bytes(blob[12:16], "big")
    data_length = int.from_bytes(blob[16:24], "big")
    aux_length = int.from_bytes(blob[28:30], "big")
    if not MIN_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE or aux_length > MAX_AUX_BYTES:
        raise BrisartRecoveryError("recovery record header is invalid")
    chunk_count = -(-data_length // chunk_size)
    if chunk_count > MAX_CHUNKS or parity_count > chunk_count or (chunk_count and not parity_count):
        raise BrisartRecoveryError("recovery record header is invalid")
    table_start = _FIXED_HEADER + aux_length
    table_end = table_start + 8 * (chunk_count + parity_count)
    expected = table_end + 4 + parity_count * chunk_size
    if len(blob) != expected:
        raise BrisartRecoveryError("recovery record has the wrong length")
    if zlib.crc32(blob[:table_end]).to_bytes(4, "big") != blob[table_end:table_end + 4]:
        raise BrisartRecoveryError("recovery record header is damaged")
    table = blob[table_start:table_end]
    checksums = [table[i:i + 8] for i in range(0, len(table), 8)]
    body = blob[table_end + 4:]
    return RecoveryRecord(
        chunk_size=chunk_size,
        parity_count=parity_count,
        data_length=data_length,
        aux=blob[_FIXED_HEADER:table_start],
        data_checksums=checksums[:chunk_count],
        parity_checksums=checksums[chunk_count:],
        parity_blocks=[body[i * chunk_size:(i + 1) * chunk_size] for i in range(parity_count)],
    )


def recorded_crc(blob: bytes) -> int:
    return int.from_bytes(blob[24:28], "big")


def scan(data: bytes, record: RecoveryRecord) -> list[int]:
    """Return indices of chunks whose checksums do not match."""
    normalised = data[:record.data_length].ljust(record.data_length, b"\x00")
    chunks = _chunks(normalised, record.chunk_size)
    bad = [index for index, chunk in enumerate(chunks) if _checksum(chunk) != record.data_checksums[index]]
    if len(data) < record.data_length:
        first_missing = len(data) // record.chunk_size
        bad = sorted(set(bad) | set(range(first_missing, record.chunk_count)))
    return bad


def repair(data: bytes, record_blob) -> tuple[bytes, dict]:
    """Repair ``data`` using a recovery record (bytes or RecoveryRecord)."""
    record = record_blob if isinstance(record_blob, RecoveryRecord) else parse_recovery(record_blob)
    if not isinstance(data, bytes):
        raise BrisartRecoveryError("data must be bytes")
    bad = scan(data, record)
    normalised = data[:record.data_length].ljust(record.data_length, b"\x00")
    chunks = _chunks(normalised, record.chunk_size)
    report = {
        "chunk_count": record.chunk_count,
        "damaged_chunks": list(bad),
        "repaired_chunks": [],
        "length_adjusted": len(data) != record.data_length,
    }
    by_group: dict[int, list[int]] = {}
    for index in bad:
        by_group.setdefault(index % record.parity_count, []).append(index)
    unrecoverable = []
    for group, members in sorted(by_group.items()):
        parity = record.parity_blocks[group]
        if len(members) > 1 or _checksum(parity) != record.parity_checksums[group]:
            unrecoverable.extend(members)
            continue
        target = members[0]
        others = [chunks[i] for i in range(group, record.chunk_count, record.parity_count) if i != target]
        rebuilt = _xor_blocks(others + [parity], record.chunk_size)
        if _checksum(rebuilt) != record.data_checksums[target]:
            unrecoverable.append(target)
            continue
        chunks[target] = rebuilt
        report["repaired_chunks"].append(target)
    if unrecoverable:
        report["unrecoverable_chunks"] = sorted(unrecoverable)
        raise BrisartRecoveryError(
            f"{len(unrecoverable)} damaged chunk(s) cannot be repaired: {sorted(unrecoverable)[:10]}"
        )
    repaired = b"".join(chunks)[:record.data_length]
    return repaired, report
