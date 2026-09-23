"""
engine.snapshot_index
----------------------
Discovers snapshots on disk (by reading their manifests), groups them by
date, and maintains the ArchiveSnapshot store index file.

The on-disk store folder and its index/log are named after the program
(ARCHIVE_SNAPSHOT / ARCHIVE_SNAPSHOT_INDEX.json / ARCHIVE_SNAPSHOT_LOG.md).
"""
from __future__ import annotations

import json
from pathlib import Path

from .app_info import (
    MANIFEST_FILENAME,
    PROJECT_CONTEXT_DEST_DIRNAME,
    PROJECT_CONTEXT_INDEX_FILENAME,
    STORE_DIRNAME,
    STORE_INDEX_FILENAME,
)
from .settings import StoredSnapshot


def store_root_for(
    source_root: Path,
    store_dir_name: str = STORE_DIRNAME,
) -> Path:
    """
    Return the ArchiveSnapshot store folder for a source folder.
    """
    return source_root / store_dir_name


def snapshot_folder_for(source_root: Path, date_key: str, time_slug: str) -> Path:
    """
    Build the dated snapshot folder path.

    date_key format: YYYY-MM-DD
    time_slug format: HHMMSS
    """
    year, month, _day = date_key.split("-")
    return store_root_for(source_root) / year / month / f"{date_key}_{time_slug}"


def load_project_context_meta(snapshot_dir: Path) -> tuple[bool, int, Path | None]:
    """
    Return Project Context Helper attachment state for a snapshot.
    """
    context_dir = snapshot_dir / PROJECT_CONTEXT_DEST_DIRNAME
    index_path = context_dir / PROJECT_CONTEXT_INDEX_FILENAME
    if not index_path.exists():
        return False, 0, None
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return True, int(data.get("file_count", 0)), context_dir
    except Exception:
        return True, 0, context_dir


def discover_snapshots(source_root: Path) -> list[StoredSnapshot]:
    """
    Discover snapshots by reading manifests under the store root.
    """
    base = store_root_for(source_root)
    if not base.exists():
        return []
    snapshots: list[StoredSnapshot] = []
    for manifest_path in sorted(base.rglob(MANIFEST_FILENAME)):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            created = data.get("created", "")
            summary = data.get("summary", {})
            archive_name = data.get("archive_name", "")
            folder_name = manifest_path.parent.name
            date_key = folder_name[:10]
            attached, file_count, context_dir = load_project_context_meta(manifest_path.parent)
            snapshots.append(
                StoredSnapshot(
                    date_key=date_key,
                    created=created,
                    snapshot_dir=manifest_path.parent,
                    manifest_path=manifest_path,
                    archive_name=archive_name,
                    included_count=int(summary.get("included_count", 0)),
                    skipped_count=int(summary.get("skipped_count", 0)),
                    included_bytes=int(summary.get("included_bytes", 0)),
                    project_context_attached=attached,
                    project_context_file_count=file_count,
                    project_context_dir=context_dir,
                )
            )
        except Exception:
            continue
    snapshots.sort(key=lambda item: str(item.snapshot_dir))
    return snapshots


def snapshots_by_date(source_root: Path) -> dict[str, list[StoredSnapshot]]:
    """
    Group discovered snapshots by date.
    """
    grouped: dict[str, list[StoredSnapshot]] = {}
    for snapshot in discover_snapshots(source_root):
        grouped.setdefault(snapshot.date_key, []).append(snapshot)
    return grouped


def latest_snapshot_before(
    source_root: Path,
    snapshot_dir: Path,
) -> StoredSnapshot | None:
    """
    Return the previous snapshot before a given snapshot directory.
    """
    snapshots = discover_snapshots(source_root)
    snapshots = [item for item in snapshots if item.snapshot_dir < snapshot_dir]
    if not snapshots:
        return None
    return snapshots[-1]


def write_store_index(source_root: Path) -> Path:
    """
    Write the ARCHIVE_SNAPSHOT_INDEX.json summary file.
    """
    base = store_root_for(source_root)
    base.mkdir(parents=True, exist_ok=True)
    snapshots = discover_snapshots(source_root)
    data = {
        "source_root": str(source_root),
        "snapshot_count": len(snapshots),
        "snapshots": [
            {
                "date_key": item.date_key,
                "created": item.created,
                "snapshot_dir": str(item.snapshot_dir),
                "manifest_path": str(item.manifest_path),
                "archive_name": item.archive_name,
                "included_count": item.included_count,
                "skipped_count": item.skipped_count,
                "included_bytes": item.included_bytes,
                "project_context_attached": item.project_context_attached,
                "project_context_file_count": item.project_context_file_count,
                "project_context_dir": str(item.project_context_dir) if item.project_context_dir else "",
            }
            for item in snapshots
        ],
    }
    path = base / STORE_INDEX_FILENAME
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    return path
