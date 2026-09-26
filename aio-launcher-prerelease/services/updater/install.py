"""
File: services/updater/install.py

Purpose:
Install a verified source ZIP release: extract it, back up the current
application, overwrite files with the release, and remove files that
earlier releases shipped but the Archive no longer uses.

Communication / relationships:
- services/updater/orchestration.py calls apply_zip_update() only with a
  path already verified by services/updater/download.py.
- Uses paths and lists from services/updater/constants.py and versions
  from services/updater/versioning.py.

Settings / parameters:
- Extraction folder: UPDATES_DIR/extracted_<zip stem>.
- Backup folder: BACKUPS_DIR/v<version>_<timestamp>.
- PROTECTED_NAMES are skipped for both backup and copy.
- OBSOLETE_RELEASE_PATHS are removed after the backup and copy steps.

Edge cases:
- A ZIP that wraps everything in one top-level folder is unwrapped.
- Obsolete-path entries that are absolute, contain "..", resolve
  outside the application folder, or are not regular files are skipped.
- Missing obsolete files are ignored.

Known limitations:
- Copying is overwrite-only. Files dropped from a release are deleted
  only if they are listed in OBSOLETE_RELEASE_PATHS.
- No automatic rollback; restore manually from the backup folder.
- A restart is required after installing.

Examples:
- result = apply_zip_update(verified_zip, current_version="0.9.2")
- remove_obsolete_files(app_dir)
"""

from __future__ import annotations

import datetime
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from services.updater.constants import (
    BACKUPS_DIR,
    EXECUTION_DIR,
    OBSOLETE_RELEASE_PATHS,
    PROTECTED_NAMES,
    UPDATES_DIR,
)
from services.updater.versioning import read_local_version, version_slug


@dataclass(slots=True)
class InstallResult:
    backup_dir: Path
    applied_files: tuple[Path, ...]
    restart_required: bool = True
    removed_files: tuple[Path, ...] = ()


def find_release_root(extract_dir: Path) -> Path:
    """If the zip unpacked into a single wrapping subfolder (common for
    GitHub-style source archives), descend into it; otherwise use the
    extraction directory itself."""
    candidates = [e for e in extract_dir.iterdir()]
    if len(candidates) == 1 and candidates[0].is_dir():
        return candidates[0]
    return extract_dir


def backup_application(app_dir: Path, current_version: str) -> Path:
    """Copies the current application's files (excluding PROTECTED_NAMES)
    into a timestamped backup folder BEFORE anything is overwritten, so a
    bad update can always be reversed manually."""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS_DIR / f"v{version_slug(current_version)}_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for entry in app_dir.iterdir():
        if entry.name in PROTECTED_NAMES:
            continue
        destination = backup_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(entry, destination)
    return backup_dir


def apply_extracted_update(source_root: Path, app_dir: Path) -> list[Path]:
    """Overwrite-only: copies every file from source_root into app_dir,
    skipping PROTECTED_NAMES and __pycache__. Files present in app_dir
    but absent from the release are left untouched, never deleted."""
    applied: list[Path] = []
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative = source_path.relative_to(source_root)
        if relative.parts and relative.parts[0] in PROTECTED_NAMES:
            continue
        if "__pycache__" in relative.parts:
            continue
        destination = app_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        applied.append(destination)
    return applied


def remove_obsolete_files(app_dir: Path, obsolete_paths=OBSOLETE_RELEASE_PATHS) -> list[Path]:
    """Deletes files listed in OBSOLETE_RELEASE_PATHS from app_dir.
    Entries that are absolute, contain '..', resolve outside app_dir, or
    point at anything other than a regular file are skipped, never
    deleted. Missing files are ignored. Returns the files removed."""
    removed: list[Path] = []
    root = Path(app_dir).resolve()
    for entry in obsolete_paths:
        text = str(entry).replace("\\", "/").strip()
        parts = [part for part in text.split("/") if part]
        if not parts or text.startswith("/") or ":" in parts[0] or ".." in parts:
            continue
        target = root.joinpath(*parts)
        try:
            resolved = target.resolve()
        except OSError:
            continue
        if root not in resolved.parents:
            continue
        if not resolved.is_file():
            continue
        try:
            resolved.unlink()
        except OSError:
            continue
        removed.append(resolved)
    return removed


def apply_zip_update(verified_zip_path: Path, app_dir: Path | None = None, current_version: str = "") -> InstallResult:
    """Extracts a verified zip release, backs up the current app, and
    overwrites it with the release's files. Raises on any failure --
    the caller is responsible for surfacing that cleanly. Only ever
    called on a path already returned by download_and_verify_release()."""
    if app_dir is None:
        app_dir = EXECUTION_DIR
    extract_dir = UPDATES_DIR / f"extracted_{verified_zip_path.stem}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(verified_zip_path, "r") as archive:
        archive.extractall(extract_dir)

    source_root = find_release_root(extract_dir)
    backup_dir = backup_application(app_dir, current_version or read_local_version())
    applied = apply_extracted_update(source_root, app_dir)
    removed = remove_obsolete_files(app_dir)
    return InstallResult(
        backup_dir=backup_dir,
        applied_files=tuple(applied),
        restart_required=True,
        removed_files=tuple(removed),
    )
