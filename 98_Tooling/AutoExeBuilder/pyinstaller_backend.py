"""
PyInstaller backend wrapper for AutoExeBuilder.

AutoExeBuilder itself uses only the Python standard library.
Executable packaging requires PyInstaller to be available in the active Python environment.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from build_profiles import BuildProfile, resolve_entrypoint, resolve_icon_path


def is_pyinstaller_available() -> bool:
    """
    Return True if PyInstaller is importable in the current Python environment.
    """
    return importlib.util.find_spec("PyInstaller") is not None


def build_pyinstaller_command(profile: BuildProfile) -> list[str]:
    """
    Build a PyInstaller command as a subprocess argument list.
    """
    entrypoint = resolve_entrypoint(profile)
    icon_path = resolve_icon_path(profile)

    output_root = Path(profile.output_folder).expanduser().resolve()
    dist_path = output_root / "dist"
    work_path = output_root / "build"
    spec_path = output_root / "spec"

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
    ]

    if profile.onefile:
        command.append("--onefile")
    else:
        command.append("--onedir")

    if profile.windowed:
        command.append("--windowed")
    else:
        command.append("--console")

    command.extend(["--name", profile.executable_name])
    command.extend(["--distpath", str(dist_path)])
    command.extend(["--workpath", str(work_path)])
    command.extend(["--specpath", str(spec_path)])

    if profile.clean_build:
        command.append("--clean")

    if not profile.confirm_overwrite:
        command.append("--noconfirm")

    if icon_path:
        command.extend(["--icon", str(icon_path)])

    command.append(str(entrypoint))

    return command


def command_to_text(command: list[str]) -> str:
    """
    Convert a command list into readable command text.
    """
    parts = []

    for item in command:
        if " " in item:
            parts.append(f'"{item}"')
        else:
            parts.append(item)

    return " ".join(parts)


def run_pyinstaller_build(profile: BuildProfile) -> dict:
    """
    Run the PyInstaller build command and return build results.
    """
    if not is_pyinstaller_available():
        return {
            "success": False,
            "return_code": None,
            "command": command_to_text(build_pyinstaller_command(profile)),
            "stdout": "",
            "stderr": (
                "PyInstaller is not installed in the active Python environment.\n\n"
                "Install it with:\n"
                "py -m pip install pyinstaller\n\n"
                "Then run AutoExeBuilder again."
            ),
        }

    command = build_pyinstaller_command(profile)

    process = subprocess.run(
        command,
        cwd=profile.project_root,
        capture_output=True,
        text=True,
        errors="replace",
    )

    return {
        "success": process.returncode == 0,
        "return_code": process.returncode,
        "command": command_to_text(command),
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def expected_executable_path(profile: BuildProfile) -> str:
    """
    Return the likely output executable path.
    """
    output_root = Path(profile.output_folder).expanduser().resolve()
    dist_path = output_root / "dist"

    if profile.onefile:
        exe_name = profile.executable_name
        if sys.platform.startswith("win") and not exe_name.lower().endswith(".exe"):
            exe_name += ".exe"
        return str(dist_path / exe_name)

    folder = dist_path / profile.executable_name

    if sys.platform.startswith("win"):
        return str(folder / f"{profile.executable_name}.exe")

    return str(folder / profile.executable_name)