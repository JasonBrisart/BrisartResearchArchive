#!/usr/bin/env python3
"""
main.py
-------
Primary entry point for ArchiveSnapshot.

Usage:
    python main.py
        Open the calendar GUI.

    python main.py snapshot <folder> [options]
        Create one snapshot without opening the GUI.

    python main.py daily --init-config [--config PATH]
        Create an example daily snapshot configuration.

    python main.py daily --once [--config PATH] [--force]
        Run due daily snapshot jobs once and exit.

    python main.py daily --watch [--config PATH]
        Run the visible daily snapshot watcher.

    python main.py prune <folder> [--keep-last N] [--keep-within-days N] [--apply]
        Show (and optionally apply) a snapshot retention policy.

Part of BrisartPreservationTools.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from automation import add_daily_arguments, run_daily_command
from engine import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_NAME,
    ArchiveSettings,
    RetentionPolicy,
    apply_retention,
    build_retention_report,
    create_snapshot,
    human_bytes,
    plan_retention,
)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the ArchiveSnapshot command-line parser.
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=f"{APP_NAME} v{APP_VERSION}",
    )
    subparsers = parser.add_subparsers(dest="command")

    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Create one snapshot from the command line.",
    )
    snapshot_parser.add_argument(
        "folder",
        help="Folder to archive.",
    )
    snapshot_parser.add_argument(
        "--name",
        default="",
        help="Archive name.",
    )
    snapshot_parser.add_argument(
        "--description",
        default="",
        help="Archive description.",
    )
    snapshot_parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Do not create a ZIP snapshot.",
    )
    snapshot_parser.add_argument(
        "--no-hashes",
        action="store_true",
        help="Do not generate SHA256 hashes.",
    )
    snapshot_parser.add_argument(
        "--no-diff",
        action="store_true",
        help="Do not generate a change report against the previous snapshot.",
    )
    snapshot_parser.add_argument(
        "--no-project-context",
        action="store_true",
        help=(
            "Do not attach a Project Context Helper bundle from "
            "SNAPSHOT_ACTIVE."
        ),
    )
    snapshot_parser.add_argument(
        "--max-file-mb",
        type=float,
        default=2000,
        help="Maximum size of one included file in megabytes.",
    )
    snapshot_parser.add_argument(
        "--max-total-mb",
        type=float,
        default=100000,
        help="Maximum total included size in megabytes.",
    )

    daily_parser = subparsers.add_parser(
        "daily",
        help="Headless daily snapshot automation.",
    )
    add_daily_arguments(daily_parser)

    prune_parser = subparsers.add_parser(
        "prune",
        help="Remove old snapshots according to a retention policy.",
    )
    prune_parser.add_argument(
        "folder",
        help="Archived folder whose ARCHIVE_SNAPSHOT store should be pruned.",
    )
    prune_parser.add_argument(
        "--keep-last",
        type=int,
        default=10,
        help="Keep this many of the most recent snapshots (0 disables).",
    )
    prune_parser.add_argument(
        "--keep-within-days",
        type=int,
        default=0,
        help="Also keep any snapshot newer than this many days (0 disables).",
    )
    prune_parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually delete the selected snapshots. Without this flag a "
            "dry-run plan is printed and nothing is removed."
        ),
    )

    return parser


def run_snapshot_command(parsed: argparse.Namespace) -> int:
    """
    Create one snapshot from parsed command-line arguments.
    """
    settings = ArchiveSettings(
        archive_name=parsed.name,
        archive_description=parsed.description,
        include_zip_snapshot=not parsed.no_zip,
        include_hashes=not parsed.no_hashes,
        include_diff_report=not parsed.no_diff,
        include_project_context_bundle=not parsed.no_project_context,
        max_file_bytes=int(parsed.max_file_mb * 1_000_000),
        max_total_bytes=int(parsed.max_total_mb * 1_000_000),
    )
    result = create_snapshot(
        Path(parsed.folder),
        settings=settings,
    )
    print(f"{APP_NAME} v{APP_VERSION}")
    print(f"Created by {AUTHOR}")
    print(f"Part of {REPOSITORY_NAME}")
    print()
    print("Archive snapshot complete.")
    print(f"Export folder  : {result.export_dir}")
    print(f"Included files : {result.included_count}")
    print(f"Skipped files  : {result.skipped_count}")
    print(f"Included size  : {human_bytes(result.total_included_bytes)}")
    if result.summary_path:
        print(f"Summary        : {result.summary_path}")
    if result.manifest_path:
        print(f"Manifest       : {result.manifest_path}")
    if result.hashes_path:
        print(f"Hashes         : {result.hashes_path}")
    if result.tree_path:
        print(f"Folder tree    : {result.tree_path}")
    if result.diff_path:
        print(f"Diff report    : {result.diff_path}")
    if result.project_context_path:
        print(f"Project Context: {result.project_context_path}")
    if result.zip_path:
        print(f"ZIP snapshot   : {result.zip_path}")
    return 0


def run_prune_command(parsed: argparse.Namespace) -> int:
    """
    Show, and optionally apply, a snapshot retention policy.

    The default is a dry run: the plan is printed and nothing is removed
    unless --apply is passed. This mirrors the engine's safe-by-default
    contract so a prune is always previewed before anything is deleted.
    """
    policy = RetentionPolicy(
        keep_last=parsed.keep_last,
        keep_within_days=parsed.keep_within_days,
    )
    if parsed.apply:
        plan = apply_retention(parsed.folder, policy)
    else:
        plan = plan_retention(parsed.folder, policy)

    print(f"{APP_NAME} v{APP_VERSION}")
    print()
    print(build_retention_report(plan))
    if not parsed.apply and plan.removed:
        print()
        print("Dry run only. Re-run with --apply to remove these snapshots.")
    return 0


def main() -> None:
    """
    Run ArchiveSnapshot.
    """
    parser = build_parser()
    parsed = parser.parse_args(sys.argv[1:])
    if parsed.command == "snapshot":
        raise SystemExit(run_snapshot_command(parsed))
    if parsed.command == "daily":
        raise SystemExit(run_daily_command(parsed))
    if parsed.command == "prune":
        raise SystemExit(run_prune_command(parsed))
    from ui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
