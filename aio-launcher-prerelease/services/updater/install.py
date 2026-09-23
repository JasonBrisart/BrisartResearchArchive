"""
services/updater/install.py

Real in-place installation for source (zip) releases: extracts a
verified archive, backs up the current application files, then
overwrites them with the release. Everything here only ever runs on a
path already returned by download.download_and_verify_release() --
i.e. already hash- and signature-verified.
"""

from __future__ import annotations

import datetime
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from services.updater.constants import BACKUPS_DIR, EXECUTION_DIR, PROTECTED_NAMES, UPDATES_DIR
from services.updater.versioning import read_local_version, version_slug


@dataclass(slots=True)
class InstallResult:
    backup_dir: Path
    applied_files: tuple[Path, ...]
    restart_required: bool = True


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
    return InstallResult(backup_dir=backup_dir, applied_files=tuple(applied), restart_required=True)
