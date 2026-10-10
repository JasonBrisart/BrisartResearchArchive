"""
File: gui/dialogs.py

Purpose
-------
Wrap tkinter messages, folder opening, and build-complete formatting shared by desktop tabs.

Implemented responsibilities:
- open_folder: Try Windows os.startfile; if unavailable display the path, and if opening fails
  display an error dialog.
- show_error: Display a tkinter error messagebox with the supplied title and message.
- show_warning: Display a tkinter warning messagebox with the supplied title and message.
- show_info: Display a tkinter informational messagebox with the supplied title and message.
- ask_yes_no: Display a confirmation messagebox and return the user's boolean choice.
- format_git_line: Format BuildResult branch/commit and dirty/clean/unverified status for a
  completion dialog; omit the line when both identifiers are absent.
- show_build_complete: Display output folder, optional Git line, included/skipped counts, and
  optional snapshot path from BuildResult.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.models: BuildResult.

Consumers in the supplied source:
- gui/about_tab.py imports ask_yes_no, open_folder, show_error, show_info.
- gui/build_tab.py imports open_folder, show_build_complete, show_error, show_info,
  show_warning.
- gui/profiles_section.py imports ask_yes_no, show_error, show_info, show_warning.

Settings / parameters
---------------------
Accepts dialog titles/messages, folder Paths, or BuildResult. Git formatting distinguishes
  dirty, clean, and unverified.

Function signatures (nested callbacks are scoped to their enclosing function):
- open_folder(path: Path) -> None
- show_error(title: str, message: str) -> None
- show_warning(title: str, message: str) -> None
- show_info(title: str, message: str) -> None
- ask_yes_no(title: str, message: str) -> bool
- format_git_line(result: BuildResult) -> str
- show_build_complete(result: BuildResult) -> None

Edge cases
----------
No Git branch/commit yields no Git summary. Missing os.startfile falls back to displaying the
  path; other opening errors show an error dialog.

BuildResult.snapshot_path=None omits the ZIP line. Git is_dirty=None is displayed as unverified,
  not clean.

Known limitations
-----------------
Automatic folder opening uses Windows os.startfile. On other platforms the helper displays the
  folder path rather than launching a file manager. Dialogs require a tkinter GUI context.

The completion dialog reports BuildResult metadata only; it does not independently reopen/verify
  the output files.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.dialogs import show_info

    window = tk.Tk()
    window.withdraw()
    show_info("Project Context Helper", "Export review completed.")
    window.destroy()
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

