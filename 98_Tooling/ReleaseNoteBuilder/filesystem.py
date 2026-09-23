"""
Filesystem helpers for ReleaseNoteBuilder.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from constants import EXCLUDED_DIRS, EXCLUDED_FILES, EXCLUDED_SUFFIXES, TEXT_SUFFIXES


def timestamp_now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def validate_folder(path_value: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {path}")
    return path


def is_excluded(path: Path) -> bool:
    path_parts = set(path.parts)
    if path_parts.intersection(EXCLUDED_DIRS):
        return True
    if path.name in EXCLUDED_FILES:
        return True
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    return False


def iter_project_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not is_excluded(path):
            yield path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_read_text(path: Path, max_chars: int = 12000) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


def collect_file_snapshot(root: Path) -> dict:
    snapshot = {}
    for file_path in iter_project_files(root):
        relative_path = str(file_path.relative_to(root)).replace("\\", "/")
        try:
            stat = file_path.stat()
            snapshot[relative_path] = {
                "path": relative_path,
                "name": file_path.name,
                "suffix": file_path.suffix.lower(),
                "size": stat.st_size,
                "hash": file_hash(file_path),
                "text_preview": safe_read_text(file_path),
            }
        except Exception as exc:
            snapshot[relative_path] = {
                "path": relative_path,
                "name": file_path.name,
                "suffix": file_path.suffix.lower(),
                "size": 0,
                "hash": "",
                "text_preview": "",
                "error": str(exc),
            }
    return snapshot


def build_tree(root: Path) -> list[str]:
    lines = []
    for path in sorted(root.rglob("*")):
        if is_excluded(path):
            continue
        relative = path.relative_to(root)
        depth = len(relative.parts) - 1
        indent = "  " * depth
        if path.is_dir():
            lines.append(f"{indent}- {path.name}/")
        else:
            lines.append(f"{indent}- {path.name}")
    return lines
