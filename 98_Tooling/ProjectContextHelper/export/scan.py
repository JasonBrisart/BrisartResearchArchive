"""
File: export/scan.py

Purpose
-------
Decide which project files go into an export and read each of them exactly once: walk the
  project, classify every entry as a candidate or a skip with a reason, apply per-file and
  total byte budgets, capture the selected files on a thread pool, enforce source
  completeness, and render the folder tree. Owns the records describing that result
  (FileRecord, SkipRecord, ScanResult).

Communication / relationships
-----------------------------
Imports app (INTERNAL_NAME_PREFIX), export/events.py (Progress, checkpoint), and
  export/settings.py (ScanSettings, resolve_workers). Imported by export/pipeline.py
  (collect_included_files, ScanResult) and export/render.py (records, build_tree,
  SOURCE_COMPLETENESS_FAILURE_REASONS).

Settings / parameters
---------------------
Reads the extension and exclusion sets, both byte limits, the hash and line-count toggles,
  require_complete_source, and workers from ScanSettings. The thread count is
  resolve_workers(settings.workers) and is returned as ScanResult.workers_used. Files are
  captured in batches of twice that count. With a spool_dir, captured bytes are written to
  spool_dir/<relative path> and listed in captured_paths; without one, they are discarded.

Six skip reasons fail completeness: file_too_large, total_size_limit, size_unavailable,
  read_unavailable, source_changed, directory_unavailable. Intentional skips do not:
  excluded_directory/file/suffix, extension_not_included, symlink_not_followed,
  not_a_regular_file, export_output_directory, internal_tool_file.

Edge cases
----------
Budgets apply in sorted path order, so the worker count never changes which files are
  included. A file exactly at the limit fits. After the total budget is hit, smaller files
  later in order can still fit. A file whose size changed between discovery and capture is
  skipped as source_changed. Compound extensions such as .env.example match by filename
  ending. Exclusions are case-insensitive. With required completeness, a blocking skip raises
  ValueError listing every blocked file, both before and after capture.

Known limitations
-----------------
Completeness covers configured eligible files, not the whole repository. Files are read at
  slightly different moments, so an export is not an atomic snapshot. The folder tree comes
  from a separate walk that applies exclusions only, so it can show files that are absent
  from the index. Capture holds at most two buffers per thread, each up to max_file_bytes + 1.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from export.settings import settings_for_profile
    from export.scan import collect_included_files, build_tree

    root = Path("/path/to/project").resolve()
    settings = settings_for_profile("archive")
    scan = collect_included_files(root, settings)
    print(len(scan.included_records), scan.workers_used)
    print(build_tree(root, settings))
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable
import hashlib
import os
import stat

from app import INTERNAL_NAME_PREFIX
from export.events import Progress, checkpoint
from export.settings import ScanSettings, resolve_workers

SKIP_OUTSIDE_ROOT = "outside_root"
SKIP_EXTENSION_NOT_INCLUDED = "extension_not_included"
SKIP_FILE_TOO_LARGE = "file_too_large"
SKIP_TOTAL_SIZE_LIMIT = "total_size_limit"
SKIP_SIZE_UNAVAILABLE = "size_unavailable"
SKIP_READ_UNAVAILABLE = "read_unavailable"
SKIP_SOURCE_CHANGED = "source_changed"
SKIP_DIRECTORY_UNAVAILABLE = "directory_unavailable"
SKIP_SYMLINK = "symlink_not_followed"
SKIP_SPECIAL_FILE = "not_a_regular_file"
SKIP_EXPORT_OUTPUT = "export_output_directory"
SKIP_INTERNAL = "internal_tool_file"

SOURCE_COMPLETENESS_FAILURE_REASONS = {
    SKIP_FILE_TOO_LARGE, SKIP_TOTAL_SIZE_LIMIT, SKIP_SIZE_UNAVAILABLE, SKIP_READ_UNAVAILABLE,
    SKIP_SOURCE_CHANGED, SKIP_DIRECTORY_UNAVAILABLE,
}


@dataclass(frozen=True, slots=True)
class FileRecord:
    relative_path: str
    size_bytes: int
    extension: str
    sha256: str | None = None
    line_count: int | None = None


@dataclass(frozen=True, slots=True)
class SkipRecord:
    relative_path: str
    reason: str
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ScanResult:
    included_paths: tuple[Path, ...]
    included_records: tuple[FileRecord, ...]
    skipped_records: tuple[SkipRecord, ...]
    total_included_bytes: int
    captured_paths: tuple[Path, ...] = ()
    workers_used: int = 1


@dataclass(frozen=True, slots=True)
class FileMeta:
    path: Path
    relative_path: str
    size_bytes: int | None
    suffix: str
    name_lower: str


def relative_string(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def safe_size(path: Path) -> int | None:
    try:
        return path.lstat().st_size
    except OSError:
        return None


def build_file_meta(path: Path, root: Path) -> FileMeta:
    return FileMeta(
        path=path, relative_path=relative_string(path, root),
        size_bytes=safe_size(path), suffix=path.suffix.lower(), name_lower=path.name.lower(),
    )


def exclusion_reason(path: Path, root: Path, settings: ScanSettings) -> str | None:
    """
    Return why a path is excluded, or None. Directory and file names compare
    case-insensitively, like suffixes, because Windows treats Build and build as
    the same folder. Only directory components are checked against
    exclude_dirs, so a file literally named build is not mistaken for a folder.
    """
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return SKIP_OUTSIDE_ROOT
    directory_parts = relative_parts if path.is_dir() else relative_parts[:-1]
    exclude_dirs_lower = {d.lower() for d in settings.exclude_dirs}
    exclude_files_lower = {f.lower() for f in settings.exclude_files}
    for part in directory_parts:
        if part.lower() in exclude_dirs_lower:
            return f"excluded_directory:{part}"
    if path.name.lower() in exclude_files_lower:
        return f"excluded_file:{path.name}"
    suffix = path.suffix.lower()
    if suffix in settings.exclude_suffixes:
        return f"excluded_suffix:{suffix}"
    return None


def is_configured_source_file(meta: FileMeta, settings: ScanSettings) -> bool:
    if meta.suffix in settings.include_extensions:
        return True
    if meta.name_lower in settings.include_extensions:
        return True
    return any(
        meta.name_lower.endswith(extension)
        for extension in settings.include_extensions
        if extension.count(".") > 1
    )


def skip_record(meta: FileMeta, reason: str) -> SkipRecord:
    return SkipRecord(relative_path=meta.relative_path, reason=reason, size_bytes=meta.size_bytes)


def source_completeness_failures(skipped_records: list[SkipRecord]) -> list[SkipRecord]:
    return [r for r in skipped_records if r.reason in SOURCE_COMPLETENESS_FAILURE_REASONS]


def build_source_failure_message(failures: list[SkipRecord]) -> str:
    lines = [
        "SOURCE COMPLETENESS CHECK FAILED", "",
        "Archive mode requires every eligible source/text file to be captured.",
        "The build was stopped because one or more eligible files were not included.",
        "", "Skipped eligible source files:",
    ]
    for record in failures:
        size_display = "unknown" if record.size_bytes is None else str(record.size_bytes)
        lines.append(f"- {record.relative_path} ({record.reason}, {size_display} bytes)")
    lines.append("")
    lines.append("Increase the archive limits, remove the exclusion, or fix the unreadable file before building a preservation snapshot.")
    return "\n".join(lines)


def discover_candidates(
    root: Path,
    settings: ScanSettings,
    output_dir: Path | None = None,
    cancel: Event | None = None,
) -> tuple[list[FileMeta], list[SkipRecord]]:
    """
    Walk the project depth-first, never entering excluded folders, the export
    output folder, .pch- entries, or symlinks. Each skipped folder yields one
    record instead of one per descendant file.
    """
    output_resolved = output_dir.resolve() if output_dir is not None else None
    candidates: list[FileMeta] = []
    skipped: list[SkipRecord] = []

    def visit(directory: Path) -> None:
        checkpoint(cancel)
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            skipped.append(skip_record(build_file_meta(directory, root), SKIP_DIRECTORY_UNAVAILABLE))
            return
        for path in entries:
            if path.name.startswith(INTERNAL_NAME_PREFIX):
                skipped.append(skip_record(build_file_meta(path, root), SKIP_INTERNAL))
                continue
            try:
                info = path.lstat()
            except OSError:
                skipped.append(skip_record(build_file_meta(path, root), SKIP_SIZE_UNAVAILABLE))
                continue
            meta = build_file_meta(path, root)
            if stat.S_ISLNK(info.st_mode):
                skipped.append(skip_record(meta, SKIP_SYMLINK))
                continue
            if stat.S_ISDIR(info.st_mode):
                if output_resolved is not None and path.resolve() == output_resolved:
                    skipped.append(SkipRecord(relative_path=meta.relative_path, reason=SKIP_EXPORT_OUTPUT))
                    continue
                reason = exclusion_reason(path, root, settings)
                if reason:
                    skipped.append(SkipRecord(relative_path=meta.relative_path, reason=reason))
                    continue
                visit(path)
                continue
            if not stat.S_ISREG(info.st_mode):
                skipped.append(skip_record(meta, SKIP_SPECIAL_FILE))
                continue
            reason = exclusion_reason(path, root, settings)
            if reason:
                skipped.append(skip_record(meta, reason))
            elif not is_configured_source_file(meta, settings):
                skipped.append(skip_record(meta, SKIP_EXTENSION_NOT_INCLUDED))
            elif meta.size_bytes is None:
                skipped.append(skip_record(meta, SKIP_SIZE_UNAVAILABLE))
            elif meta.size_bytes > settings.max_file_bytes:
                skipped.append(skip_record(meta, SKIP_FILE_TOO_LARGE))
            else:
                candidates.append(meta)

    visit(root)
    return candidates, skipped


def capture_file(meta: FileMeta, settings: ScanSettings) -> tuple[FileRecord | None, bytes | None, str | None]:
    """
    Read one file exactly once. Its hash, line count, rendered text, and ZIP
    copy all come from these bytes, so they always describe the same content.
    """
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(meta.path, flags)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None, None, SKIP_SOURCE_CHANGED
            data = handle.read(settings.max_file_bytes + 1)
    except OSError:
        return None, None, SKIP_READ_UNAVAILABLE
    if len(data) != meta.size_bytes:
        return None, None, SKIP_SOURCE_CHANGED
    record = FileRecord(
        relative_path=meta.relative_path, size_bytes=len(data),
        extension=meta.suffix or meta.name_lower,
        sha256=(hashlib.sha256(data).hexdigest() if settings.include_hashes else None),
        line_count=(len(data.decode("utf-8", errors="replace").splitlines()) if settings.include_line_counts else None),
    )
    return record, data, None


def collect_included_files(
    root: Path,
    settings: ScanSettings,
    output_dir: Path | None = None,
    spool_dir: Path | None = None,
    cancel: Event | None = None,
    progress: Callable[[Progress], None] | None = None,
) -> ScanResult:
    emit = progress or (lambda _event: None)
    emit(Progress("discovering", message="Scanning project folders"))
    candidates, skipped_records = discover_candidates(root, settings, output_dir, cancel)

    selected: list[FileMeta] = []
    total_bytes = 0
    for meta in sorted(candidates, key=lambda m: m.path):
        if total_bytes + (meta.size_bytes or 0) > settings.max_total_bytes:
            skipped_records.append(skip_record(meta, SKIP_TOTAL_SIZE_LIMIT))
            continue
        selected.append(meta)
        total_bytes += meta.size_bytes or 0

    failures = source_completeness_failures(skipped_records)
    if settings.require_complete_source and failures:
        raise ValueError(build_source_failure_message(failures))

    included_paths: list[Path] = []
    included_records: list[FileRecord] = []
    captured_paths: list[Path] = []
    workers = resolve_workers(settings.workers)
    batch_size = workers * 2
    done = 0
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pch-capture") as pool:
        for start in range(0, len(selected), batch_size):
            checkpoint(cancel)
            batch = selected[start:start + batch_size]
            for meta, (record, data, reason) in zip(batch, pool.map(lambda m: capture_file(m, settings), batch)):
                done += 1
                if reason is not None:
                    skipped_records.append(skip_record(meta, reason))
                    continue
                included_paths.append(meta.path)
                included_records.append(record)
                if spool_dir is not None:
                    captured = spool_dir / meta.path.relative_to(root)
                    captured.parent.mkdir(parents=True, exist_ok=True)
                    captured.write_bytes(data)
                    captured_paths.append(captured)
            emit(Progress("capturing", done, len(selected)))
    checkpoint(cancel)

    skipped_records.sort(key=lambda r: r.relative_path)
    failures = source_completeness_failures(skipped_records)
    if settings.require_complete_source and failures:
        raise ValueError(build_source_failure_message(failures))

    return ScanResult(
        included_paths=tuple(included_paths), included_records=tuple(included_records),
        skipped_records=tuple(skipped_records),
        total_included_bytes=sum(r.size_bytes for r in included_records),
        captured_paths=tuple(captured_paths),
        workers_used=workers,
    )


def build_tree(root: Path, settings: ScanSettings, output_dir: Path | None = None) -> str:
    """
    Render a directory-first folder tree using exclusion rules only. A symlinked
    directory that loops back to an ancestor is labelled instead of expanded.
    """
    lines: list[str] = [root.name + "/"]
    output_resolved = output_dir.resolve() if output_dir is not None else None

    def keep(entry: Path) -> bool:
        if entry.name.startswith(INTERNAL_NAME_PREFIX) or exclusion_reason(entry, root, settings):
            return False
        try:
            return output_resolved is None or entry.resolve() != output_resolved
        except OSError:
            return True

    def walk(directory: Path, prefix: str = "", visited: frozenset[Path] = frozenset()) -> None:
        try:
            resolved = directory.resolve()
        except OSError:
            resolved = directory
        if resolved in visited:
            return
        visited = visited | {resolved}
        try:
            entries = sorted(
                [e for e in directory.iterdir() if keep(e)],
                key=lambda item: (not item.is_dir(), item.name.lower()),
            )
        except OSError:
            return
        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            is_dir = entry.is_dir()
            try:
                entry_resolved = entry.resolve() if is_dir else None
            except OSError:
                entry_resolved = None
            is_loop = is_dir and entry_resolved is not None and entry_resolved in visited
            suffix = "/ (symlink loop, not expanded)" if is_loop else ("/" if is_dir else "")
            lines.append(prefix + connector + entry.name + suffix)
            if is_dir and not is_loop:
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension, visited)

    walk(root)
    return "\n".join(lines)