"""
ui.app
--------

Main ArchiveSnapshot GUI application: window setup, shared state, and
tab coordination.

All archival logic lives in the engine package. This module and its
sibling tab modules contain only presentation logic.
"""

from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk

from engine.app_info import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_NAME,
)
from engine.settings import StoredSnapshot

from .about_tab import AboutTab
from .app_settings import load_app_settings
from .calendar_tab import CalendarTab
from .comparison_tab import ComparisonTab
from .path_actions import PathActions
from .settings_tab import SettingsTab
from .snapshot_tab import SnapshotTab
from .verification_tab import VerificationTab


class ArchiveSnapshotApp:
    """
    ArchiveSnapshot's main Tkinter application.
    """

    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title(f"{APP_NAME} v{APP_VERSION}")
        self.window.geometry("1040x760")
        self.window.minsize(920, 680)

        loaded = load_app_settings()

        self.selected_folder = tk.StringVar(value=loaded.selected_archive_folder)
        self.archive_name = tk.StringVar(value=loaded.archive_name)
        self.archive_description = tk.StringVar(value=loaded.archive_description)

        self.include_zip = tk.BooleanVar(value=loaded.include_zip_snapshot)
        self.include_hashes = tk.BooleanVar(value=loaded.include_hashes)
        self.include_tree = tk.BooleanVar(value=loaded.include_folder_tree)
        self.include_diff = tk.BooleanVar(value=loaded.include_diff_report)
        self.include_project_context = tk.BooleanVar(
            value=loaded.include_project_context_bundle
        )

        self.max_file_mb = tk.StringVar(value=str(loaded.max_file_mb))
        self.max_total_mb = tk.StringVar(value=str(loaded.max_total_mb))

        self.daily_enabled = tk.BooleanVar(value=loaded.daily_mode_enabled)
        self.daily_hour = tk.StringVar(value=str(loaded.daily_run_hour))
        self.daily_minute = tk.StringVar(value=str(loaded.daily_run_minute))

        self.status = tk.StringVar(value="Select an archive folder.")
        self.selected_snapshot: StoredSnapshot | None = None

        today = datetime.datetime.now()
        self.current_year = today.year
        self.current_month = today.month

        self.path_actions = PathActions(self)

        self.build_ui()
        self.calendar_tab.refresh()
        self.window.after(60000, self.settings_tab.daily_check_loop)

    def build_ui(self) -> None:
        """
        Build the window header, notebook, tabs, and status bar.
        """
        header = tk.Label(
            self.window,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=("Segoe UI", 20, "bold"),
        )
        header.pack(pady=(14, 2))

        subtitle = tk.Label(
            self.window,
            text=(
                f"{APP_TAGLINE}\n"
                f"Created by {AUTHOR} \u2022 Part of {REPOSITORY_NAME}"
            ),
            justify="center",
            fg="#555555",
        )
        subtitle.pack(pady=(0, 10))

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 8))

        # The Calendar tab is built first: build_folder_picker() on every
        # other tab defers its "Refresh" button to self.calendar_tab, so
        # this attribute must exist before the remaining tabs are built.
        self.calendar_tab = CalendarTab(self, notebook)
        self.snapshot_tab = SnapshotTab(self, notebook)
        self.comparison_tab = ComparisonTab(self, notebook)
        self.verification_tab = VerificationTab(self, notebook)
        self.settings_tab = SettingsTab(self, notebook)
        self.about_tab = AboutTab(self, notebook)

        status_bar = tk.Label(
            self.window,
            textvariable=self.status,
            anchor="w",
            relief="sunken",
            padx=8,
        )
        status_bar.pack(side="bottom", fill="x")

    def run(self) -> None:
        """
        Start the Tkinter main loop.
        """
        self.window.mainloop()


def run_gui() -> None:
    """
    Launch the ArchiveSnapshot GUI.
    """
    app = ArchiveSnapshotApp()
    app.run()
