"""
engine.folder_scanner
---------------------
Walks a source folder, applies ArchiveSettings exclusion rules and size
limits, and produces a ScanResult plus a readable folder tree.

This module performs no writes — see engine.snapshot_writer and
engine.snapshot_builder for that.
"""
from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

from .settings import ArchiveSettings, FileRecord, ScanResult, SkipRecord


def validate_root(path_value: str | Path) -> Path:
    """
    Resolve and validate an archive source folder.
    """

    root = Path(path_value).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"Archive source folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Archive source path is not a folder: {root}")

    return root


def relative_string(path: Path, root: Path) -> str:
    """
    Return a safe relative path string.
    """

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_size(path: Path) -> int | None:
    """
    Return file size, or None if unavailable.
    """

    try:
        return path.stat().st_size
    except OSError:
        return None


def modified_time(path: Path) -> str:
    """
    Return file modified time as a readable timestamp.
    """

    try:
        value = datetime.datetime.fromtimestamp(path.stat().st_mtime).astimezone()
        return value.strftime("%Y-%m-%d %H:%M:%S %z")
    except OSError:
        return ""


def sha256_file(path: Path) -> str | None:
    """
    Generate a SHA256 checksum for a file.
    """

    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return None


def exclusion_reason(path: Path, root: Path, settings: ArchiveSettings) -> str | None:
    """
    Return a reason string if the path should be excluded, otherwise None.
    """

    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return "outside_root"

    for part in relative_parts:
        if part in settings.excluded_dirs:
            return f"excluded_directory:{part}"

    if path.name in settings.excluded_files:
        return f"excluded_file:{path.name}"

    suffix = path.suffix.lower()
    if suffix in settings.excluded_suffixes:
        return f"excluded_suffix:{suffix}"

    return None


def should_include_file(
    path: Path,
    root: Path,
    settings: ArchiveSettings,
    current_total_bytes: int,
) -> tuple[bool, SkipRecord | None]:
    """
    Decide whether a file should be included in the scan.
    """

    relative_path = relative_string(path, root)

    if not path.is_file():
        return False, None

    reason = exclusion_reason(path, root, settings)
    if reason:
        return False, SkipRecord(
            relative_path=relative_path,
            reason=reason,
            size_bytes=safe_size(path),
        )

    size = safe_size(path)
    if size is None:
        return False, SkipRecord(
            relative_path=relative_path,
            reason="size_unavailable",
            size_bytes=None,
        )

    if size > settings.max_file_bytes:
        return False, SkipRecord(
            relative_path=relative_path,
            reason="file_too_large",
            size_bytes=size,
        )

    if current_total_bytes + size > settings.max_total_bytes:
        return False, SkipRecord(
            relative_path=relative_path,
            reason="total_size_limit",
            size_bytes=size,
        )

    return True, None


def scan_folder(root: Path, settings: ArchiveSettings) -> ScanResult:
    """
    Scan the source folder and build a ScanResult.
    """

    included_paths: list[Path] = []
    included_records: list[FileRecord] = []
    skipped_records: list[SkipRecord] = []
    total_bytes = 0

    for path in sorted(root.rglob("*")):
        include, skip = should_include_file(
            path=path,
            root=root,
            settings=settings,
            current_total_bytes=total_bytes,
        )

        if skip is not None:
            skipped_records.append(skip)
            continue

        if not include:
            continue

        size = safe_size(path)
        if size is None:
            skipped_records.append(
                SkipRecord(
                    relative_path=relative_string(path, root),
                    reason="size_unavailable",
                    size_bytes=None,
                )
            )
            continue

        checksum = sha256_file(path) if settings.include_hashes else None

        included_paths.append(path)
        included_records.append(
            FileRecord(
                relative_path=relative_string(path, root),
                size_bytes=size,
                modified_time=modified_time(path),
                extension=path.suffix.lower() or path.name.lower(),
                sha256=checksum,
            )
        )
        total_bytes += size

    return ScanResult(
        included_paths=included_paths,
        included_records=included_records,
        skipped_records=skipped_records,
        total_included_bytes=total_bytes,
    )


def build_folder_tree(root: Path, settings: ArchiveSettings) -> str:
    """
    Build a readable folder tree, honoring the same exclusion rules as
    the scan.
    """

    lines: list[str] = [root.name + "/"]

    def walk(directory: Path, prefix: str = "") -> None:
        try:
            entries = sorted(
                [
                    entry
                    for entry in directory.iterdir()
                    if not exclusion_reason(entry, root, settings)
                ],
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
        except OSError:
            return

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            label = entry.name + "/" if entry.is_dir() else entry.name
            lines.append(prefix + connector + label)

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension)

    walk(root)
    return "\n".join(lines)