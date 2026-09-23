"""
engine
------
Core, non-UI logic for ArchiveSnapshot: scanning, snapshot creation,
snapshot discovery/indexing, change reports, integrity verification,
retention, and Project Context Helper import.

This package has no Tkinter or CLI dependency and can be reused by the
GUI (ui/), the headless daily runner (automation/), or any future
front-end without modification.

Common entry points are re-exported here for convenience:

    from engine import create_snapshot, ArchiveSettings
"""
from .app_info import APP_NAME, APP_VERSION, APP_TAGLINE, AUTHOR, REPOSITORY_NAME
from .settings import ArchiveSettings, AppSettings, StoredSnapshot, SnapshotResult
from .snapshot_builder import create_snapshot
from .snapshot_index import discover_snapshots, snapshots_by_date, write_store_index
from .change_report import compare_snapshot_dirs, build_diff_markdown
from .integrity_check import verify_snapshot_against_source, build_verify_report
from .retention import (
    RetentionPolicy,
    RetentionPlan,
    plan_retention,
    apply_retention,
    build_retention_report,
)
from .snapshot_writer import human_bytes
from .project_context_import import (
    ensure_project_context_active_dir,
    project_context_active_dir,
    project_context_display_text,
)

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "APP_TAGLINE",
    "AUTHOR",
    "REPOSITORY_NAME",
    "ArchiveSettings",
    "AppSettings",
    "StoredSnapshot",
    "SnapshotResult",
    "create_snapshot",
    "discover_snapshots",
    "snapshots_by_date",
    "write_store_index",
    "compare_snapshot_dirs",
    "build_diff_markdown",
    "verify_snapshot_against_source",
    "build_verify_report",
    "RetentionPolicy",
    "RetentionPlan",
    "plan_retention",
    "apply_retention",
    "build_retention_report",
    "human_bytes",
    "ensure_project_context_active_dir",
    "project_context_active_dir",
    "project_context_display_text",
]
