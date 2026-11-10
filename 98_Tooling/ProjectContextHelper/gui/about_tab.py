"""
File: gui/about_tab.py

Purpose
-------
Build the About tab: application information and attribution, and the Recent Exports list
  with open, refresh, and clear.

Communication / relationships
-----------------------------
Imports app (attribution), gui/state.py (GuiState), gui/widgets.py (open_folder), and storage
  (history). Imported by gui/window.py. Registers refresh_history as state.history_refresh so
  the Build tab can refresh the list after each export.

Settings / parameters
---------------------
Shows the newest 20 history entries: created, profile, included and skipped counts, Git
  branch and commit when recorded, and project folder.

Edge cases
----------
An empty history shows a placeholder row. Opening an export whose folder was deleted shows an
  error. Clearing history asks first and never deletes export folders; a busy or unwritable
  settings folder shows an error.

Known limitations
-----------------
The list does not refresh on its own when another window or the command line records an
  export; use Refresh.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.about_tab import create_about_tab
    from gui.state import make_gui_state

    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_about_tab(frame, make_gui_state())
    window.mainloop()
"""

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from app import AFFILIATION, APP_NAME, APP_VERSION, AUTHOR
from gui.state import GuiState
from gui.widgets import open_folder
from storage import HistoryEntry, clear_history, recent_entries


def create_about_tab(parent: tk.Frame, state: GuiState) -> None:
    about_text = tk.Label(
        parent, justify="left", anchor="nw", wraplength=760,
        text=(
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "A no-dependency utility that packages a project folder into a "
            "readable Markdown context file, JSON manifest, summary file, "
            "settings record, and optional ZIP snapshot.\n\n"
            f"Author: {AUTHOR}\n{AFFILIATION}"
        ),
    )
    about_text.pack(fill="x", padx=18, pady=(18, 8))
    history_frame = tk.LabelFrame(parent, text="Recent Exports", padx=8, pady=8)
    history_frame.pack(fill="both", expand=True, padx=16, pady=(8, 8))
    tree_container = tk.Frame(history_frame)
    tree_container.pack(fill="both", expand=True)
    history_scrollbar = tk.Scrollbar(tree_container)
    history_scrollbar.pack(side="right", fill="y")
    columns = ("created", "profile", "included", "skipped", "git", "root")
    history_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=9, yscrollcommand=history_scrollbar.set)
    history_tree.heading("created", text="Created")
    history_tree.heading("profile", text="Profile")
    history_tree.heading("included", text="Included")
    history_tree.heading("skipped", text="Skipped")
    history_tree.heading("git", text="Git")
    history_tree.heading("root", text="Project Folder")
    history_tree.column("created", width=145, anchor="w")
    history_tree.column("profile", width=65, anchor="center")
    history_tree.column("included", width=65, anchor="center")
    history_tree.column("skipped", width=65, anchor="center")
    history_tree.column("git", width=140, anchor="center")
    history_tree.column("root", width=230, anchor="w")
    history_tree.pack(side="left", fill="both", expand=True)
    history_scrollbar.config(command=history_tree.yview)
    entry_lookup: dict[str, HistoryEntry] = {}

    def format_git_cell(entry: HistoryEntry) -> str:
        if not entry.git_branch and not entry.git_commit_short:
            return ""
        branch = entry.git_branch or "(detached)"
        commit = entry.git_commit_short or ""
        return f"{branch}@{commit}" if commit else branch

    def refresh_history() -> None:
        history_tree.delete(*history_tree.get_children())
        entry_lookup.clear()
        entries = recent_entries(limit=20)
        if not entries:
            history_tree.insert("", "end", values=("No exports yet.", "", "", "", "", "Build a project context export to see it here."))
            return
        for entry in entries:
            item_id = history_tree.insert("", "end", values=(entry.created, entry.profile, entry.included_count, entry.skipped_count, format_git_cell(entry), entry.root))
            entry_lookup[item_id] = entry
    refresh_history()
    state.history_refresh = refresh_history

    def open_selected_export() -> None:
        selection = history_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select a recent export first.")
            return
        entry = entry_lookup.get(selection[0])
        if entry is None:
            return
        export_dir = Path(entry.export_dir)
        if not export_dir.exists():
            messagebox.showerror("Folder Not Found", f"This export folder no longer exists:\n{export_dir}")
            return
        open_folder(export_dir)

    def clear_export_history() -> None:
        if not messagebox.askyesno("Clear History", "Remove all recorded export history?\n\nThis only clears this list. It does not delete any actual export files or folders."):
            return
        try:
            clear_history()
        except Exception as exc:
            messagebox.showerror("Clear History Failed", str(exc))
            return
        refresh_history()
    history_buttons = tk.Frame(history_frame)
    history_buttons.pack(fill="x", pady=(8, 0))
    tk.Button(history_buttons, text="Open Selected Export Folder", command=open_selected_export).pack(side="left")
    tk.Button(history_buttons, text="Refresh", command=refresh_history).pack(side="left", padx=(8, 0))
    tk.Button(history_buttons, text="Clear History", command=clear_export_history).pack(side="left", padx=(8, 0))
