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
Imports application/identity.py (INTERNAL_NAME_PREFIX), export/events.py (Progress, checkpoint), and
  export/settings.py (ScanSettings, resolve_workers). Imported by export/pipeline.py
  (collect_included_files, ScanResult), export/render.py (records, build_tree,
  SOURCE_COMPLETENESS_FAILURE_REASONS), and export/snapshot.py (ScanResult).

Settings / parameters
---------------------
Reads the extension and exclusion sets, both byte limits, the hash and line-count toggles,
  require_complete_source, and workers from ScanSettings. The thread count is
  resolve_workers(settings.workers) and is returned as ScanResult.workers_used. Files are
  captured in batches of four times that count. With a spool_dir, each capture thread
  writes its bytes to spool_dir/<relative path> itself (so disk writes run in parallel)
  and they are listed in captured_paths; without one, they are discarded.
  Discovery and the folder tree use os.scandir with the exclusion sets lowercased once per
  scan (Exclusions); line counts use count_lines, which skips decoding unless the bytes
  contain a line break other than \n.

Six skip reasons fail completeness: file_too_large, total_size_limit, size_unavailable,
  read_unavailable, source_changed, directory_unavailable. Intentional skips do not:
  excluded_directory/file/suffix, extension_not_included, symlink_not_followed,
  not_a_regular_file, export_output_directory, internal_tool_file.

Edge cases
----------
Budgets apply in sorted path order, so the worker count never changes which files are
  included. A file exactly at the limit fits. After the total budget is hit, smaller files
  later in order can still fit. A file whose size changed between discovery and capture is
  skipped as source_changed. A file that cannot be copied into the staging folder (for
  example a path too long for Windows once the staging prefix is added) is skipped as
  read_unavailable, so archive mode names it instead of aborting with a bare OS error. Each
  staged copy gets the original file's modification time, which the ZIP then records.
  Compound include-extensions such as .env.example and compound exclude-suffixes such as
  .min.js match by filename ending, because a file's last suffix (.js) can never equal them.
  Extension, suffix, folder, and file exclusions all compare case-insensitively. With
  required completeness, a blocking skip raises ValueError listing every blocked file, both
  before and after capture.

Known limitations
-----------------
Completeness covers configured eligible files, not the whole repository. Files are read at
  slightly different moments, so an export is not an atomic snapshot. The folder tree comes
  from a separate walk that applies exclusions only, so it can show files that are absent
  from the index. Capture holds at most four buffers per thread, each up to max_file_bytes + 1.
  The export output folder is recognised by comparing normalised real paths, which assumes
  the walk never passes through a symlink (it never follows one).

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

from application.identity import INTERNAL_NAME_PREFIX
from export.events import Progress, checkpoint
from export.settings import ScanSettings, resolve_workers

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


def name_suffix(name: str) -> str:
    """Lowercased final suffix with pathlib's rule: '.gitignore' and 'foo.' have none."""
    index = name.rfind(".")
    return name[index:].lower() if 0 < index < len(name) - 1 else ""


class Exclusions:
    """
    The exclusion sets lowercased once per scan. Names compare case-insensitively,
    like suffixes, because Windows treats Build and build as the same folder. Callers
    walk top-down and never enter an excluded folder, so only an entry's own name is
    checked; a file literally named build is never mistaken for a folder.
    """

    __slots__ = ("dirs", "files", "suffixes", "compound_suffixes", "extensions", "compound_extensions")

    def __init__(self, settings: ScanSettings) -> None:
        self.dirs = frozenset(d.lower() for d in settings.exclude_dirs)
        self.files = frozenset(f.lower() for f in settings.exclude_files)
        self.suffixes = frozenset(s.lower() for s in settings.exclude_suffixes)
        self.compound_suffixes = tuple(sorted(s for s in self.suffixes if s.count(".") > 1))
        self.extensions = frozenset(e.lower() for e in settings.include_extensions)
        self.compound_extensions = tuple(sorted(e for e in self.extensions if e.count(".") > 1))

    def reason(self, name: str, is_dir: bool) -> str | None:
        lowered = name.lower()
        if is_dir and lowered in self.dirs:
            return f"excluded_directory:{name}"
        if lowered in self.files:
            return f"excluded_file:{name}"
        suffix = name_suffix(name)
        if suffix in self.suffixes:
            return f"excluded_suffix:{suffix}"
        # A compound suffix such as .min.js can never equal a file's last suffix (.js), so it
        # matches by filename ending, the same rule compound include-extensions use.
        for compound in self.compound_suffixes:
            if lowered.endswith(compound):
                return f"excluded_suffix:{compound}"
        return None

    def is_source(self, suffix: str, name_lower: str) -> bool:
        # Compound extensions such as .env.example match by filename ending.
        return (
            suffix in self.extensions or name_lower in self.extensions
            or any(name_lower.endswith(extension) for extension in self.compound_extensions)
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
    Walk the project depth-first with os.scandir, never entering excluded folders, the
    export output folder, .pch- entries, or symlinks. Each skipped folder yields one
    record instead of one per descendant file. One lstat per entry (free on Windows,
    where scandir returns it with the listing); paths are built only for candidates.
    """
    exclusions = Exclusions(settings)
    output_key = os.path.normcase(str(output_dir.resolve())) if output_dir is not None else None
    candidates: list[FileMeta] = []
    skipped: list[SkipRecord] = []

    def visit(directory: str, relative_dir: str, directory_size: int | None) -> None:
        checkpoint(cancel)
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError:
            skipped.append(SkipRecord(relative_dir or ".", SKIP_DIRECTORY_UNAVAILABLE, directory_size))
            return
        for entry in entries:
            name = entry.name
            relative = f"{relative_dir}{os.sep}{name}" if relative_dir else name
            if name.startswith(INTERNAL_NAME_PREFIX):
                skipped.append(SkipRecord(relative, SKIP_INTERNAL, _size_or_none(entry)))
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                skipped.append(SkipRecord(relative, SKIP_SIZE_UNAVAILABLE))
                continue
            mode = info.st_mode
            if stat.S_ISLNK(mode):
                skipped.append(SkipRecord(relative, SKIP_SYMLINK, info.st_size))
                continue
            if stat.S_ISDIR(mode):
                if output_key is not None and os.path.normcase(entry.path) == output_key:
                    skipped.append(SkipRecord(relative, SKIP_EXPORT_OUTPUT))
                    continue
                reason = exclusions.reason(name, is_dir=True)
                if reason:
                    skipped.append(SkipRecord(relative, reason))
                    continue
                visit(entry.path, relative, info.st_size)
                continue
            if not stat.S_ISREG(mode):
                skipped.append(SkipRecord(relative, SKIP_SPECIAL_FILE, info.st_size))
                continue
            size = info.st_size
            name_lower = name.lower()
            suffix = name_suffix(name)
            reason = exclusions.reason(name, is_dir=False)
            if reason:
                skipped.append(SkipRecord(relative, reason, size))
            elif not exclusions.is_source(suffix, name_lower):
                skipped.append(SkipRecord(relative, SKIP_EXTENSION_NOT_INCLUDED, size))
            elif size > settings.max_file_bytes:
                skipped.append(SkipRecord(relative, SKIP_FILE_TOO_LARGE, size))
            else:
                candidates.append(FileMeta(Path(entry.path), relative, size, suffix, name_lower))

    try:
        root_size = root.lstat().st_size
    except OSError:
        root_size = None
    visit(str(root), "", root_size)
    return candidates, skipped


def _size_or_none(entry: os.DirEntry) -> int | None:
    try:
        return entry.stat(follow_symlinks=False).st_size
    except OSError:
        return None


# Byte sequences that str.splitlines() treats as line breaks besides \n, as they appear
# in UTF-8. Each `in` test is a C memchr/memmem scan, far faster than one regex here.
_EXTRA_LINE_BREAKS = (b"\r", b"\x0b", b"\x0c", b"\x1c", b"\x1d", b"\x1e", b"\xc2\x85", b"\xe2\x80\xa8", b"\xe2\x80\xa9")


def count_lines(data: bytes) -> int:
    """
    Exactly len(data.decode("utf-8", "replace").splitlines()), without decoding when
    the bytes contain no line break other than \n (nearly every source file).
    """
    if any(sequence in data for sequence in _EXTRA_LINE_BREAKS):
        return len(data.decode("utf-8", errors="replace").splitlines())
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def capture_file(
    meta: FileMeta, settings: ScanSettings, spool_path: Path | None = None,
) -> tuple[FileRecord | None, str | None]:
    """
    Read one file exactly once. Its hash, line count, rendered text, and ZIP copy all
    come from these bytes, so they always describe the same content. Runs on a capture
    thread, including the spool write, so disk writes are parallel too.
    """
    try:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(meta.path, flags)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                return None, SKIP_SOURCE_CHANGED
            data = handle.read(settings.max_file_bytes + 1)
    except OSError:
        return None, SKIP_READ_UNAVAILABLE
    if len(data) != meta.size_bytes:
        return None, SKIP_SOURCE_CHANGED
    if spool_path is not None:
        try:
            spool_path.parent.mkdir(parents=True, exist_ok=True)
            spool_path.write_bytes(data)
        except OSError:
            # Typically a path too long for the staging folder. Report this one file (a
            # completeness failure) instead of aborting the whole export with a bare OS error.
            return None, SKIP_READ_UNAVAILABLE
        try:
            # The ZIP is built from this copy, so it must carry the original modification time.
            os.utime(spool_path, ns=(info.st_atime_ns, info.st_mtime_ns))
        except OSError:
            pass
    record = FileRecord(
        relative_path=meta.relative_path, size_bytes=len(data),
        extension=meta.suffix or meta.name_lower,
        sha256=(hashlib.sha256(data).hexdigest() if settings.include_hashes else None),
        line_count=(count_lines(data) if settings.include_line_counts else None),
    )
    return record, None


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
    batch_size = workers * 4
    done = 0

    def capture(meta: FileMeta) -> tuple[FileRecord | None, str | None, Path | None]:
        spool_path = spool_dir / meta.path.relative_to(root) if spool_dir is not None else None
        record, reason = capture_file(meta, settings, spool_path)
        return record, reason, spool_path

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pch-capture") as pool:
        for start in range(0, len(selected), batch_size):
            checkpoint(cancel)
            batch = selected[start:start + batch_size]
            for meta, (record, reason, spool_path) in zip(batch, pool.map(capture, batch)):
                done += 1
                if reason is not None:
                    skipped_records.append(skip_record(meta, reason))
                    continue
                included_paths.append(meta.path)
                included_records.append(record)
                if spool_path is not None:
                    captured_paths.append(spool_path)
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
    Render a directory-first folder tree using exclusion rules only. Symlinked folders
    are shown and expanded, but one that loops back to an ancestor is labelled instead.
    Real paths are tracked incrementally, so only symlinks cost a realpath() call.
    """
    exclusions = Exclusions(settings)
    lines: list[str] = [root.name + "/"]
    output_key = os.path.normcase(str(output_dir.resolve())) if output_dir is not None else None

    def walk(directory: str, real_directory: str, prefix: str, visited: frozenset[str]) -> None:
        try:
            with os.scandir(directory) as iterator:
                listed = list(iterator)
        except OSError:
            return
        entries = []
        for entry in listed:
            try:
                is_dir = entry.is_dir()
                is_link = entry.is_symlink()
            except OSError:
                is_dir = is_link = False
            if entry.name.startswith(INTERNAL_NAME_PREFIX) or exclusions.reason(entry.name, is_dir):
                continue
            real = os.path.realpath(entry.path) if is_link else os.path.join(real_directory, entry.name)
            if output_key is not None and os.path.normcase(real) == output_key:
                continue
            entries.append((not is_dir, entry.name.lower(), entry, is_dir, real))
        entries.sort(key=lambda item: (item[0], item[1]))
        for index, (_, _, entry, is_dir, real) in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
            key = os.path.normcase(real)
            is_loop = is_dir and key in visited
            suffix = "/ (symlink loop, not expanded)" if is_loop else ("/" if is_dir else "")
            lines.append(prefix + connector + entry.name + suffix)
            if is_dir and not is_loop:
                extension = "    " if is_last else "\u2502   "
                walk(entry.path, real, prefix + extension, visited | {key})

    real_root = str(root.resolve())
    walk(str(root), real_root, "", frozenset({os.path.normcase(real_root)}))
    return "\n".join(lines)
