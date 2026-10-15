"""
File: core/builder.py

Purpose
-------
Orchestrate root and settings validation, optional Git inspection, scanning with single-read
  parallel capture, output rendering into a hidden staging folder, publication of the finished
  export, and best-effort export history recording.

Implemented responsibilities:
- validate_settings: Deep-copy settings and reject unsupported profiles, nonpositive size
  limits, worker counts outside 1-MAX_WORKERS, and empty output folder names; the caller's
  object is never mutated.
- resolve_output_dir: Reject absolute, drive-qualified, or parent-traversing output folder
  names and any name that resolves outside the project root or to the root itself.
- reserve_export_dir: Choose project_context_<timestamp>, adding _2, _3, ... when that name is
  already taken, so two builds in the same second never share a folder.
- publish: Move a finished staging folder into place: rename it to the reserved timestamped
  folder, or (flat output) replace the generated files in the output folder one by one.
- create_context: Validate; inspect Git when requested; create a .pch-build-* staging folder
  inside the output folder; scan and capture into it; write context, manifest, summary, and
  settings; optionally ZIP the captured sources; publish; append best-effort history; return
  BuildResult. Any failure or cancellation before publication deletes the staging folder.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: CONTEXT_FILENAME, DEFAULT_PROFILE, INTERNAL_NAME_PREFIX, MANIFEST_FILENAME,
  MAX_WORKERS, SETTINGS_FILENAME, SNAPSHOT_FILENAME, SUMMARY_FILENAME, VALID_PROFILES,
  settings_for_profile.
- core.events: Progress, checkpoint.
- core.exporters: build_manifest, build_context_markdown, build_summary_text,
  create_snapshot_zip.
- core.git_state: build_git_state.
- services.storage: HistoryEntry, append_history_entry.
- core.models: BuildResult, ScanSettings.
- core.scanner: collect_included_files.
- core.utils: timestamp_now, timestamp_slug, validate_root.

Consumers in the supplied source:
- cli/cli.py imports create_context.
- gui/builders.py imports create_context.

Settings / parameters
---------------------
Accepts a root Path, optional ScanSettings, an optional threading.Event for cancellation, and an
  optional progress callback receiving core.events.Progress. Omitting settings now uses the
  archive preset (v3.1.4 used raw ScanSettings() with empty extension sets).

Function signatures (nested callbacks are scoped to their enclosing function):
- validate_settings(settings: ScanSettings) -> ScanSettings
- resolve_output_dir(root: Path, name: str) -> Path
- reserve_export_dir(base_export_dir: Path) -> Path
- publish(stage: Path, base_export_dir: Path, timestamped: bool) -> Path
- create_context(root: Path, settings: ScanSettings | None=None, cancel: Event | None=None,
  progress: Callable[[Progress], None] | None=None) -> BuildResult

Edge cases
----------
Invalid settings and unsafe output paths raise ValueError before anything is written. A
  completeness failure, cancellation, or rendering error removes the staging folder; the output
  folder itself may remain (empty, or with earlier exports). History-write failures are
  suppressed after publication. Cancellation is not checked once publication starts.

Flat output (timestamped_export_folder=False) overwrites the generated files in the output folder
  as v3.1.4 did; with ZIP disabled, an older PROJECT_SNAPSHOT.zip there is left untouched. Git
  inspection excludes the output folder's name from its working-tree walk.

Known limitations
-----------------
Publication is a directory rename (timestamped) or per-file replace (flat), not a durable
  transaction: a hard kill or power loss can leave a .pch-build-* folder behind, which the
  scanner skips and which can be deleted manually. Two separate processes reserving the same
  folder name at the same instant are not fully excluded. Files are captured one at a time, not
  as an atomic snapshot of the whole project.

History is stored beside the application, not in the selected project root.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from core.builder import create_context
    from core.constants import settings_for_profile

    settings = settings_for_profile("archive")
    settings.include_snapshot_zip = False
    settings.workers = 8
    result = create_context(Path("/path/to/project"), settings)
    print(result.context_path, result.included_count)
"""

from copy import deepcopy
from pathlib import Path, PureWindowsPath
from threading import Event
from typing import Callable
import json
import os
import shutil
import tempfile

from core.constants import (
    CONTEXT_FILENAME,
    DEFAULT_PROFILE,
    INTERNAL_NAME_PREFIX,
    MANIFEST_FILENAME,
    MAX_WORKERS,
    SETTINGS_FILENAME,
    SNAPSHOT_FILENAME,
    SUMMARY_FILENAME,
    VALID_PROFILES,
    settings_for_profile,
)
from core.events import Progress, checkpoint
from core.exporters import (
    build_manifest,
    build_context_markdown,
    build_summary_text,
    create_snapshot_zip,
)
from core.git_state import build_git_state
from services.storage import (
    HistoryEntry,
    append_history_entry,
)
from core.models import (
    BuildResult,
    ScanSettings,
)
from core.scanner import collect_included_files
from core.utils import (
    timestamp_now,
    timestamp_slug,
    validate_root,
)

GENERATED_FILENAMES = (CONTEXT_FILENAME, MANIFEST_FILENAME, SUMMARY_FILENAME, SETTINGS_FILENAME, SNAPSHOT_FILENAME)
STAGING_PREFIX = f"{INTERNAL_NAME_PREFIX}build-"


def validate_settings(settings: ScanSettings) -> ScanSettings:
    settings = deepcopy(settings)
    if settings.profile not in VALID_PROFILES:
        raise ValueError(f"Unsupported profile: {settings.profile!r}.")
    for name in ("max_file_bytes", "max_total_bytes"):
        value = getattr(settings, name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer (got {value!r}).")
    if type(settings.workers) is not int or not 1 <= settings.workers <= MAX_WORKERS:
        raise ValueError(f"workers must be a whole number from 1 to {MAX_WORKERS} (got {settings.workers!r}).")
    if not isinstance(settings.output_dir_name, str) or not settings.output_dir_name.strip():
        raise ValueError("Output folder name cannot be empty.")
    settings.output_dir_name = settings.output_dir_name.strip()
    return settings


def resolve_output_dir(root: Path, name: str) -> Path:
    """
    v4.0.0: v3.1.4 joined output_dir_name onto the root without checks,
    so an absolute path or "..\\elsewhere" wrote exports outside the
    project. The name must now be a relative path that stays inside the
    project root.
    """
    windows = PureWindowsPath(name)
    relative = Path(name)
    if relative.is_absolute() or windows.drive or windows.root or ".." in relative.parts or ".." in windows.parts:
        raise ValueError(f"Output folder must be a relative path inside the project (got {name!r}).")
    output = (root / relative).resolve()
    if output == root or not output.is_relative_to(root):
        raise ValueError(f"Output folder must resolve to a subfolder of the project (got {name!r}).")
    return output


def reserve_export_dir(base_export_dir: Path) -> Path:
    stem = f"project_context_{timestamp_slug()}"
    candidate = base_export_dir / stem
    counter = 2
    while candidate.exists():
        candidate = base_export_dir / f"{stem}_{counter}"
        counter += 1
    return candidate


def publish(stage: Path, base_export_dir: Path, timestamped: bool) -> Path:
    if timestamped:
        while True:
            final_dir = reserve_export_dir(base_export_dir)
            try:
                stage.rename(final_dir)
                return final_dir
            except FileExistsError:
                continue
    for name in GENERATED_FILENAMES:
        produced = stage / name
        if produced.exists():
            os.replace(produced, base_export_dir / name)
    stage.rmdir()
    return base_export_dir


def create_context(
    root: Path,
    settings: ScanSettings | None = None,
    cancel: Event | None = None,
    progress: Callable[[Progress], None] | None = None,
) -> BuildResult:
    emit = progress or (lambda _event: None)
    root = validate_root(root)
    settings = validate_settings(settings if settings is not None else settings_for_profile(DEFAULT_PROFILE))
    base_export_dir = resolve_output_dir(root, settings.output_dir_name)
    checkpoint(cancel)
    created = timestamp_now()

    git_state = None
    if settings.include_git_state:
        git_state = build_git_state(
            root, exclude_dirs=settings.exclude_dirs | {base_export_dir.name},
            exclude_files=settings.exclude_files, commit_limit=settings.git_state_commit_limit,
        )

    base_export_dir.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=base_export_dir))
    published = False
    try:
        spool = stage / "captured"
        scan = collect_included_files(
            root, settings, output_dir=base_export_dir, spool_dir=spool, cancel=cancel, progress=emit,
        )

        emit(Progress("rendering", message="Writing context, manifest, summary, and settings"))
        context_text = build_context_markdown(
            root=root, scan=scan, settings=settings, created=created, git_state=git_state, output_dir=base_export_dir,
        )
        (stage / CONTEXT_FILENAME).write_text(context_text, encoding="utf-8")
        manifest = build_manifest(root=root, scan=scan, settings=settings, created=created, git_state=git_state)
        (stage / MANIFEST_FILENAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        summary_text = build_summary_text(root=root, scan=scan, settings=settings, created=created, git_state=git_state)
        (stage / SUMMARY_FILENAME).write_text(summary_text, encoding="utf-8")
        (stage / SETTINGS_FILENAME).write_text(json.dumps(settings.to_jsonable(), indent=2), encoding="utf-8")
        checkpoint(cancel)

        if settings.include_snapshot_zip:
            emit(Progress("zipping", message="Writing PROJECT_SNAPSHOT.zip"))
            create_snapshot_zip(
                zip_path=stage / SNAPSHOT_FILENAME, context_path=stage / CONTEXT_FILENAME,
                manifest_path=stage / MANIFEST_FILENAME, summary_path=stage / SUMMARY_FILENAME,
                settings_path=stage / SETTINGS_FILENAME, scan=scan, root=root,
            )
        checkpoint(cancel)
        shutil.rmtree(spool, ignore_errors=True)

        emit(Progress("publishing", message="Publishing completed export"))
        export_dir = publish(stage, base_export_dir, settings.timestamped_export_folder)
        published = True
    finally:
        if not published:
            shutil.rmtree(stage, ignore_errors=True)

    snapshot_path = export_dir / SNAPSHOT_FILENAME if settings.include_snapshot_zip else None
    result = BuildResult(
        export_dir=export_dir, context_path=export_dir / CONTEXT_FILENAME,
        manifest_path=export_dir / MANIFEST_FILENAME, summary_path=export_dir / SUMMARY_FILENAME,
        settings_path=export_dir / SETTINGS_FILENAME, snapshot_path=snapshot_path,
        included_count=len(scan.included_records), skipped_count=len(scan.skipped_records),
        total_included_bytes=scan.total_included_bytes,
        git_branch=(git_state.branch if git_state else None),
        git_commit_short=(git_state.head_commit_short if git_state else None),
        git_is_dirty=(git_state.is_dirty if git_state else None),
    )
    try:
        append_history_entry(HistoryEntry(
            created=created, root=str(root), profile=settings.profile, export_dir=str(export_dir),
            included_count=result.included_count, skipped_count=result.skipped_count,
            total_included_bytes=result.total_included_bytes,
            git_branch=result.git_branch or "", git_commit_short=result.git_commit_short or "",
        ))
    except Exception:
        pass
    return result
