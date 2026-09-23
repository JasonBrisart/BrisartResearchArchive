#!/usr/bin/env python3
"""
ReadmeBuilder
-------------

A tiny no-dependency utility that scans a project folder and generates a
GitHub-focused README draft plus a separate technical analysis file.

What it does:
1. Scans a selected project folder recursively.
2. Detects project structure, file types, Python imports, entry points, and metadata.
3. Builds README_DRAFT.md for GitHub visitors.
4. Builds README_ANALYSIS.md for technical scan details.
5. Builds README_BUILDER_MANIFEST.json with machine-readable scan metadata.

Usage:
- Double-click the script to launch the GUI.
- Or run from the command line:

    py readme_builder.py
    py readme_builder.py "C:\\Path\\To\\Project"

No internet.
No third-party packages.
Works with standard Python.

Author:
Jason Brisart

Repository:
https://github.com/JasonBrisart/BrisartDevTools
"""

from __future__ import annotations

import sys
from pathlib import Path

from filesystem import iter_project_files, timestamp_now, validate_root
from generators import write_outputs


def create_readme_draft(root: Path) -> tuple[Path, Path, Path]:
    """
    Create README_DRAFT.md, README_ANALYSIS.md, and README_BUILDER_MANIFEST.json.
    """
    root = validate_root(root)
    created = timestamp_now()
    files = iter_project_files(root)

    return write_outputs(root, files, created)


def run_cli() -> None:
    """
    Run from the command line.

    If a folder argument is provided, scan that folder.
    Otherwise, scan the current working directory.
    """
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    readme_path, analysis_path, manifest_path = create_readme_draft(folder)

    print("Created:")
    print(readme_path)
    print(analysis_path)
    print(manifest_path)


def main() -> None:
    """
    Entry point.

    CLI mode:
        py readme_builder.py "C:\\Path\\To\\Project"

    GUI mode:
        py readme_builder.py
    """
    if len(sys.argv) > 1:
        run_cli()
    else:
        from gui import run_gui
        run_gui()


if __name__ == "__main__":
    main()