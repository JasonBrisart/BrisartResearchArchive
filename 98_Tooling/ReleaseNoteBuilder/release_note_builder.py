"""
ReleaseNoteBuilder
------------------

A lightweight no-dependency Python utility that compares two project folders
and generates release notes, changelog drafts, and structured release metadata.

Part of BrisartDevTools.
"""

from __future__ import annotations

import sys
from pathlib import Path

from constants import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_NAME,
    REPOSITORY_URL,
    APPLICATION_TAGLINE,
)

from filesystem import validate_folder
from diff_engine import build_project_comparison
from generators import write_outputs


def create_release_notes(
    old_folder: str,
    new_folder: str,
    output_folder: str | None = None,
    version_label: str = "Unversioned Release",
) -> dict:
    old_root = validate_folder(old_folder)
    new_root = validate_folder(new_folder)

    if output_folder:
        output_root = Path(output_folder).expanduser().resolve()
    else:
        output_root = new_root

    comparison = build_project_comparison(old_root, new_root)

    return write_outputs(
        output_folder=output_root,
        comparison=comparison,
        version_label=version_label,
    )


def print_usage() -> None:
    print(f"{APP_NAME} v{APP_VERSION}")
    print("Part of BrisartDevTools")
    print(f"Author: {AUTHOR}")
    print(f"Repository: {REPOSITORY_NAME}")
    print(REPOSITORY_URL)
    print()
    print(APPLICATION_TAGLINE)
    print()

    print("Usage:")
    print()

    print("  GUI:")
    print("    py release_note_builder.py")
    print()

    print("  CLI:")
    print("    py release_note_builder.py OLD_FOLDER NEW_FOLDER")
    print()

    print("  CLI with output folder and version label:")
    print(
        "    py release_note_builder.py "
        "OLD_FOLDER NEW_FOLDER OUTPUT_FOLDER VERSION_LABEL"
    )

    print()

    print("Examples:")
    print(
        '  py release_note_builder.py '
        '"C:\\Projects\\App_v1" '
        '"C:\\Projects\\App_v2"'
    )

    print(
        '  py release_note_builder.py '
        '"C:\\Projects\\App_v1" '
        '"C:\\Projects\\App_v2" '
        '"C:\\Projects\\ReleaseNotes" '
        '"v1.1.0"'
    )

    print()
    print("Generated Files:")
    print("  - RELEASE_NOTES.md")
    print("  - CHANGELOG_DRAFT.md")
    print("  - RELEASE_MANIFEST.json")


def run_cli(args: list[str]) -> int:
    if len(args) < 2:
        print_usage()
        return 1

    old_folder = args[0]
    new_folder = args[1]
    output_folder = args[2] if len(args) >= 3 else None
    version_label = args[3] if len(args) >= 4 else "Unversioned Release"

    print(f"{APP_NAME} v{APP_VERSION}")
    print("Part of BrisartDevTools")
    print(f"Repository: {REPOSITORY_URL}")
    print()

    outputs = create_release_notes(
        old_folder=old_folder,
        new_folder=new_folder,
        output_folder=output_folder,
        version_label=version_label,
    )

    print(f"{APP_NAME} complete.")
    print()

    print("Generated files:")
    print(f"- {outputs['release_notes']}")
    print(f"- {outputs['changelog']}")
    print(f"- {outputs['manifest']}")

    return 0


def main() -> None:
    args = sys.argv[1:]

    if args:
        raise SystemExit(run_cli(args))

    from gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()