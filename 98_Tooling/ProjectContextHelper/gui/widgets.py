"""
File: gui/widgets.py

Purpose
-------
Hold the small Tk pieces more than one tab uses: a vertically scrollable content area, the
  muted text color, opening an export folder in the system file manager, and the Build
  Complete message. Tabs call tkinter.messagebox directly for every other dialog.

Communication / relationships
-----------------------------
Imports export/pipeline.py (BuildResult). Imported by gui/build_tab.py (open_folder,
  show_build_complete, MUTED), gui/options_tab.py and gui/extras_tab.py
  (create_scrollable_area, MUTED), gui/about_tab.py (open_folder), and gui/window.py (MUTED).

Settings / parameters
---------------------
create_scrollable_area(parent) returns the frame to fill; the frame stretches to the canvas
  width. Mouse-wheel scrolling uses MouseWheel (delta/120 per step) on Windows and macOS and
  Button-4/5 on Linux, bound only while the pointer is over the area.

Edge cases
----------
open_folder uses os.startfile; where that does not exist (macOS, Linux) it shows the path in
  a message instead, and any other failure shows an error. The Build Complete message omits
  the Git line when there is no branch or commit and the ZIP line when no ZIP was made, and
  shows an unknown dirty state as "unverified", never "clean".

Known limitations
-----------------
Wheel bindings use bind_all and unbind_all, so they replace any other global wheel handler
  while the pointer is inside the area. Small trackpad deltas (under 120) can round to zero.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.widgets import create_scrollable_area

    window = tk.Tk()
    content = create_scrollable_area(window)
    for index in range(40):
        tk.Label(content, text=f"Row {index}").pack(anchor="w")
    window.mainloop()
"""

from pathlib import Path
import os
import tkinter as tk
from tkinter import messagebox

from export.pipeline import BuildResult

MUTED = "#666666"


def create_scrollable_area(parent: tk.Frame) -> tk.Frame:
    container = tk.Frame(parent)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas)
    content_window_id = canvas.create_window((0, 0), window=content, anchor="nw")

    def on_content_configure(_event=None) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(event) -> None:
        canvas.itemconfig(content_window_id, width=event.width)

    content.bind("<Configure>", on_content_configure)
    canvas.bind("<Configure>", on_canvas_configure)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def on_mousewheel(event) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_mousewheel_linux_up(_event) -> None:
        canvas.yview_scroll(-1, "units")

    def on_mousewheel_linux_down(_event) -> None:
        canvas.yview_scroll(1, "units")

    def bind_wheel(_event=None) -> None:
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        canvas.bind_all("<Button-4>", on_mousewheel_linux_up)
        canvas.bind_all("<Button-5>", on_mousewheel_linux_down)

    def unbind_wheel(_event=None) -> None:
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", bind_wheel)
    canvas.bind("<Leave>", unbind_wheel)

    return content


def open_folder(path: Path) -> None:
    try:
        os.startfile(path)
    except AttributeError:
        messagebox.showinfo("Open Folder", f"Export folder:\n{path}")
    except Exception as exc:
        messagebox.showerror("Open Folder Failed", str(exc))


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
