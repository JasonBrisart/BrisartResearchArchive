"""
Filesystem helpers for ReadmeBuilder.
"""

from __future__ import annotations

import datetime
from collections import Counter
from pathlib import Path

from constants import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    DEFAULT_EXCLUDE_SUFFIXES,
    MAX_TREE_ITEMS,
)


def timestamp_now() -> str:
    """
    Return a timezone-aware timestamp string.
    """
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def validate_root(root: Path) -> Path:
    """
    Resolve and validate the selected project root.
    """
    root = root.expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"Folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Selected path is not a folder: {root}")

    return root


def is_excluded(path: Path, root: Path) -> bool:
    """
    Return True if a path should be excluded from scanning.
    """
    try:
        rel_parts = path.relative_to(root).parts
    except ValueError:
        return True

    if path.is_symlink():
        return True

    if any(part in DEFAULT_EXCLUDE_DIRS for part in rel_parts):
        return True

    if path.name in DEFAULT_EXCLUDE_FILES:
        return True

    if path.suffix.lower() in DEFAULT_EXCLUDE_SUFFIXES:
        return True

    return False


def iter_project_paths(root: Path) -> list[Path]:
    """
    Return all non-excluded paths inside a project root.
    """
    paths: list[Path] = []

    for path in sorted(root.rglob("*")):
        if is_excluded(path, root):
            continue

        paths.append(path)

    return paths


def iter_project_files(root: Path) -> list[Path]:
    """
    Return all non-excluded files inside a project root.
    """
    return [path for path in iter_project_paths(root) if path.is_file()]


def safe_read_text(path: Path) -> str:
    """
    Safely read a text file.
    """
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def humanize_project_name(root: Path) -> str:
    """
    Convert a folder name into a readable project name.
    """
    raw = root.name.replace("_", " ").replace("-", " ").strip()

    if not raw:
        return "Project"

    known_words = {
        "api": "API",
        "gui": "GUI",
        "cli": "CLI",
        "ai": "AI",
        "json": "JSON",
        "csv": "CSV",
        "readme": "README",
        "builder": "Builder",
        "context": "Context",
        "helper": "Helper",
    }

    parts = []

    for part in raw.split():
        lower = part.lower()
        parts.append(known_words.get(lower, part.capitalize()))

    return " ".join(parts)


def build_tree(root: Path) -> str:
    """
    Build a readable project folder tree.
    """
    lines: list[str] = []
    count = 0

    for path in sorted(root.rglob("*")):
        if count >= MAX_TREE_ITEMS:
            lines.append("  ...")
            break

        if is_excluded(path, root):
            continue

        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        depth = len(rel.parts) - 1
        prefix = "  " * depth + "- "
        label = f"{path.name}/" if path.is_dir() else path.name

        lines.append(prefix + label)
        count += 1

    if not lines:
        return "(No files detected.)"

    return "\n".join(lines)


def collect_extension_counts(files: list[Path]) -> Counter:
    """
    Count file extensions.
    """
    counter: Counter = Counter()

    for path in files:
        suffix = path.suffix.lower() or "(no extension)"
        counter[suffix] += 1

    return counter


def detect_existing_readme(root: Path) -> bool:
    """
    Return True if the project already has a README.md.
    """
    return (root / "README.md").exists()


def detect_license(root: Path) -> str:
    """
    Detect common license files.
    """
    names = [
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "COPYING",
        "COPYING.txt",
    ]

    for name in names:
        if (root / name).exists():
            return name

    return ""


def detect_version_file(root: Path) -> str:
    """
    Detect common version/config files.
    """
    names = [
        "version.txt",
        "VERSION",
        "VERSION.txt",
        "pyproject.toml",
        "package.json",
    ]

    for name in names:
        if (root / name).exists():
            return name

    return ""


def collect_top_level_components(root: Path, files: list[Path]) -> list[dict]:
    """
    Summarize top-level project components.
    """
    data: dict[str, dict] = {}

    for path in files:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue

        if len(rel.parts) == 1:
            component = "(root files)"
        else:
            component = rel.parts[0]

        if component not in data:
            data[component] = {
                "name": component,
                "file_count": 0,
                "extensions": Counter(),
                "examples": [],
            }

        data[component]["file_count"] += 1
        data[component]["extensions"][path.suffix.lower() or "(no extension)"] += 1

        if len(data[component]["examples"]) < 5:
            data[component]["examples"].append(str(rel))

    components = list(data.values())
    components.sort(key=lambda item: item["file_count"], reverse=True)

    results = []

    for component in components:
        results.append(
            {
                "name": component["name"],
                "file_count": component["file_count"],
                "extensions": dict(sorted(component["extensions"].items())),
                "examples": component["examples"],
            }
        )

    return results