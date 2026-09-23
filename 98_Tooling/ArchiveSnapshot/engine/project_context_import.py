"""
engine.project_context_import
------------------------------
Project Context Helper bundle ingest support for ArchiveSnapshot.

This module does not generate Project Context Helper exports — Project
Context Helper remains the exporter. ArchiveSnapshot only imports an
already-created bundle from the active inbox folder and attaches it to
a dated snapshot.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .app_info import (
    PROJECT_CONTEXT_ACTIVE_DIRNAME,
    PROJECT_CONTEXT_ACTIVE_SUBDIRNAME,
    PROJECT_CONTEXT_DEST_DIRNAME,
    PROJECT_CONTEXT_INDEX_FILENAME,
    PROJECT_CONTEXT_KNOWN_FILES,
)


@dataclass(slots=True)
class ProjectContextFile:
    """
    One imported Project Context Helper file.
    """

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(slots=True)
class ProjectContextBundle:
    """
    Metadata for a Project Context Helper bundle attached to a snapshot.
    """

    imported_at: str
    source_active_dir: str
    snapshot_project_context_dir: str
    file_count: int
    total_bytes: int
    files: list[ProjectContextFile]
    helper_created: str = ""
    helper_version: str = ""
    helper_root: str = ""
    helper_repository: str = ""
    helper_profile: str = ""
    manifest_summary: dict[str, Any] | None = None


def timestamp_now() -> str:
    """
    Return a local timezone-aware timestamp.
    """

    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def project_context_active_dir(source_root: Path) -> Path:
    """
    Return the active Project Context Helper inbox directory.

    Users place Project Context Helper export files here before creating
    an ArchiveSnapshot snapshot.
    """

    return source_root / PROJECT_CONTEXT_ACTIVE_DIRNAME / PROJECT_CONTEXT_ACTIVE_SUBDIRNAME


def project_context_snapshot_dir(snapshot_dir: Path) -> Path:
    """
    Return the destination folder inside a dated snapshot.
    """

    return snapshot_dir / PROJECT_CONTEXT_DEST_DIRNAME


def sha256_file(path: Path) -> str:
    """
    Return SHA256 checksum for a file.
    """

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file_size(path: Path) -> int:
    """
    Return file size, or zero if unavailable.
    """

    try:
        return path.stat().st_size
    except OSError:
        return 0


def load_json_file(path: Path) -> dict[str, Any]:
    """
    Load JSON safely.
    """

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def has_project_context_bundle(source_root: Path) -> bool:
    """
    Return True if the active inbox contains any Project Context Helper files.
    """

    active_dir = project_context_active_dir(source_root)
    if not active_dir.exists() or not active_dir.is_dir():
        return False

    for path in active_dir.iterdir():
        if path.is_file() and path.name in PROJECT_CONTEXT_KNOWN_FILES:
            return True

    return False


def ensure_project_context_active_dir(source_root: Path) -> Path:
    """
    Create the active inbox folder if it does not exist.
    """

    active_dir = project_context_active_dir(source_root)
    active_dir.mkdir(parents=True, exist_ok=True)
    return active_dir


def discover_project_context_files(active_dir: Path) -> list[Path]:
    """
    Discover known Project Context Helper files in the active inbox.

    The design is intentionally strict so ArchiveSnapshot does not become
    a generic importer. It imports the known Project Context Helper bundle.
    """

    if not active_dir.exists() or not active_dir.is_dir():
        return []

    found: list[Path] = []
    for filename in sorted(PROJECT_CONTEXT_KNOWN_FILES):
        path = active_dir / filename
        if path.exists() and path.is_file():
            found.append(path)

    return found


def build_bundle_metadata(
    source_root: Path,
    snapshot_dir: Path,
    copied_files: list[ProjectContextFile],
) -> ProjectContextBundle:
    """
    Build Project Context Helper bundle metadata.
    """

    active_dir = project_context_active_dir(source_root)
    destination_dir = project_context_snapshot_dir(snapshot_dir)

    manifest_path = destination_dir / "PROJECT_MANIFEST.json"
    manifest = load_json_file(manifest_path)

    settings = manifest.get("settings", {}) if isinstance(manifest.get("settings"), dict) else {}

    total_bytes = sum(item.size_bytes for item in copied_files)

    return ProjectContextBundle(
        imported_at=timestamp_now(),
        source_active_dir=str(active_dir),
        snapshot_project_context_dir=str(destination_dir),
        file_count=len(copied_files),
        total_bytes=total_bytes,
        files=copied_files,
        helper_created=str(manifest.get("created", "")),
        helper_version=str(manifest.get("version", "")),
        helper_root=str(manifest.get("root", "")),
        helper_repository=str(manifest.get("repository_name", "")),
        helper_profile=str(settings.get("profile", "")),
        manifest_summary=manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {},
    )


def import_project_context_bundle(
    source_root: Path,
    snapshot_dir: Path,
) -> ProjectContextBundle | None:
    """
    Import Project Context Helper files into a snapshot.

    Returns None if no active bundle exists.
    """

    active_dir = project_context_active_dir(source_root)
    files = discover_project_context_files(active_dir)

    if not files:
        return None

    destination_dir = project_context_snapshot_dir(snapshot_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)

    copied: list[ProjectContextFile] = []

    for source_path in files:
        destination_path = destination_dir / source_path.name
        shutil.copy2(source_path, destination_path)

        copied.append(
            ProjectContextFile(
                relative_path=source_path.name,
                size_bytes=safe_file_size(destination_path),
                sha256=sha256_file(destination_path),
            )
        )

    bundle = build_bundle_metadata(
        source_root=source_root,
        snapshot_dir=snapshot_dir,
        copied_files=copied,
    )

    index_path = destination_dir / PROJECT_CONTEXT_INDEX_FILENAME
    index_path.write_text(
        json.dumps(asdict(bundle), indent=2),
        encoding="utf-8",
    )

    return bundle


def load_project_context_index(snapshot_dir: Path) -> dict[str, Any]:
    """
    Load Project Context Helper index from a snapshot.
    """

    index_path = project_context_snapshot_dir(snapshot_dir) / PROJECT_CONTEXT_INDEX_FILENAME
    if not index_path.exists():
        return {}

    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def project_context_display_text(snapshot_dir: Path) -> str:
    """
    Build readable calendar detail text for an attached Project Context bundle.
    """

    data = load_project_context_index(snapshot_dir)
    if not data:
        return "Project Context: none"

    lines: list[str] = []
    lines.append("Project Context Helper bundle: attached")
    lines.append(f"Imported: {data.get('imported_at', '')}")
    lines.append(f"Files: {data.get('file_count', 0)}")
    lines.append(f"Helper version: {data.get('helper_version', '')}")
    lines.append(f"Helper profile: {data.get('helper_profile', '')}")

    helper_created = data.get("helper_created", "")
    if helper_created:
        lines.append(f"Helper export created: {helper_created}")

    helper_root = data.get("helper_root", "")
    if helper_root:
        lines.append(f"Helper root: {helper_root}")

    files = data.get("files", [])
    if files:
        lines.append("")
        lines.append("Imported files:")
        for item in files:
            if isinstance(item, dict):
                lines.append(f"- {item.get('relative_path', '')}")

    return "\n".join(lines)