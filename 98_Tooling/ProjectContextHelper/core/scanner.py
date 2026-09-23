from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from core.models import (
    FileRecord,
    ScanResult,
    ScanSettings,
    SkipRecord,
)
from core.utils import (
    count_lines,
    sha256_file,
)

SKIP_OUTSIDE_ROOT = "outside_root"
SKIP_EXTENSION_NOT_INCLUDED = "extension_not_included"
SKIP_FILE_TOO_LARGE = "file_too_large"
SKIP_TOTAL_SIZE_LIMIT = "total_size_limit"
SKIP_SIZE_UNAVAILABLE = "size_unavailable"
SKIP_READ_UNAVAILABLE = "read_unavailable"

SOURCE_COMPLETENESS_FAILURE_REASONS = {
    SKIP_FILE_TOO_LARGE, SKIP_TOTAL_SIZE_LIMIT, SKIP_SIZE_UNAVAILABLE, SKIP_READ_UNAVAILABLE,
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
        return path.stat().st_size
    except OSError:
        return None


def build_file_meta(path: Path, root: Path) -> FileMeta:
    return FileMeta(
        path=path, relative_path=relative_string(path, root),
        size_bytes=safe_size(path), suffix=path.suffix.lower(), name_lower=path.name.lower(),
    )


def can_read_text_file(path: Path) -> bool:
    try:
        path.read_text(encoding="utf-8", errors="replace")
        return True
    except Exception:
        return False


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


def should_include_file(path: Path, root: Path, settings: ScanSettings) -> tuple[bool, SkipRecord | None, FileMeta]:
    meta = build_file_meta(path, root)
    if not path.is_file():
        return False, None, meta
    reason = exclusion_reason(path, root, settings)
    if reason:
        return False, skip_record(meta, reason), meta
    if not is_configured_source_file(meta, settings):
        return False, skip_record(meta, SKIP_EXTENSION_NOT_INCLUDED), meta
    if meta.size_bytes is None:
        return False, skip_record(meta, SKIP_SIZE_UNAVAILABLE), meta
    if meta.size_bytes > settings.max_file_bytes:
        return False, skip_record(meta, SKIP_FILE_TOO_LARGE), meta
    if settings.include_file_contents and not can_read_text_file(path):
        return False, skip_record(meta, SKIP_READ_UNAVAILABLE), meta
    return True, None, meta


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


def build_file_record(meta: FileMeta, settings: ScanSettings) -> FileRecord:
    return FileRecord(
        relative_path=meta.relative_path, size_bytes=meta.size_bytes or 0,
        extension=meta.suffix or meta.name_lower,
        sha256=(sha256_file(meta.path) if settings.include_hashes else None),
        line_count=(count_lines(meta.path) if settings.include_line_counts else None),
    )


def collect_included_files(root: Path, settings: ScanSettings) -> ScanResult:
    included_paths: list[Path] = []
    included_records: list[FileRecord] = []
    skipped_records: list[SkipRecord] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        include, skip, meta = should_include_file(path, root, settings)
        if skip is not None:
            skipped_records.append(skip)
            continue
        if not include:
            continue
        if meta.size_bytes is None:
            skipped_records.append(skip_record(meta, SKIP_SIZE_UNAVAILABLE))
            continue
        if total_bytes + meta.size_bytes > settings.max_total_bytes:
            skipped_records.append(skip_record(meta, SKIP_TOTAL_SIZE_LIMIT))
            continue
        included_paths.append(path)
        included_records.append(build_file_record(meta, settings))
        total_bytes += meta.size_bytes
    failures = source_completeness_failures(skipped_records)
    if settings.require_complete_source and failures:
        raise ValueError(build_source_failure_message(failures))
    return ScanResult(
        included_paths=tuple(included_paths), included_records=tuple(included_records),
        skipped_records=tuple(skipped_records), total_included_bytes=total_bytes,
    )


def build_tree(root: Path, settings: ScanSettings) -> str:
    """
    Build a readable folder tree for the selected project. Protected
    against symlink loops (a directory that, directly or via a
    longer chain, points back at one of its own ancestors): each
    directory's resolved real path is tracked while walking, and
    revisiting one already on the current path is reported directly
    in the tree as a loop instead of being descended into again.
    """
    lines: list[str] = [root.name + "/"]

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
                [e for e in directory.iterdir() if not exclusion_reason(e, root, settings)],
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
