"""
ui.path_actions
-----------------

Shared filesystem and folder-picker actions used across ArchiveSnapshot's
GUI tabs.

This module contains no engine logic beyond calling into
engine.project_context_import to locate the Project Context Helper
inbox folder. It opens paths in the system file browser / default
application and builds the reusable "Archive Folder" picker widget
shared by the Calendar, Create Snapshot, Compare, Verify, and Settings
tabs.
"""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from engine.project_context_import import ensure_project_context_active_dir


def open_path(path: Path) -> None:
    """
    Open a path in the system file browser / default application.
    """
    try:
        os.startfile(path)
    except AttributeError:
        messagebox.showinfo("Path", str(path))
    except Exception as exc:
        messagebox.showerror("Open Failed", str(exc))


class PathActions:
    """
    Shared folder/file actions used by multiple tabs.
    """

    def __init__(self, app) -> None:
        self.app = app

    def browse_folder(self) -> None:
        """
        Prompt the user to select an archive folder, then refresh the
        Calendar tab.
        """
        folder = filedialog.askdirectory(title="Select archive folder")
        if folder:
            self.app.selected_folder.set(folder)
            self.app.calendar_tab.refresh()

    def open_selected_folder(self) -> None:
        """
        Open the currently selected archive folder.
        """
        folder = self.app.selected_folder.get().strip()
        if folder:
            open_path(Path(folder))

    def open_project_context_inbox(self) -> None:
        """
        Create (if needed) and open the Project Context Helper inbox
        folder for the selected archive folder.
        """
        folder = self.app.selected_folder.get().strip()
        if not folder:
            messagebox.showerror(
                "Missing Folder", "Select an archive folder first."
            )
            return

        root = Path(folder).expanduser().resolve()
        inbox = ensure_project_context_active_dir(root)
        open_path(inbox)


def build_folder_picker(parent: tk.Frame, app) -> tk.LabelFrame:
    """
    Build the reusable "Archive Folder" picker widget.

    Used by the Calendar, Create Snapshot, Compare, Verify, and Settings
    tabs so the folder path field and its buttons behave identically
    everywhere.
    """
    frame = tk.LabelFrame(parent, text="Archive Folder", padx=10, pady=10)
    frame.pack(fill="x", padx=14, pady=10)

    tk.Entry(frame, textvariable=app.selected_folder).pack(
        side="left", fill="x", expand=True
    )

    tk.Button(
        frame,
        text="Browse",
        command=app.path_actions.browse_folder,
    ).pack(side="left", padx=(8, 0))

    tk.Button(
        frame,
        text="Open",
        command=app.path_actions.open_selected_folder,
    ).pack(side="left", padx=(8, 0))

    tk.Button(
        frame,
        text="Refresh",
        command=lambda: app.calendar_tab.refresh(),
    ).pack(side="left", padx=(8, 0))

    tk.Button(
        frame,
        text="Open Project Context Inbox",
        command=app.path_actions.open_project_context_inbox,
    ).pack(side="left", padx=(8, 0))

    return frame
