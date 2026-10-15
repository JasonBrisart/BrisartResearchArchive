"""
File: core/scanner.py

Purpose
-------
Select eligible source/text files with a pruned directory walk, apply byte budgets in a
  deterministic order, capture every included file exactly once with a bounded thread pool,
  enforce configured completeness, and render a folder tree.

Implemented responsibilities:
- relative_string: Return the path relative to root as a string; if it is not lexically
  relative, return the full path string instead.
- safe_size: Read lstat().st_size; return None on OSError so the scanner can record
  size_unavailable.
- build_file_meta: Capture a candidate's path, relative display path, size, lowercased suffix,
  and lowercased filename in FileMeta.
- exclusion_reason: Check lexical root membership, excluded directory components, excluded
  filenames, and excluded suffixes in that order; return the first reason or None.
- is_configured_source_file: Match lowercased suffix or exact filename against
  include_extensions, then test filename endings for configured compound extensions.
- skip_record: Convert FileMeta plus a reason string into an immutable SkipRecord, preserving an
  unavailable size as None.
- source_completeness_failures: Return only skip records whose reason belongs to
  SOURCE_COMPLETENESS_FAILURE_REASONS.
- build_source_failure_message: Format the blocking file list with reason/byte size and
  remediation text for a required-completeness ValueError.
- discover_candidates: Walk the root depth-first without entering excluded directories, the
  export output directory, internal .pch-* entries, or symlinks; classify every visited entry as
  a candidate or a SkipRecord.
- capture_file: Worker-thread function: open one candidate, read at most max_file_bytes + 1
  bytes, reject a size change since discovery, and compute SHA256/line count from those bytes.
- collect_included_files: Discover, apply the total-byte budget in sorted path order, capture in
  parallel batches, optionally spool captured bytes, enforce completeness, and return ScanResult.
- build_tree: Render a directory-first, case-insensitive-name-sorted folder tree using exclusion
  rules, skipping the export output directory and internal entries; mark ancestor symlink loops.
- walk: Nested tree-rendering callback: track resolved ancestor directories, filter entries,
  append connectors/loop labels, and recursively expand nonloop directories.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: INTERNAL_NAME_PREFIX.
- core.events: Progress, checkpoint.
- core.models: FileRecord, ScanResult, ScanSettings, SkipRecord.

Consumers in the supplied source:
- core/builder.py imports collect_included_files.
- core/exporters.py imports SOURCE_COMPLETENESS_FAILURE_REASONS, build_tree.

Settings / parameters
---------------------
Uses ScanSettings extension/name matching, exclusions, byte limits, hash/line toggles,
  require_complete_source, and workers (thread count, 1-32). Six reasons count toward
  completeness: file_too_large, total_size_limit, size_unavailable, read_unavailable,
  source_changed, directory_unavailable.

Captured bytes are written to spool_dir/<relative path> when spool_dir is supplied; otherwise
  hashes and line counts are still computed from one read, but the bytes are discarded and
  captured_paths is empty.

Function signatures (nested callbacks are scoped to their enclosing function):
- relative_string(path: Path, root: Path) -> str
- safe_size(path: Path) -> int | None
- build_file_meta(path: Path, root: Path) -> FileMeta
- exclusion_reason(path: Path, root: Path, settings: ScanSettings) -> str | None
- is_configured_source_file(meta: FileMeta, settings: ScanSettings) -> bool
- skip_record(meta: FileMeta, reason: str) -> SkipRecord
- source_completeness_failures(skipped_records: list[SkipRecord]) -> list[SkipRecord]
- build_source_failure_message(failures: list[SkipRecord]) -> str
- discover_candidates(root: Path, settings: ScanSettings, output_dir: Path | None=None,
  cancel: Event | None=None) -> tuple[list[FileMeta], list[SkipRecord]]
- capture_file(meta: FileMeta, settings: ScanSettings) -> tuple[FileRecord | None, bytes |
  None, str | None]
- collect_included_files(root: Path, settings: ScanSettings, output_dir: Path | None=None,
  spool_dir: Path | None=None, cancel: Event | None=None, progress:
  Callable[[Progress], None] | None=None) -> ScanResult
- build_tree(root: Path, settings: ScanSettings, output_dir: Path | None=None) -> str
- walk(directory: Path, prefix: str='', visited: frozenset[Path]=frozenset()) -> None

Module constants and expressions:
- SKIP_OUTSIDE_ROOT = 'outside_root'
- SKIP_EXTENSION_NOT_INCLUDED = 'extension_not_included'
- SKIP_FILE_TOO_LARGE = 'file_too_large'
- SKIP_TOTAL_SIZE_LIMIT = 'total_size_limit'
- SKIP_SIZE_UNAVAILABLE = 'size_unavailable'
- SKIP_READ_UNAVAILABLE = 'read_unavailable'
- SKIP_SOURCE_CHANGED = 'source_changed'
- SKIP_DIRECTORY_UNAVAILABLE = 'directory_unavailable'
- SKIP_SYMLINK = 'symlink_not_followed'
- SKIP_SPECIAL_FILE = 'not_a_regular_file'
- SKIP_EXPORT_OUTPUT = 'export_output_directory'
- SKIP_INTERNAL = 'internal_tool_file'
- SOURCE_COMPLETENESS_FAILURE_REASONS = {SKIP_FILE_TOO_LARGE, SKIP_TOTAL_SIZE_LIMIT,
  SKIP_SIZE_UNAVAILABLE, SKIP_READ_UNAVAILABLE, SKIP_SOURCE_CHANGED, SKIP_DIRECTORY_UNAVAILABLE}

FileMeta record fields:
- path: Path (required constructor field)
- relative_path: str (required constructor field)
- size_bytes: int | None (required constructor field)
- suffix: str (required constructor field)
- name_lower: str (required constructor field)

Edge cases
----------
Directory and filename exclusions are case-insensitive. Compound extensions match filename
  endings. An excluded directory produces one excluded_directory skip record for the directory
  itself; its contents are not walked or listed. Exactly-at-limit files fit because size checks
  use >. A total-budget skip does not stop selection; later smaller files can still fit.

Candidates are budgeted and captured in sorted Path order, matching v3.1.4's sorted rglob order,
  so worker count never changes which files are included. A file whose size changed between
  discovery and capture is skipped as source_changed. Symlinked files and directories are skipped
  as symlink_not_followed (an intentional exclusion, not a completeness failure).

Known limitations
-----------------
Completeness is scoped to configured eligible files, not the entire repository. Intentional
  exclusions, unsupported extensions, and symlinks do not fail it. Each file is read once, but
  files are captured at slightly different moments; this is not an atomic project-wide
  snapshot. The tree is rendered from a separate walk using exclusions only, so it can show
  files absent from the index.

Without spool_dir, captured bytes are not retained, so later rendering must reread originals.
  Capture holds at most 2 x workers file buffers in memory at once; each buffer is bounded by
  max_file_bytes + 1.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from core.constants import settings_for_profile
    from core.scanner import collect_included_files, build_tree

    root = Path("/path/to/project").resolve()
    settings = settings_for_profile("archive")
    scan = collect_included_files(root, settings)
    print(len(scan.included_records), scan.total_included_bytes)
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

from core.constants import INTERNAL_NAME_PREFIX
from core.events import Progress, checkpoint
from core.models import (
    FileRecord,
    ScanResult,
    ScanSettings,
    SkipRecord,
)

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
    Bugfix (v3.1.2): directory-name and file-name exclusion matching
    were case-sensitive (`part in settings.exclude_dirs`, `path.name
    in settings.exclude_files`), while suffix exclusion two lines
    below (`suffix = path.suffix.lower()`) was already
    case-insensitive, and include_extensions matching in
    is_configured_source_file() below is also already
    case-insensitive by construction (both sides are pre-lowercased).
    This was an inconsistency within this same function: on a
    case-preserving-but-case-insensitive filesystem (the default on
    Windows, and optionally on macOS), a folder actually named
    "Build" or "Node_Modules" or "Venv" would silently NOT be excluded
    by the default "build" / "node_modules" / "venv" entries in
    DEFAULT_EXCLUDE_DIRS, even though Windows itself treats those
    names as the same folder. Directory-name and file-name exclusion
    now compare case-insensitively too, matching how suffix and
    extension matching already behave.

    v4.0.0: unchanged. The pruned walk in discover_candidates() calls
    this once per directory instead of once per descendant file.
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
    v4.0.0: replaces v3.1.4's root.rglob("*") traversal. Excluded
    directories (and the export output directory, wherever it is
    configured) are pruned at entry instead of having every descendant
    visited and individually rejected. This also stops custom output
    folder names from being swept into later exports, which v3.1.4 did
    not prevent.
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
    Read one file exactly once. Hash and line count come from these same
    bytes, and the caller spools the same bytes for Markdown and ZIP
    rendering, so all three always describe identical content
    (v3.1.4 read each file up to four separate times).
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
    workers = max(1, settings.workers)
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
    )


def build_tree(root: Path, settings: ScanSettings, output_dir: Path | None = None) -> str:
    """
    Build a readable folder tree for the selected project. Protected
    against symlink loops: each directory's resolved real path is tracked
    while walking, and revisiting one already on the current path is
    reported directly in the tree as a loop instead of being descended
    into again. v4.0.0: the configured export output directory and this
    tool's internal .pch-* entries are left out, whatever they are named.
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
