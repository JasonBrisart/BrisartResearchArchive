"""
File: cli.py

Purpose
-------
Run Project Context Helper from the command line: parse arguments, build export settings from
  the preset, remembered settings, a named profile, and explicit flags, run the export, record
  it, and print the result. Also lists and deletes saved custom profiles, and opens the desktop
  window when no project folder is given.

Communication / relationships
-----------------------------
Imports app (banner), export/settings.py (presets and flag parsing), export/pipeline.py
  (create_context), export/events.py (--progress), and storage (profiles, last settings,
  record_export). Imported by run.py (main) and tests/test_cli.py. gui/window.py is imported
  only when the window opens, so command-line exports load neither tkinter nor any network
  module.

Settings / parameters
---------------------
Settings are applied in order, later winning: the --profile preset (archive by default),
  --use-last-settings, --load-profile NAME, then explicit flags. --extensions replaces the
  extension set; --exclude-dir/--exclude-file add to it. --workers accepts auto (default,
  every detected CPU core) or 1-32. Byte limits must be positive; negative detail and Git
  history limits count as 0. --progress writes phases to stderr so stdout stays parseable.
  Every successful export is added to history; --remember-settings and --save-profile NAME
  store its settings.

Edge cases
----------
Expected failures (bad settings, missing folder, completeness stop, filesystem errors) print
  "Build failed: ..." and exit 1; Ctrl+C exits 130 with nothing published; unknown flags,
  including the removed --check-updates, --install-updates, and --open-releases, exit 2.
  --no-git-state beats --git-state. A missing --load-profile prints a warning and continues.
  A failed --save-profile is reported without failing the finished export. Without a project
  folder, --list-profiles and --delete-profile run and return instead of opening the window.

Known limitations
-----------------
Not every setting has a flag, and no flag turns hashes, contents, and similar sections back
  on after the standard preset disables them; use a saved profile. main() reads sys.argv; it
  takes no argument list.

Examples
--------
From the directory containing run.py (or with its full path from anywhere):

    python run.py "/path/to/project"
    python run.py "/path/to/project" --profile standard --no-zip
    python run.py "/path/to/project" --workers 4 --progress
    python run.py "/path/to/project" --save-profile "Review"
    python run.py "/path/to/project" --load-profile "Review" --no-redact
    python run.py --list-profiles
    python run.py --delete-profile "Review"
"""

from pathlib import Path
import argparse
import sys

from app import APP_NAME, APP_VERSION
from export.events import Progress
from export.pipeline import create_context
from export.settings import (
    AUTO_WORKERS,
    DEFAULT_PROFILE,
    MAX_WORKERS,
    VALID_PROFILES,
    normalize_extension,
    settings_for_profile,
)
import storage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("root", nargs="?", help="Project folder to export. If omitted, GUI mode launches.")
    parser.add_argument("--profile", choices=sorted(VALID_PROFILES), default=DEFAULT_PROFILE)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-file-bytes", type=int, default=None)
    parser.add_argument("--max-total-bytes", type=int, default=None)
    parser.add_argument("--extensions", default=None)
    parser.add_argument("--exclude-dir", action="append", default=[])
    parser.add_argument("--exclude-file", action="append", default=[])
    parser.add_argument("--no-zip", action="store_true")
    parser.add_argument("--no-redact", action="store_true")
    parser.add_argument("--no-hashes", action="store_true")
    parser.add_argument("--no-line-counts", action="store_true")
    parser.add_argument("--no-tree", action="store_true")
    parser.add_argument("--no-index", action="store_true")
    parser.add_argument("--no-contents", action="store_true")
    parser.add_argument("--no-skipped-details", action="store_true")
    parser.add_argument("--skipped-details-limit", type=int, default=None)
    parser.add_argument("--git-state", action="store_true")
    parser.add_argument("--no-git-state", action="store_true")
    parser.add_argument("--git-state-commit-limit", type=int, default=None)
    parser.add_argument("--use-last-settings", action="store_true")
    parser.add_argument("--remember-settings", action="store_true")
    parser.add_argument("--load-profile", metavar="NAME", default=None)
    parser.add_argument("--save-profile", metavar="NAME", default=None)
    parser.add_argument("--delete-profile", metavar="NAME", default=None)
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--flat-output", action="store_true")
    parser.add_argument(
        "--workers", default=None, metavar="auto|N",
        help=f"Capture threads: 'auto' (default, every detected CPU core) or 1-{MAX_WORKERS}.",
    )
    parser.add_argument("--progress", action="store_true", help="Print build phases to stderr.")
    return parser


def settings_from_args(args):
    settings = settings_for_profile(args.profile)
    if args.use_last_settings:
        remembered = storage.load_last_settings()
        if remembered is not None:
            settings = remembered
    if args.load_profile:
        loaded = storage.load_profile(args.load_profile)
        if loaded is not None:
            settings = loaded
        else:
            print(f"Warning: custom profile '{args.load_profile}' was not found; continuing with the settings that would otherwise apply.")
    if args.output_dir:
        settings.output_dir_name = args.output_dir
    if args.max_file_bytes is not None:
        if args.max_file_bytes <= 0:
            raise ValueError(f"--max-file-bytes must be a positive integer (got {args.max_file_bytes}).")
        settings.max_file_bytes = args.max_file_bytes
    if args.max_total_bytes is not None:
        if args.max_total_bytes <= 0:
            raise ValueError(f"--max-total-bytes must be a positive integer (got {args.max_total_bytes}).")
        settings.max_total_bytes = args.max_total_bytes
    if args.extensions:
        settings.include_extensions = {normalize_extension(i) for i in args.extensions.split(",") if i.strip()}
    if args.exclude_dir:
        settings.exclude_dirs.update(args.exclude_dir)
    if args.exclude_file:
        settings.exclude_files.update(args.exclude_file)
    if args.no_zip:
        settings.include_snapshot_zip = False
    if args.no_redact:
        settings.redact_sensitive_lines = False
    if args.no_hashes:
        settings.include_hashes = False
    if args.no_line_counts:
        settings.include_line_counts = False
    if args.no_tree:
        settings.include_folder_tree = False
    if args.no_index:
        settings.include_file_index = False
    if args.no_contents:
        settings.include_file_contents = False
    if args.no_skipped_details:
        settings.include_skipped_details = False
    if args.skipped_details_limit is not None:
        settings.skipped_details_limit = max(0, args.skipped_details_limit)
    if args.git_state:
        settings.include_git_state = True
    if args.no_git_state:
        settings.include_git_state = False
    if args.git_state_commit_limit is not None:
        settings.git_state_commit_limit = max(0, args.git_state_commit_limit)
    if args.flat_output:
        settings.timestamped_export_folder = False
    if args.workers is not None:
        settings.workers = parse_workers_arg(args.workers)
    return settings


def parse_workers_arg(value: str) -> int | str:
    text = value.strip().lower()
    if text == AUTO_WORKERS:
        return AUTO_WORKERS
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"--workers must be 'auto' or a whole number from 1 to {MAX_WORKERS} (got {value!r}).") from None


def run_profile_list() -> None:
    names = storage.list_profiles()
    print(f"{APP_NAME} v{APP_VERSION}")
    print()
    if names:
        print("Custom profiles:")
        for name in names:
            print(f"  - {name}")
    else:
        print("No custom profiles saved yet.")


def run_profile_delete(name: str) -> None:
    deleted = storage.delete_profile(name)
    print(f"{APP_NAME} v{APP_VERSION}")
    print()
    if deleted:
        print(f"Deleted custom profile '{name}'.")
    else:
        print(f"No custom profile named '{name}' was found.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_profiles:
        run_profile_list()
        if not args.root:
            return

    if args.delete_profile:
        run_profile_delete(args.delete_profile)
        if not args.root:
            return

    if not args.root:
        from gui.window import run_gui
        run_gui()
        return

    def print_progress(event: Progress) -> None:
        count = f" {event.completed}/{event.total}" if event.total else ""
        print(f"[{event.phase}]{count} {event.message}".rstrip(), file=sys.stderr)

    try:
        settings = settings_from_args(args)
        result = create_context(
            Path(args.root), settings=settings, progress=print_progress if args.progress else None,
        )
    except (ValueError, OSError) as exc:
        print(f"{APP_NAME} v{APP_VERSION}")
        print()
        print(f"Build failed: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"{APP_NAME} v{APP_VERSION}")
        print()
        print("Build interrupted; no export was published.")
        sys.exit(130)

    storage.record_export(result, settings)
    if args.remember_settings:
        storage.save_last_settings(settings)

    if args.save_profile:
        try:
            storage.save_profile(args.save_profile, settings)
            print(f"Saved custom profile '{args.save_profile}'.")
        except (ValueError, OSError) as exc:
            print(f"Could not save custom profile: {exc}")

    print(f"{APP_NAME} v{APP_VERSION}")
    print()
    print("Build completed")
    print("----------------")
    print(f"Export Folder: {result.export_dir}")
    print(f"Context File : {result.context_path}")
    print(f"Manifest File: {result.manifest_path}")
    print(f"Summary File : {result.summary_path}")
    print(f"Settings File: {result.settings_path}")
    if result.snapshot_path:
        print(f"Snapshot Zip : {result.snapshot_path}")
    if result.git_branch or result.git_commit_short:
        dirty_display = "unverified" if result.git_is_dirty is None else ("dirty" if result.git_is_dirty else "clean")
        print(f"Git State    : {result.git_branch or '(detached HEAD)'} @ {result.git_commit_short or 'unknown'} ({dirty_display})")
    print()
    print(f"Included Files: {result.included_count}")
    print(f"Skipped Files : {result.skipped_count}")
    print(f"Included Bytes: {result.total_included_bytes}")
    print(f"Capture Workers: {result.capture_workers}")

