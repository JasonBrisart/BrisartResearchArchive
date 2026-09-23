"""
ui.snapshot_tab
------------------

Create Snapshot tab: archive metadata, snapshot options, size limits,
and snapshot creation.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from engine.settings import ArchiveSettings
from engine.snapshot_builder import create_snapshot
from engine.snapshot_writer import human_bytes

from .path_actions import build_folder_picker


class SnapshotTab:
    """
    The Create Snapshot tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Create Snapshot")

        self.build()

    def build(self) -> None:
        """
        Build all widgets for the Create Snapshot tab.
        """
        build_folder_picker(self.frame, self.app)

        meta = tk.LabelFrame(self.frame, text="Snapshot Metadata", padx=10, pady=10)
        meta.pack(fill="x", padx=14, pady=8)

        tk.Label(meta, text="Archive Name").grid(row=0, column=0, sticky="w", pady=4)
        tk.Entry(meta, textvariable=self.app.archive_name, width=80).grid(
            row=0, column=1, sticky="ew", pady=4
        )

        tk.Label(meta, text="Description").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(meta, textvariable=self.app.archive_description, width=80).grid(
            row=1, column=1, sticky="ew", pady=4
        )

        meta.columnconfigure(1, weight=1)

        options = tk.LabelFrame(self.frame, text="Snapshot Options", padx=10, pady=10)
        options.pack(fill="x", padx=14, pady=8)

        tk.Checkbutton(
            options, text="Create ZIP Snapshot", variable=self.app.include_zip
        ).pack(anchor="w")

        tk.Checkbutton(
            options, text="Generate SHA256 Hashes", variable=self.app.include_hashes
        ).pack(anchor="w")

        tk.Checkbutton(
            options, text="Generate Folder Tree", variable=self.app.include_tree
        ).pack(anchor="w")

        tk.Checkbutton(
            options,
            text="Generate Change Report Since Previous Snapshot",
            variable=self.app.include_diff,
        ).pack(anchor="w")

        tk.Checkbutton(
            options,
            text="Attach Project Context Helper bundle from SNAPSHOT_ACTIVE",
            variable=self.app.include_project_context,
        ).pack(anchor="w")

        limits = tk.LabelFrame(self.frame, text="Size Limits", padx=10, pady=10)
        limits.pack(fill="x", padx=14, pady=8)

        tk.Label(limits, text="Max File MB").grid(row=0, column=0, sticky="w")
        tk.Entry(limits, textvariable=self.app.max_file_mb, width=14).grid(
            row=0, column=1, sticky="w", padx=8
        )

        tk.Label(limits, text="Max Total MB").grid(row=1, column=0, sticky="w")
        tk.Entry(limits, textvariable=self.app.max_total_mb, width=14).grid(
            row=1, column=1, sticky="w", padx=8
        )

        tk.Button(
            self.frame,
            text="Create Archive Snapshot",
            command=self.create_snapshot_from_gui,
            height=2,
            width=32,
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=18)

    def settings_from_gui(self) -> ArchiveSettings:
        """
        Build ArchiveSettings from the current GUI values.
        """
        try:
            max_file_bytes = int(float(self.app.max_file_mb.get()) * 1_000_000)
        except ValueError:
            raise ValueError("Max File MB must be numeric.")

        try:
            max_total_bytes = int(float(self.app.max_total_mb.get()) * 1_000_000)
        except ValueError:
            raise ValueError("Max Total MB must be numeric.")

        return ArchiveSettings(
            archive_name=self.app.archive_name.get().strip(),
            archive_description=self.app.archive_description.get().strip(),
            include_zip_snapshot=self.app.include_zip.get(),
            include_hashes=self.app.include_hashes.get(),
            include_folder_tree=self.app.include_tree.get(),
            include_diff_report=self.app.include_diff.get(),
            include_project_context_bundle=self.app.include_project_context.get(),
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )

    def create_snapshot_from_gui(self) -> None:
        """
        Create a snapshot using the currently selected folder and
        options.
        """
        folder = self.app.selected_folder.get().strip()
        if not folder:
            messagebox.showerror("Missing Folder", "Select an archive folder first.")
            return

        try:
            self.app.settings_tab.save_settings_from_gui(show_message=False)
            self.app.status.set("Creating archive snapshot...")
            self.app.window.update_idletasks()

            result = create_snapshot(folder, settings=self.settings_from_gui())

            self.app.status.set(
                f"Snapshot complete: {result.export_dir} "
                f"({result.included_count} files, "
                f"{human_bytes(result.total_included_bytes)})"
            )

            messagebox.showinfo(
                "Snapshot Complete",
                (
                    f"Snapshot folder:\n{result.export_dir}\n\n"
                    f"Included files: {result.included_count}\n"
                    f"Skipped files: {result.skipped_count}\n"
                    f"Included size: {human_bytes(result.total_included_bytes)}"
                ),
            )

            self.app.calendar_tab.refresh()
        except Exception as exc:
            self.app.status.set(f"Snapshot failed: {exc}")
            messagebox.showerror("Snapshot Failed", str(exc))
