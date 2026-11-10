"""
File: export/pipeline.py

Purpose
-------
Run one export from start to finish: validate the project folder, settings, and output
  folder; optionally read Git state; scan and capture into a hidden staging folder; write the
  context, manifest, summary, settings, and optional ZIP there; then publish the finished
  folder in one step and return a BuildResult. This is the single entry point both interfaces
  call, and it has no knowledge of app state, the GUI, or the network.

Communication / relationships
-----------------------------
Imports app (output names, staging prefix), export/events.py, export/git_state.py,
  export/render.py, export/scan.py, and export/settings.py. Imported by cli.py and
  gui/build_tab.py (create_context, BuildResult), and gui/widgets.py (BuildResult); storage.py
  names BuildResult in type annotations only. Export history is recorded by the callers through
  storage.record_export, not here.

Settings / parameters
---------------------
create_context(root, settings=None, cancel=None, progress=None). Omitted settings mean the
  archive preset. cancel is a threading.Event checked between folders, capture batches, and
  phases; progress receives export.events.Progress. Exports go to
  <root>/<output_dir_name>/project_context_<YYYYMMDD_HHMMSS>, with _2, _3, ... added when
  that name is taken, or straight into the output folder when timestamped_export_folder is
  off (flat output). BuildResult.capture_workers is the thread count actually used.

Edge cases
----------
Invalid settings, a missing root, or an unsafe output folder raise before anything is
  written. A completeness stop, cancellation, or any error before publication deletes the
  staging folder (the output folder itself may remain, empty). Flat output overwrites the
  generated files; with the ZIP off, an older ZIP there is left alone. The caller's settings
  object is never modified.

Known limitations
-----------------
Publication is a directory rename (or per-file replace for flat output), not a durable
  transaction: a hard kill or power loss can leave a .pch-build-* folder, which later scans
  skip and which can be deleted. Two separate processes reserving the same folder name in the
  same instant are not fully excluded.

Examples
--------
Usage from the directory containing run.py:

    from pathlib import Path
    from export.pipeline import create_context
    from export.settings import settings_for_profile

    settings = settings_for_profile("archive")
    settings.include_snapshot_zip = False
    settings.workers = 8          # or "auto" (the default): every detected CPU core
    result = create_context(Path("/path/to/project"), settings)
    print(result.context_path, result.included_count, result.capture_workers)
"""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from threading import Event
from typing import Callable
import datetime
import json
import os
import shutil
import tempfile

from app import (
    CONTEXT_FILENAME,
    INTERNAL_NAME_PREFIX,
    MANIFEST_FILENAME,
    OUTPUT_FILENAMES,
    SETTINGS_FILENAME,
    SNAPSHOT_FILENAME,
    SUMMARY_FILENAME,
)
from export.events import Progress, checkpoint
from export.git_state import build_git_state
from export.render import build_context_markdown, build_manifest, build_summary_text, create_snapshot_zip
from export.scan import collect_included_files
from export.settings import DEFAULT_PROFILE, ScanSettings, settings_for_profile, validate_settings

STAGING_PREFIX = f"{INTERNAL_NAME_PREFIX}build-"


@dataclass(frozen=True, slots=True)
class BuildResult:
    created: str
    root: Path
    export_dir: Path
    context_path: Path
    manifest_path: Path
    summary_path: Path
    settings_path: Path
    snapshot_path: Path | None
    included_count: int
    skipped_count: int
    total_included_bytes: int
    capture_workers: int
    git_branch: str | None = None
    git_commit_short: str | None = None
    git_is_dirty: bool | None = None


def timestamp_now() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def timestamp_slug() -> str:
    return datetime.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def validate_root(root: Path) -> Path:
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Project folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Selected path is not a folder: {root}")
    return root


def resolve_output_dir(root: Path, name: str) -> Path:
    """
    Return the output folder inside root. Absolute, drive-qualified, and '..'
    names are rejected, as is anything that resolves outside the project or to
    the project itself.
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
    for name in OUTPUT_FILENAMES:
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
            emit(Progress("zipping", message=f"Writing {SNAPSHOT_FILENAME}"))
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
    return BuildResult(
        created=created, root=root, export_dir=export_dir, context_path=export_dir / CONTEXT_FILENAME,
        manifest_path=export_dir / MANIFEST_FILENAME, summary_path=export_dir / SUMMARY_FILENAME,
        settings_path=export_dir / SETTINGS_FILENAME, snapshot_path=snapshot_path,
        included_count=len(scan.included_records), skipped_count=len(scan.skipped_records),
        total_included_bytes=scan.total_included_bytes, capture_workers=scan.workers_used,
        git_branch=(git_state.branch if git_state else None),
        git_commit_short=(git_state.head_commit_short if git_state else None),
        git_is_dirty=(git_state.is_dirty if git_state else None),
    )
