"""
engine.settings
---------------
Dataclasses describing archive settings, scan results, snapshot results,
and saved GUI/app settings for ArchiveSnapshot.

No file I/O or scanning logic lives here — this module only defines the
shapes that other engine modules pass around.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .app_info import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_FILES,
    DEFAULT_EXCLUDED_SUFFIXES,
)


@dataclass(slots=True)
class ArchiveSettings:
    """
    Settings used for one archive snapshot.
    """
    archive_name: str = ""
    archive_description: str = ""
    include_hashes: bool = True
    include_zip_snapshot: bool = True
    include_folder_tree: bool = True
    include_manifest: bool = True
    include_summary: bool = True
    include_diff_report: bool = True
    include_project_context_bundle: bool = True
    max_file_bytes: int = 2_000_000_000
    max_total_bytes: int = 100_000_000_000
    excluded_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_DIRS))
    excluded_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_FILES))
    excluded_suffixes: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDED_SUFFIXES))

    def to_jsonable(self) -> dict[str, Any]:
        data = asdict(self)
        data["excluded_dirs"] = sorted(self.excluded_dirs)
        data["excluded_files"] = sorted(self.excluded_files)
        data["excluded_suffixes"] = sorted(self.excluded_suffixes)
        return data


@dataclass(slots=True)
class FileRecord:
    """
    Metadata for a single file included in a snapshot.
    """
    relative_path: str
    size_bytes: int
    modified_time: str
    extension: str
    sha256: str | None = None


@dataclass(slots=True)
class SkipRecord:
    """
    Metadata for a file skipped during scanning.
    """
    relative_path: str
    reason: str
    size_bytes: int | None = None


@dataclass(slots=True)
class ScanResult:
    """
    Result of scanning a source folder.
    """
    included_paths: list[Path]
    included_records: list[FileRecord]
    skipped_records: list[SkipRecord]
    total_included_bytes: int


@dataclass(slots=True)
class SnapshotResult:
    """
    Result of building one complete dated snapshot.
    """
    export_dir: Path
    summary_path: Path | None
    manifest_path: Path | None
    hashes_path: Path | None
    tree_path: Path | None
    settings_path: Path
    zip_path: Path | None
    diff_path: Path | None
    project_context_path: Path | None
    included_count: int
    skipped_count: int
    total_included_bytes: int


@dataclass(slots=True)
class StoredSnapshot:
    """
    One snapshot entry discovered in the ArchiveSnapshot store.
    """
    date_key: str
    created: str
    snapshot_dir: Path
    manifest_path: Path
    archive_name: str
    included_count: int
    skipped_count: int
    included_bytes: int
    project_context_attached: bool = False
    project_context_file_count: int = 0
    project_context_dir: Path | None = None


@dataclass(slots=True)
class AppSettings:
    """
    Saved GUI application settings (last-used folder, options, daily mode).
    """
    selected_archive_folder: str = ""
    archive_name: str = ""
    archive_description: str = ""
    daily_mode_enabled: bool = False
    daily_run_hour: int = 2
    daily_run_minute: int = 0
    include_zip_snapshot: bool = True
    include_hashes: bool = True
    include_folder_tree: bool = True
    include_diff_report: bool = True
    include_project_context_bundle: bool = True
    max_file_mb: float = 2000
    max_total_mb: float = 100000

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)
