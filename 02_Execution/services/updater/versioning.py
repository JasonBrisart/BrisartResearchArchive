"""
services/updater/versioning.py

Version string parsing/comparison and reading the locally installed
version from version.txt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.updater.constants import LOCAL_VERSION_FILE, VERSION_PATTERN


def normalize_version(version_text: Any) -> tuple[int, int, int]:
    value = str(version_text).strip()
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format: {value!r}")
    return tuple(int(component) for component in match.groups())


def canonical_version(version_text: Any) -> str:
    major, minor, patch = normalize_version(version_text)
    return f"{major}.{minor}.{patch}"


def version_slug(value: str) -> str:
    slug = "".join(c for c in str(value) if c.isalnum() or c in {".", "-", "_"})
    return slug or "latest"


def is_remote_newer(remote_version: Any, local_version: Any) -> bool:
    return normalize_version(remote_version) > normalize_version(local_version)


def default_emit(line: str) -> None:
    print(line)


def read_local_version(emit: Callable[[str], None] = default_emit) -> str:
    if not LOCAL_VERSION_FILE.is_file():
        emit("Local version metadata was not found. Using 0.0.0.")
        return "0.0.0"
    try:
        value = LOCAL_VERSION_FILE.read_text(encoding="utf-8-sig").strip()
        return canonical_version(value)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        emit(f"Local version metadata is invalid. Using 0.0.0: {exc}")
        return "0.0.0"
