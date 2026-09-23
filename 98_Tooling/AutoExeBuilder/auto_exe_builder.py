#!/usr/bin/env python3
"""
AutoExeBuilder
--------------

A lightweight no-dependency Python utility that helps turn local Python projects
into distributable executables through a clean GUI or CLI workflow.

AutoExeBuilder itself uses only the Python standard library.

Executable packaging requires PyInstaller to be installed in the active Python
environment.

What it does:
- Scans a selected Python project folder.
- Detects likely app entry points.
- Supports GUI and CLI usage.
- Builds one-file or one-folder executable outputs.
- Supports windowed or console builds.
- Writes a build command file.
- Writes human-readable build notes.
- Writes a machine-readable build manifest.

Part of BrisartDevTools.

Author:
Jason Brisart

Repository:
https://github.com/JasonBrisart/BrisartDevTools
"""

from __future__ import annotations

import argparse
import sys

from build_profiles import BuildProfile
from constants import APP_NAME, APP_VERSION, APPLICATION_TAGLINE, AUTHOR, REPOSITORY_NAME, REPOSITORY_URL
from filesystem import ensure_output_folder, humanize_project_name, safe_exe_name, validate_project_folder
from generators import write_build_outputs
from project_scanner import scan_project
from pyinstaller_backend import run_pyinstaller_build


def build_exe_from_profile(profile: BuildProfile) -> dict:
    """
    Build an executable using a complete BuildProfile.
    """
    project_root = validate_project_folder(profile.project_root)
    scan = scan_project(project_root)
    build_result = run_pyinstaller_build(profile)
    outputs = write_build_outputs(profile, scan, build_result)

    return {
        "profile": profile.to_dict(),
        "scan": scan,
        "build_result": build_result,
        "outputs": outputs,
    }


def build_exe_for_project(
    project_folder: str,
    entrypoint: str | None = None,
    output_folder: str | None = None,
    executable_name: str | None = None,
    onefile: bool = True,
    windowed: bool = True,
    clean_build: bool = True,
    icon_path: str = "",
) -> dict:
    """
    Scan a project and build an executable.
    """
    project_root = validate_project_folder(project_folder)
    scan = scan_project(project_root)

    selected_entrypoint = entrypoint or scan.get("suggested_entrypoint")

    if not selected_entrypoint:
        raise ValueError(
            "No entry point detected. Provide one manually, for example:\n"
            "py auto_exe_builder.py C:\\Path\\To\\Project --entrypoint main.py"
        )

    output_root = ensure_output_folder(project_root, output_folder)
    name = executable_name or humanize_project_name(project_root)

    profile = BuildProfile(
        project_root=str(project_root),
        entrypoint=selected_entrypoint,
        output_folder=str(output_root),
        executable_name=safe_exe_name(name),
        onefile=onefile,
        windowed=windowed,
        clean_build=clean_build,
        confirm_overwrite=False,
        icon_path=icon_path,
    )

    build_result = run_pyinstaller_build(profile)
    outputs = write_build_outputs(profile, scan, build_result)

    return {
        "profile": profile.to_dict(),
        "scan": scan,
        "build_result": build_result,
        "outputs": outputs,
    }


def print_intro() -> None:
    """
    Print app intro.
    """
    print(f"{APP_NAME} v{APP_VERSION}")
    print("Part of BrisartDevTools")
    print(f"Author: {AUTHOR}")
    print(f"Repository: {REPOSITORY_NAME}")
    print(REPOSITORY_URL)
    print()
    print(APPLICATION_TAGLINE)
    print()


def create_parser() -> argparse.ArgumentParser:
    """
    Create CLI parser.
    """
    parser = argparse.ArgumentParser(
        prog="auto_exe_builder.py",
        description="Build a distributable executable from a Python project folder.",
    )

    parser.add_argument(
        "project_folder",
        nargs="?",
        help="Path to the Python project folder. If omitted, the GUI opens.",
    )

    parser.add_argument(
        "--entrypoint",
        help="Relative or absolute path to the Python entry point file.",
    )

    parser.add_argument(
        "--output",
        help="Output folder for build artifacts.",
    )

    parser.add_argument(
        "--name",
        help="Executable name.",
    )

    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Build a one-folder executable instead of one-file.",
    )

    parser.add_argument(
        "--console",
        action="store_true",
        help="Show console window instead of windowed/no-console mode.",
    )

    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not clean PyInstaller cache before building.",
    )

    parser.add_argument(
        "--icon",
        help="Optional path to .ico file.",
    )

    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Only scan the project and print detected entry points.",
    )

    return parser


def run_cli(args: list[str]) -> int:
    """
    Run AutoExeBuilder from CLI.
    """
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.project_folder:
        from gui import run_gui
        run_gui()
        return 0

    print_intro()

    project_root = validate_project_folder(parsed.project_folder)
    scan = scan_project(project_root)

    print("Project scan complete.")
    print(f"- Project root: {project_root}")
    print(f"- Files scanned: {scan.get('files_scanned')}")
    print(f"- Python files scanned: {scan.get('python_files_scanned')}")
    print(f"- Suggested entry point: {scan.get('suggested_entrypoint') or 'none'}")
    print()

    if scan.get("entrypoints"):
        print("Detected entry points:")
        for item in scan["entrypoints"]:
            reasons = ", ".join(item.get("entrypoint_reasons", []))
            print(f"- {item['path']} | score={item['entrypoint_score']} | {reasons}")
        print()

    if parsed.scan_only:
        return 0

    result = build_exe_for_project(
        project_folder=str(project_root),
        entrypoint=parsed.entrypoint,
        output_folder=parsed.output,
        executable_name=parsed.name,
        onefile=not parsed.onedir,
        windowed=not parsed.console,
        clean_build=not parsed.no_clean,
        icon_path=parsed.icon or "",
    )

    build_result = result["build_result"]
    outputs = result["outputs"]

    if build_result.get("success"):
        print("Build complete.")
    else:
        print("Build failed.")

    print()
    print("Generated files:")
    print(f"- Build command: {outputs['command']}")
    print(f"- Build notes: {outputs['notes']}")
    print(f"- Build manifest: {outputs['manifest']}")
    print(f"- Expected executable: {outputs['expected_executable']}")
    print()

    if not build_result.get("success"):
        print("Error output:")
        print(build_result.get("stderr", ""))

    return 0 if build_result.get("success") else 1


def main() -> None:
    """
    Main entry point.
    """
    raise SystemExit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()