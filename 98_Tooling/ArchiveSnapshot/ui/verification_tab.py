"""
ui.verification_tab
-----------------------

Verify tab: check the newest snapshot's recorded files against the
current state of the source folder.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from engine.integrity_check import build_verify_report, verify_snapshot_against_source
from engine.snapshot_index import discover_snapshots

from .path_actions import build_folder_picker


class VerificationTab:
    """
    The Verify tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Verify")

        self.verify_text: tk.Text | None = None

        self.build()

    def build(self) -> None:
        """
        Build all widgets for the Verify tab.
        """
        build_folder_picker(self.frame, self.app)

        tk.Label(
            self.frame,
            text="Verify the latest snapshot against the current folder state.",
        ).pack(anchor="w", padx=18, pady=12)

        tk.Button(
            self.frame,
            text="Verify Latest Snapshot",
            command=self.verify_latest_snapshot,
            height=2,
            width=32,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=8)

        self.verify_text = tk.Text(self.frame, wrap="word")
        self.verify_text.pack(fill="both", expand=True, padx=18, pady=12)

    def verify_latest_snapshot(self) -> None:
        """
        Verify the newest discovered snapshot against its source folder.
        """
        folder = self.app.selected_folder.get().strip()
        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        root = Path(folder).expanduser().resolve()
        snapshots = discover_snapshots(root)

        if not snapshots:
            messagebox.showinfo("No Snapshots", "No snapshots found.")
            return

        latest = snapshots[-1]

        try:
            result = verify_snapshot_against_source(latest.snapshot_dir, root)
            text = build_verify_report(result)
            self.verify_text.delete("1.0", tk.END)
            self.verify_text.insert("1.0", text)
        except Exception as exc:
            messagebox.showerror("Verify Failed", str(exc))
