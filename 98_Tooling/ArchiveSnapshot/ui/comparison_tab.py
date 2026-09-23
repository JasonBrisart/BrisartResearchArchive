"""
ui.comparison_tab
--------------------

Compare tab: diff the two most recent snapshots in the selected archive
folder.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from engine.change_report import build_diff_markdown, compare_snapshot_dirs
from engine.snapshot_index import discover_snapshots

from .path_actions import build_folder_picker


class ComparisonTab:
    """
    The Compare tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Compare")

        self.compare_text: tk.Text | None = None

        self.build()

    def build(self) -> None:
        """
        Build all widgets for the Compare tab.
        """
        build_folder_picker(self.frame, self.app)

        info = tk.Label(
            self.frame,
            text="Compare the two latest snapshots in the selected archive folder.",
            justify="left",
        )
        info.pack(anchor="w", padx=18, pady=12)

        tk.Button(
            self.frame,
            text="Compare Two Latest Snapshots",
            command=self.compare_latest_two,
            height=2,
            width=32,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=8)

        self.compare_text = tk.Text(self.frame, wrap="word")
        self.compare_text.pack(fill="both", expand=True, padx=18, pady=12)

    def compare_latest_two(self) -> None:
        """
        Compare the two newest discovered snapshots.
        """
        folder = self.app.selected_folder.get().strip()
        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        snapshots = discover_snapshots(Path(folder).expanduser().resolve())
        if len(snapshots) < 2:
            messagebox.showinfo(
                "Not Enough Snapshots", "At least two snapshots are required."
            )
            return

        old_snapshot = snapshots[-2]
        new_snapshot = snapshots[-1]

        try:
            diff = compare_snapshot_dirs(
                old_snapshot.snapshot_dir, new_snapshot.snapshot_dir
            )
            text = build_diff_markdown(diff)
            self.compare_text.delete("1.0", tk.END)
            self.compare_text.insert("1.0", text)
        except Exception as exc:
            messagebox.showerror("Compare Failed", str(exc))
