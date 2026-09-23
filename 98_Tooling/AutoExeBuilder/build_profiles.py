"""
Build profile model for AutoExeBuilder.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BuildProfile:
    """
    User-selected build settings.
    """

    project_root: str
    entrypoint: str
    output_folder: str
    executable_name: str
    onefile: bool = True
    windowed: bool = True
    clean_build: bool = True
    confirm_overwrite: bool = False
    icon_path: str = ""

    def to_dict(self) -> dict:
        """
        Return a JSON-serializable profile.
        """
        return asdict(self)


def resolve_entrypoint(profile: BuildProfile) -> Path:
    """
    Resolve the entry point path from the build profile.
    """
    project_root = Path(profile.project_root).expanduser().resolve()
    entrypoint = Path(profile.entrypoint)

    if not entrypoint.is_absolute():
        entrypoint = project_root / entrypoint

    entrypoint = entrypoint.resolve()

    if not entrypoint.exists():
        raise FileNotFoundError(f"Entry point does not exist: {entrypoint}")

    if not entrypoint.is_file():
        raise FileNotFoundError(f"Entry point is not a file: {entrypoint}")

    if entrypoint.suffix.lower() != ".py":
        raise ValueError(f"Entry point must be a Python file: {entrypoint}")

    return entrypoint


def resolve_icon_path(profile: BuildProfile) -> Path | None:
    """
    Resolve an optional icon path.
    """
    if not profile.icon_path.strip():
        return None

    project_root = Path(profile.project_root).expanduser().resolve()
    icon_path = Path(profile.icon_path)

    if not icon_path.is_absolute():
        icon_path = project_root / icon_path

    icon_path = icon_path.resolve()

    if not icon_path.exists():
        raise FileNotFoundError(f"Icon file does not exist: {icon_path}")

    if not icon_path.is_file():
        raise FileNotFoundError(f"Icon path is not a file: {icon_path}")

    return icon_path