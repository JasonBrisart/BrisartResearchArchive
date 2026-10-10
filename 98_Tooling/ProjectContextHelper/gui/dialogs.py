"""
File: gui/dialogs.py

Purpose
-------
Defines open_folder, show_error, show_warning, show_info, ask_yes_no, format_git_line, show_build_complete for 98_Tooling/ProjectContextHelper/gui.

Communication / relationships
-----------------------------
Direct module imports: pathlib, os, tkinter, core.models.

Settings / parameters
---------------------
No uppercase module-level settings are declared; parameters remain defined in the code below.

Edge cases
----------
Additional edge-case guarantees are not established by this header; existing implementation and tests remain unchanged.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported usage.
"""

from pathlib import Path
import os
from tkinter import messagebox

from core.models import BuildResult


def open_folder(path: Path) -> None:
    try:
        os.startfile(path)
    except AttributeError:
        messagebox.showinfo("Open Folder", f"Export folder:\n{path}")
    except Exception as exc:
        messagebox.showerror("Open Folder Failed", str(exc))


def show_error(title: str, message: str) -> None:
    messagebox.showerror(title, message)


def show_warning(title: str, message: str) -> None:
    messagebox.showwarning(title, message)


def show_info(title: str, message: str) -> None:
    messagebox.showinfo(title, message)


def ask_yes_no(title: str, message: str) -> bool:
    return messagebox.askyesno(title, message)


def format_git_line(result: BuildResult) -> str:
    if not result.git_branch and not result.git_commit_short:
        return ""
    branch_display = result.git_branch or "(detached HEAD)"
    commit_display = result.git_commit_short or "unknown"
    if result.git_is_dirty is None:
        dirty_display = "unverified"
    elif result.git_is_dirty:
        dirty_display = "dirty"
    else:
        dirty_display = "clean"
    return f"Git: {branch_display} @ {commit_display} ({dirty_display})\n\n"


def show_build_complete(result: BuildResult) -> None:
    snapshot_line = f"\n- {result.snapshot_path}" if result.snapshot_path else ""
    messagebox.showinfo(
        "Build Complete",
        (
            f"Export Folder:\n{result.export_dir}\n\n"
            f"{format_git_line(result)}"
            f"Included Files: {result.included_count}\n"
            f"Skipped Files: {result.skipped_count}"
            f"{snapshot_line}"
        ),
    )

