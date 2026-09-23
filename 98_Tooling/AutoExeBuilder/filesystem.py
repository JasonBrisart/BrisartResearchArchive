"""
Filesystem helpers for AutoExeBuilder.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from constants import (
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_SUFFIXES,
    OUTPUT_FOLDER_NAME,
)


def timestamp_now() -> str:
    """
    Return a timezone-aware timestamp.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def validate_project_folder(path_value: str | Path) -> Path:
    """
    Resolve and validate a project folder.
    """
    path = Path(path_value).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Project folder does not exist: {path}")

    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {path}")

    return path


def is_excluded(path: Path, root: Path) -> bool:
    """
    Return True if a path should be ignored by project scanning.
    """
    try:
        relative_parts = path.relative_to(root).parts
    except ValueError:
        return True

    if path.is_symlink():
        return True

    if any(part in DEFAULT_EXCLUDED_DIRS for part in relative_parts):
        return True

    if path.suffix.lower() in DEFAULT_EXCLUDED_SUFFIXES:
        return True

    return False


def iter_project_files(root: Path) -> list[Path]:
    """
    Return non-excluded project files.
    """
    files: list[Path] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        if is_excluded(path, root):
            continue

        files.append(path)

    return files


def safe_read_text(path: Path, max_chars: int = 20000) -> str:
    """
    Safely read a text file.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception:
        return ""


def ensure_output_folder(project_root: Path, output_folder: str | Path | None = None) -> Path:
    """
    Resolve and create the AutoExeBuilder output folder.
    """
    if output_folder:
        output_root = Path(output_folder).expanduser().resolve()
    else:
        output_root = project_root / OUTPUT_FOLDER_NAME

    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def clean_path(path: Path) -> None:
    """
    Remove a file or directory if it exists.
    """
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def humanize_project_name(root: Path) -> str:
    """
    Convert a folder name into a clean executable/project label.
    """
    raw = root.name.replace("_", " ").replace("-", " ").strip()

    if not raw:
        return "PythonApp"

    words = []
    for part in raw.split():
        if part.lower() in {"api", "cli", "gui", "ai", "json", "csv", "exe"}:
            words.append(part.upper())
        else:
            words.append(part.capitalize())

    return "".join(words)


def safe_exe_name(name: str) -> str:
    """
    Convert user-provided output names into a safe executable name.
    """
    allowed = []

    for char in name.strip():
        if char.isalnum() or char in {"_", "-"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("_")

    cleaned = "".join(allowed).strip("_-")

    return cleaned or "PythonApp"