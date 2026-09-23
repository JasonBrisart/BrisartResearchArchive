#!/usr/bin/env python3
"""
automation.daily_snapshot_runner
----------------------------------
A local-first, headless daily snapshot runner for ArchiveSnapshot.

This replaces the previous standalone DailyArchiveBackup.py script. It no
longer depends on the legacy single-file ArchiveSnapshot.py (v1.0.0) — it
calls straight into engine.snapshot_builder.create_snapshot, so daily jobs
produce the exact same dated calendar snapshots as the GUI and CLI.

This module does not connect to the internet, does not upload files, and
does not run hidden. It only archives folders explicitly configured by
the user in a config file.

Part of BrisartPreservationTools.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from engine import APP_VERSION as ARCHIVE_SNAPSHOT_VERSION
from engine import ArchiveSettings, create_snapshot, human_bytes
from engine.app_info import (
    DAILY_CONFIG_FILENAME,
    DAILY_LOG_FILENAME,
    DAILY_STATE_FILENAME,
)

APP_NAME = "DailySnapshotRunner"
APP_VERSION = "2.0.0"


@dataclass(slots=True)
class DailySnapshotJob:
    """
    One configured daily snapshot job.
    """

    name: str
    source_folder: str
    archive_description: str = ""
    enabled: bool = True
    include_zip_snapshot: bool = True
    include_hashes: bool = True
    include_folder_tree: bool = True
    include_diff_report: bool = True
    include_project_context_bundle: bool = True
    max_file_mb: float = 2000
    max_total_mb: float = 100000


@dataclass(slots=True)
class DailySnapshotConfig:
    """
    Daily snapshot configuration: a list of jobs plus a preferred run time.
    """

    jobs: list[DailySnapshotJob] = field(default_factory=list)
    run_hour: int = 2
    run_minute: int = 0
    state_filename: str = DAILY_STATE_FILENAME
    log_filename: str = DAILY_LOG_FILENAME

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "jobs": [asdict(job) for job in self.jobs],
            "run_hour": self.run_hour,
            "run_minute": self.run_minute,
            "state_filename": self.state_filename,
            "log_filename": self.log_filename,
        }


def timestamp_now() -> str:
    """
    Return a timezone-aware timestamp.
    """

    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def today_key() -> str:
    """
    Return today's local date key.
    """

    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d")


def load_config(path: Path) -> DailySnapshotConfig:
    """
    Load daily snapshot config from disk.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Create one with: python main.py daily --init-config --config {path}"
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = []

    for item in data.get("jobs", []):
        jobs.append(
            DailySnapshotJob(
                name=item.get("name", ""),
                source_folder=item.get("source_folder", ""),
                archive_description=item.get("archive_description", ""),
                enabled=bool(item.get("enabled", True)),
                include_zip_snapshot=bool(item.get("include_zip_snapshot", True)),
                include_hashes=bool(item.get("include_hashes", True)),
                include_folder_tree=bool(item.get("include_folder_tree", True)),
                include_diff_report=bool(item.get("include_diff_report", True)),
                include_project_context_bundle=bool(item.get("include_project_context_bundle", True)),
                max_file_mb=float(item.get("max_file_mb", 2000)),
                max_total_mb=float(item.get("max_total_mb", 100000)),
            )
        )

    return DailySnapshotConfig(
        jobs=jobs,
        run_hour=int(data.get("run_hour", 2)),
        run_minute=int(data.get("run_minute", 0)),
        state_filename=data.get("state_filename", DAILY_STATE_FILENAME),
        log_filename=data.get("log_filename", DAILY_LOG_FILENAME),
    )


def save_config(path: Path, config: DailySnapshotConfig) -> None:
    """
    Save config file.
    """

    path.write_text(
        json.dumps(config.to_jsonable(), indent=2),
        encoding="utf-8",
    )


def create_default_config(path: Path) -> None:
    """
    Create an example config file.
    """

    if path.exists():
        raise FileExistsError(f"Config already exists: {path}")

    example = DailySnapshotConfig(
        jobs=[
            DailySnapshotJob(
                name="Example Snapshot Job",
                source_folder=str(Path.cwd()),
                archive_description=(
                    "Example daily snapshot job. Replace this with the folder "
                    "you want to preserve."
                ),
                enabled=False,
            )
        ],
        run_hour=2,
        run_minute=0,
    )
    save_config(path, example)


def load_state(path: Path) -> dict[str, Any]:
    """
    Load state file.
    """

    if not path.exists():
        return {"last_run_by_job": {}, "history": []}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"last_run_by_job": {}, "history": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    """
    Save state file.
    """

    path.write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )


def append_log(path: Path, text: str) -> None:
    """
    Append to log file.
    """

    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def run_job(job: DailySnapshotJob) -> dict[str, Any]:
    """
    Run one daily snapshot job using the shared engine.
    """

    settings = ArchiveSettings(
        archive_name=job.name,
        archive_description=job.archive_description,
        include_zip_snapshot=job.include_zip_snapshot,
        include_hashes=job.include_hashes,
        include_folder_tree=job.include_folder_tree,
        include_diff_report=job.include_diff_report,
        include_project_context_bundle=job.include_project_context_bundle,
        max_file_bytes=int(job.max_file_mb * 1_000_000),
        max_total_bytes=int(job.max_total_mb * 1_000_000),
    )

    result = create_snapshot(source_root=job.source_folder, settings=settings)

    return {
        "job_name": job.name,
        "source_folder": job.source_folder,
        "created": timestamp_now(),
        "success": True,
        "export_dir": str(result.export_dir),
        "included_count": result.included_count,
        "skipped_count": result.skipped_count,
        "included_bytes": result.total_included_bytes,
        "included_size_readable": human_bytes(result.total_included_bytes),
        "summary_path": str(result.summary_path) if result.summary_path else "",
        "manifest_path": str(result.manifest_path) if result.manifest_path else "",
        "hashes_path": str(result.hashes_path) if result.hashes_path else "",
        "tree_path": str(result.tree_path) if result.tree_path else "",
        "diff_path": str(result.diff_path) if result.diff_path else "",
        "project_context_path": str(result.project_context_path) if result.project_context_path else "",
        "zip_path": str(result.zip_path) if result.zip_path else "",
    }


def run_all_due_jobs(config_path: Path, force: bool = False) -> list[dict[str, Any]]:
    """
    Run all jobs that are due today.
    """

    config = load_config(config_path)
    state_path = config_path.parent / config.state_filename
    log_path = config_path.parent / config.log_filename

    state = load_state(state_path)
    last_run_by_job = state.setdefault("last_run_by_job", {})
    history = state.setdefault("history", [])

    date_key = today_key()
    results: list[dict[str, Any]] = []

    append_log(
        log_path,
        (
            f"\n## Daily Snapshot Run - {timestamp_now()}\n\n"
            f"- Tool: `{APP_NAME} v{APP_VERSION}`\n"
            f"- ArchiveSnapshot engine version: `{ARCHIVE_SNAPSHOT_VERSION}`\n"
            f"- Config: `{config_path}`\n"
            f"- Force run: `{force}`\n"
        ),
    )

    for job in config.jobs:
        if not job.enabled:
            append_log(log_path, f"- Skipped disabled job: `{job.name}`\n")
            continue

        if not job.name.strip():
            append_log(log_path, "- Skipped unnamed job.\n")
            continue

        if not job.source_folder.strip():
            append_log(log_path, f"- Skipped `{job.name}` because source folder is empty.\n")
            continue

        already_ran_today = last_run_by_job.get(job.name) == date_key
        if already_ran_today and not force:
            append_log(log_path, f"- Already ran today: `{job.name}`\n")
            continue

        try:
            result = run_job(job)
            results.append(result)
            last_run_by_job[job.name] = date_key
            history.append(result)

            append_log(
                log_path,
                (
                    f"### Job Complete: `{job.name}`\n\n"
                    f"- Source: `{job.source_folder}`\n"
                    f"- Snapshot: `{result['export_dir']}`\n"
                    f"- Included files: `{result['included_count']}`\n"
                    f"- Skipped files: `{result['skipped_count']}`\n"
                    f"- Included size: `{result['included_size_readable']}`\n"
                ),
            )
        except Exception as exc:
            failure = {
                "job_name": job.name,
                "source_folder": job.source_folder,
                "created": timestamp_now(),
                "success": False,
                "error": str(exc),
            }
            results.append(failure)
            history.append(failure)

            append_log(
                log_path,
                (
                    f"### Job Failed: `{job.name}`\n\n"
                    f"- Source: `{job.source_folder}`\n"
                    f"- Error: `{exc}`\n"
                ),
            )

    save_state(state_path, state)
    return results


def should_run_now(config: DailySnapshotConfig, last_loop_date: str | None) -> bool:
    """
    Determine if the long-running watcher should trigger today.
    """

    now = datetime.datetime.now().astimezone()
    current_date = now.strftime("%Y-%m-%d")

    if last_loop_date == current_date:
        return False

    if now.hour > config.run_hour:
        return True

    if now.hour == config.run_hour and now.minute >= config.run_minute:
        return True

    return False


def watch_daily(config_path: Path) -> None:
    """
    Long-running local watcher.

    This does not install itself. This does not hide itself. It only runs
    while the user keeps it running (e.g. in a terminal, or under a
    process manager / scheduled task the user sets up themselves).
    """

    print(f"{APP_NAME} v{APP_VERSION}")
    print("Daily snapshot watcher started.")
    print(f"Config: {config_path}")
    print("Press Ctrl+C to stop.")
    print()

    last_loop_date: str | None = None

    while True:
        try:
            config = load_config(config_path)
            if should_run_now(config, last_loop_date):
                print(f"[{timestamp_now()}] Running due snapshot jobs...")
                run_all_due_jobs(config_path, force=False)
                last_loop_date = today_key()
                print(f"[{timestamp_now()}] Daily snapshot pass complete.")
            time.sleep(30)
        except KeyboardInterrupt:
            print()
            print("Daily snapshot watcher stopped.")
            return
        except Exception as exc:
            print(f"[{timestamp_now()}] Error: {exc}")
            time.sleep(60)


def add_daily_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Attach daily-automation CLI arguments to a parser (used by main.py).
    """

    parser.add_argument(
        "--config",
        default=DAILY_CONFIG_FILENAME,
        help="Path to daily snapshot config JSON file.",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Create an example config file.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run due jobs once and exit.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run jobs even if they already ran today.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run as a visible daily watcher process.",
    )


def run_daily_command(parsed: argparse.Namespace) -> int:
    """
    Handle the 'daily' subcommand from main.py.
    """

    config_path = Path(parsed.config).expanduser().resolve()

    if parsed.init_config:
        create_default_config(config_path)
        print(f"Created example config: {config_path}")
        return 0

    if parsed.once:
        results = run_all_due_jobs(config_path, force=parsed.force)
        print(f"{APP_NAME} v{APP_VERSION}")
        print("Run complete.")
        print(f"Jobs processed: {len(results)}")
        for result in results:
            if result.get("success"):
                print(f"- {result.get('job_name')}: {result.get('export_dir')}")
            else:
                print(f"- {result.get('job_name')}: FAILED - {result.get('error')}")
        return 0

    if parsed.watch:
        watch_daily(config_path)
        return 0

    print(f"{APP_NAME} v{APP_VERSION}")
    print("No action specified. Use --init-config, --once, or --watch.")
    return 0


def main() -> None:
    """
    Standalone entry point (also reachable via: python main.py daily ...).
    """

    parser = argparse.ArgumentParser(
        prog="daily_snapshot_runner.py",
        description=f"{APP_NAME} v{APP_VERSION}",
    )
    add_daily_arguments(parser)
    parsed = parser.parse_args(sys.argv[1:])
    raise SystemExit(run_daily_command(parsed))


if __name__ == "__main__":
    main()