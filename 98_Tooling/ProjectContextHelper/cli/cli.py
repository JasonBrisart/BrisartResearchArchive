from pathlib import Path
import argparse
import sys

from core.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_PROFILE,
    VALID_PROFILES,
    settings_for_profile,
)
from core.builder import create_context
from core.utils import normalize_extension
from gui.main_gui import run_gui
from services import storage
from services.updater import (
    apply_exe_update,
    apply_staged_update,
    check_for_updates,
    download_update,
    open_releases_page,
    stage_exe_update,
)


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
    parser.add_argument("--check-updates", action="store_true")
    parser.add_argument("--install-updates", action="store_true")
    parser.add_argument("--open-releases", action="store_true")
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
    return settings


def run_update_check(open_page_when_available: bool = False, install: bool = False) -> None:
    """
    Bugfix (v3.1.2): the download/apply steps below had no exception
    handling at all, unlike the equivalent GUI flow in
    gui/about_tab.py (which already wraps its own call to
    download_update() in a try/except) and unlike this file's main
    build flow (already wrapped in v3.1.1). A corrupted download (see
    the new exception download_update() can now raise for a
    BadZipFile), a checksum mismatch from verify_digest(), or a
    filesystem error while backing up/copying files during
    apply_staged_update()/apply_exe_update() would previously crash
    this command with a raw Python traceback instead of the same
    clean "Update failed: ..." style message every other error path
    in this file already uses.
    """
    info = check_for_updates()
    print(f"{APP_NAME} v{APP_VERSION}")
    print()
    print(info.message)
    if not info.update_available:
        return
    print(f"Release page: {info.release_url}")
    if info.asset_kind == "none":
        return
    if not install:
        if open_page_when_available:
            open_releases_page(info.release_url)
        return
    try:
        if info.asset_kind == "exe":
            print()
            print(f"Downloading update {info.latest_version} (compiled executable)...")
            staged_path = stage_exe_update(info)
            print(f"Staged and checksum-verified at: {staged_path}")
            print("Backing up current executable and applying update...")
            apply_exe_update(staged_path, current_version=APP_VERSION)
            print("Update applied. This process will now exit so the new executable can be swapped into place; it will relaunch automatically in a few seconds.")
            sys.exit(0)
        print()
        print(f"Downloading update {info.latest_version}...")
        staged_dir = download_update(info)
        print(f"Staged in: {staged_dir}")
        print("Backing up current files and applying update...")
        result = apply_staged_update(staged_dir)
        print(f"Backup written to: {result.backup_dir}")
        print(f"Files updated: {len(result.applied_files)}")
        print("Restart the application to run the new version.")
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Update failed: {exc}")
        sys.exit(1)


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


def run_cli() -> None:
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

    if args.check_updates or args.install_updates:
        run_update_check(open_page_when_available=args.open_releases, install=args.install_updates)
        if not args.root:
            return

    if not args.root:
        run_gui()
        return

    try:
        settings = settings_from_args(args)
        result = create_context(Path(args.root), settings=settings)
    except (ValueError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"{APP_NAME} v{APP_VERSION}")
        print()
        print(f"Build failed: {exc}")
        sys.exit(1)

    if args.remember_settings:
        storage.save_last_settings(settings)

    if args.save_profile:
        try:
            storage.save_profile(args.save_profile, settings)
            print(f"Saved custom profile '{args.save_profile}'.")
        except ValueError as exc:
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


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
