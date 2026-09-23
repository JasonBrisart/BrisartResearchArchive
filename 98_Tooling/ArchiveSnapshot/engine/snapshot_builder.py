"""
engine.snapshot_builder
------------------------
Orchestrates one full snapshot creation: scan the source folder, import
any Project Context Helper bundle, write snapshot outputs, build a change
report against the previous snapshot, and update the store index.

This is the single entry point other code (CLI, GUI, daily automation)
should call to create a snapshot.
"""
from __future__ import annotations

import datetime
from dataclasses import asdict
from pathlib import Path

from .app_info import DIFF_FILENAME, STORE_LOG_FILENAME, ZIP_FILENAME
from .change_report import build_diff_markdown, compare_snapshot_dirs
from .snapshot_writer import create_zip_snapshot, write_snapshot_outputs
from .settings import ArchiveSettings, SnapshotResult
from .project_context_import import (
    import_project_context_bundle,
    project_context_snapshot_dir,
)
from .folder_scanner import scan_folder, validate_root
from .snapshot_index import latest_snapshot_before, snapshot_folder_for, write_store_index


def timestamp_now() -> str:
    """
    Human-readable timestamp.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def date_key_now() -> str:
    """
    Local date key.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d")


def time_slug_now() -> str:
    """
    Local time slug.
    """
    return datetime.datetime.now().astimezone().strftime("%H%M%S")


def append_store_log(source_root: Path, text: str) -> None:
    """
    Append to the ArchiveSnapshot store log.
    """
    from .app_info import STORE_DIRNAME

    store_root = source_root / STORE_DIRNAME
    store_root.mkdir(parents=True, exist_ok=True)
    log_path = store_root / STORE_LOG_FILENAME
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def collect_generated_files(outputs: dict[str, Path | None]) -> list[Path]:
    """
    Return existing generated files from an output map.
    """
    files: list[Path] = []
    for path in outputs.values():
        if path is not None and Path(path).exists():
            files.append(Path(path))
    return files


def project_context_generated_files(project_context_path: Path | None) -> list[Path]:
    """
    Return Project Context Helper files copied into the snapshot.
    """
    if project_context_path is None:
        return []
    if not project_context_path.exists() or not project_context_path.is_dir():
        return []
    return [path for path in sorted(project_context_path.iterdir()) if path.is_file()]


def create_snapshot(
    source_root: str | Path,
    settings: ArchiveSettings | None = None,
) -> SnapshotResult:
    """
    Create one archive snapshot.
    """
    root = validate_root(source_root)
    settings = settings or ArchiveSettings()
    created = timestamp_now()
    date_key = date_key_now()
    time_slug = time_slug_now()
    export_dir = snapshot_folder_for(root, date_key, time_slug)
    export_dir.mkdir(parents=True, exist_ok=True)
    project_context_bundle = None
    project_context_path = None
    if settings.include_project_context_bundle:
        project_context_bundle = import_project_context_bundle(
            source_root=root,
            snapshot_dir=export_dir,
        )
        if project_context_bundle is not None:
            project_context_path = project_context_snapshot_dir(export_dir)
    project_context_data = asdict(project_context_bundle) if project_context_bundle else None
    scan = scan_folder(root, settings)
    outputs = write_snapshot_outputs(
        root=root,
        export_dir=export_dir,
        scan=scan,
        settings=settings,
        created=created,
        project_context=project_context_data,
    )
    generated_files = collect_generated_files(outputs)
    generated_files.extend(project_context_generated_files(project_context_path))
    zip_path = None
    if settings.include_zip_snapshot:
        zip_path = export_dir / ZIP_FILENAME
        create_zip_snapshot(
            zip_path=zip_path,
            root=root,
            scan=scan,
            generated_files=generated_files,
        )
    diff_path = None
    previous = latest_snapshot_before(root, export_dir)
    if previous is not None and settings.include_diff_report:
        try:
            diff = compare_snapshot_dirs(previous.snapshot_dir, export_dir)
            diff_path = export_dir / DIFF_FILENAME
            diff_path.write_text(
                build_diff_markdown(diff),
                encoding="utf-8",
            )
        except Exception:
            diff_path = None
    write_store_index(root)
    project_context_log = "none"
    if project_context_bundle is not None:
        project_context_log = f"{project_context_bundle.file_count} files"
    append_store_log(
        root,
        (
            f"\n## Snapshot Created - {created}\n\n"
            f"- Folder: `{root}`\n"
            f"- Snapshot: `{export_dir}`\n"
            f"- Included files: `{len(scan.included_records)}`\n"
            f"- Skipped files: `{len(scan.skipped_records)}`\n"
            f"- Included bytes: `{scan.total_included_bytes}`\n"
            f"- Project Context Helper bundle: `{project_context_log}`\n"
        ),
    )
    return SnapshotResult(
        export_dir=export_dir,
        summary_path=outputs.get("summary"),
        manifest_path=outputs.get("manifest"),
        hashes_path=outputs.get("hashes"),
        tree_path=outputs.get("tree"),
        settings_path=outputs["settings"],
        zip_path=zip_path,
        diff_path=diff_path,
        project_context_path=project_context_path,
        included_count=len(scan.included_records),
        skipped_count=len(scan.skipped_records),
        total_included_bytes=scan.total_included_bytes,
    )
