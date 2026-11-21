"""
File: gui/widgets.py

Purpose
-------
Hold the small Tk pieces more than one tab uses: a vertically scrollable content area whose
  scrollbar appears only when the content is taller than the window, a text box synced to a
  StringVar, the muted text color, opening an export folder in the system file manager, and
  the Build Complete message. Tabs call tkinter.messagebox directly for every other dialog.

Communication / relationships
-----------------------------
Imports export/pipeline.py (BuildResult). Imported by gui/build_tab.py (open_folder,
  show_build_complete, MUTED), gui/options_tab.py (create_scrollable_area,
  create_text_field, MUTED),
  gui/extras_tab.py (create_scrollable_area, MUTED, open_folder), and gui/view_tab.py and
  gui/window.py (MUTED).

Settings / parameters
---------------------
create_scrollable_area(parent) returns the frame to fill; the frame stretches to the canvas
  width. The scroll region is the content's requested height (never less than the view), and
  scrollbar_needed() decides whether the scrollbar is packed: only when that height exceeds
  the visible height. Mouse-wheel scrolling uses MouseWheel (delta/120 per step) on Windows
  and macOS and Button-4/5 on Linux, bound only while the pointer is over the area, and does
  nothing while the scrollbar is hidden.

Edge cases
----------
The layout is recomputed when the content resizes (a section is hidden or shown), when the
  area resizes, and when the area is mapped, so a tab that was hidden while sections changed
  is correct the moment it is shown. When the scrollbar goes away the view returns to the
  top. An area Tk has not sized yet (height 1 or less) never shows a scrollbar. Showing the
  scrollbar narrows the area by its own width, which cannot change the content's height
  because the labels use fixed wrap widths, so the layout settles in one step.
  open_folder uses os.startfile; where that does not exist (macOS, Linux) it shows the path in
  a message instead, and any other failure shows an error. The Build Complete message omits
  the Git line when there is no branch or commit and the ZIP line when no ZIP was made, and
  shows an unknown dirty state as "unverified", never "clean".

Known limitations
-----------------
A text box changed by code (a profile loaded) replaces its content and clears its undo history,
  so Ctrl+Z cannot bring back the previous profile's list. Wheel bindings use bind_all and
  unbind_all, so they replace any other global wheel handler
  while the pointer is inside the area. Small trackpad deltas (under 120) can round to zero.
  Not verified on a real display: the tests drive this code through a recording stand-in for
  tkinter, so how the scrollbar and layout look needs a manual check on each platform.

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


def scrollbar_needed(content_height: int, view_height: int) -> bool:
    """
    True when the content is taller than the visible area. A view of 1 pixel or less is a
    window Tk has not sized yet (a tab that has never been shown), where no scrollbar should
    appear.
    """
    return view_height > 1 and content_height > view_height


def create_scrollable_area(parent: tk.Frame) -> tk.Frame:
    container = tk.Frame(parent)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0, borderwidth=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    content = tk.Frame(canvas)
    content_window_id = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar_shown = False

    def update_layout(_event=None) -> None:
        """Fit the scroll region to the content, and show the scrollbar only if it is needed."""
        nonlocal scrollbar_shown
        view = canvas.winfo_height()
        wanted = content.winfo_reqheight()
        canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(wanted, view)))
        needed = scrollbar_needed(wanted, view)
        if needed and not scrollbar_shown:
            scrollbar.pack(side="right", fill="y", before=canvas)
            scrollbar_shown = True
        elif not needed and scrollbar_shown:
            scrollbar.pack_forget()
            scrollbar_shown = False
            canvas.yview_moveto(0)

    def on_canvas_configure(event) -> None:
        canvas.itemconfig(content_window_id, width=event.width)
        update_layout()

    content.bind("<Configure>", update_layout)
    canvas.bind("<Configure>", on_canvas_configure)
    # A tab that was hidden while sections changed has no Configure to report that; showing it does.
    canvas.bind("<Map>", update_layout)

    def on_mousewheel(event) -> None:
        if scrollbar_shown:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def on_mousewheel_linux_up(_event) -> None:
        if scrollbar_shown:
            canvas.yview_scroll(-1, "units")

    def on_mousewheel_linux_down(_event) -> None:
        if scrollbar_shown:
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


def create_text_field(parent: tk.Widget, variable: tk.StringVar, height: int = 3) -> tk.Text:
    """
    A small word-wrapped text box kept in step with a StringVar in both directions, for lists
    too long for one line. Tk raises <<Modified>> for every change however it was made (typing,
    paste, cut, undo), and the flag is cleared after each sync so the event fires again.
    """
    box = tk.Text(parent, height=height, wrap="word", undo=True)

    def show(*_args) -> None:
        if box.get("1.0", "end-1c") != variable.get():
            box.delete("1.0", "end")
            box.insert("1.0", variable.get())
            box.edit_reset()

    def store(_event=None) -> None:
        if box.edit_modified():
            variable.set(box.get("1.0", "end-1c"))
            box.edit_modified(False)

    variable.trace_add("write", show)
    box.bind("<<Modified>>", store)
    show()
    box.edit_modified(False)
    return box


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
