"""
ui.settings_tab
------------------

Settings tab: persisted GUI settings, Project Context Helper import
option, and the visible (GUI-open) daily snapshot mode.
"""

from __future__ import annotations

import datetime
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from engine.app_info import (
    DAILY_STATE_FILENAME,
    PROJECT_CONTEXT_ACTIVE_DIRNAME,
    PROJECT_CONTEXT_ACTIVE_SUBDIRNAME,
)
from engine.settings import AppSettings
from engine.snapshot_builder import create_snapshot

from .app_settings import save_app_settings
from .path_actions import build_folder_picker


class SettingsTab:
    """
    The Settings tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Settings")

        self.build()

    def build(self) -> None:
        """
        Build all widgets for the Settings tab.
        """
        build_folder_picker(self.frame, self.app)

        daily = tk.LabelFrame(
            self.frame, text="Daily Snapshot Mode", padx=10, pady=10
        )
        daily.pack(fill="x", padx=14, pady=12)

        tk.Checkbutton(
            daily,
            text="Enable daily archival snapshot while ArchiveSnapshot is open",
            variable=self.app.daily_enabled,
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=4)

        tk.Label(daily, text="Run Hour 0-23").grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(daily, textvariable=self.app.daily_hour, width=8).grid(
            row=1, column=1, sticky="w", pady=4
        )

        tk.Label(daily, text="Run Minute 0-59").grid(
            row=1, column=2, sticky="w", padx=(18, 0), pady=4
        )
        tk.Entry(daily, textvariable=self.app.daily_minute, width=8).grid(
            row=1, column=3, sticky="w", pady=4
        )

        tk.Label(
            daily,
            text=(
                "For unattended (no GUI open) daily automation, use:\n"
                "python main.py daily --init-config, then --watch or --once"
            ),
            fg="#555555",
            justify="left",
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))

        project_context_frame = tk.LabelFrame(
            self.frame,
            text="Project Context Helper Import",
            padx=10,
            pady=10,
        )
        project_context_frame.pack(fill="x", padx=14, pady=12)

        tk.Checkbutton(
            project_context_frame,
            text=(
                "Attach Project Context Helper files from SNAPSHOT_ACTIVE "
                "when creating snapshots"
            ),
            variable=self.app.include_project_context,
        ).pack(anchor="w")

        tk.Label(
            project_context_frame,
            text=(
                "Inbox folder: "
                f"{PROJECT_CONTEXT_ACTIVE_DIRNAME}/{PROJECT_CONTEXT_ACTIVE_SUBDIRNAME}"
            ),
            fg="#555555",
        ).pack(anchor="w", pady=(6, 0))

        tk.Button(
            project_context_frame,
            text="Create or Open Project Context Inbox",
            command=self.app.path_actions.open_project_context_inbox,
        ).pack(anchor="w", pady=(8, 0))

        tk.Button(
            self.frame,
            text="Save Settings",
            command=self.save_settings_from_gui,
            height=2,
            width=26,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=18, pady=10)

    def save_settings_from_gui(self, show_message: bool = True) -> None:
        """
        Persist the current GUI settings to disk.
        """
        try:
            settings = AppSettings(
                selected_archive_folder=self.app.selected_folder.get().strip(),
                archive_name=self.app.archive_name.get().strip(),
                archive_description=self.app.archive_description.get().strip(),
                daily_mode_enabled=self.app.daily_enabled.get(),
                daily_run_hour=int(self.app.daily_hour.get()),
                daily_run_minute=int(self.app.daily_minute.get()),
                include_zip_snapshot=self.app.include_zip.get(),
                include_hashes=self.app.include_hashes.get(),
                include_folder_tree=self.app.include_tree.get(),
                include_diff_report=self.app.include_diff.get(),
                include_project_context_bundle=self.app.include_project_context.get(),
                max_file_mb=float(self.app.max_file_mb.get()),
                max_total_mb=float(self.app.max_total_mb.get()),
            )

            save_app_settings(settings)
            self.app.status.set("Settings saved.")

            if show_message:
                messagebox.showinfo(
                    "Settings Saved", "ArchiveSnapshot settings saved."
                )
        except Exception as exc:
            messagebox.showerror("Save Failed", str(exc))

    def daily_check_loop(self) -> None:
        """
        Visible daily mode.

        This only works while the GUI is open. It does not install a
        hidden service. For unattended automation, use:
        python main.py daily --watch
        """
        try:
            if self.app.daily_enabled.get():
                now = datetime.datetime.now()
                hour = int(self.app.daily_hour.get())
                minute = int(self.app.daily_minute.get())

                state_path = Path.cwd() / DAILY_STATE_FILENAME
                state = {}
                if state_path.exists():
                    try:
                        state = json.loads(state_path.read_text(encoding="utf-8"))
                    except Exception:
                        state = {}

                today_key = now.strftime("%Y-%m-%d")
                last_run = state.get("last_run")

                if last_run != today_key and (
                    now.hour > hour or (now.hour == hour and now.minute >= minute)
                ):
                    folder = self.app.selected_folder.get().strip()
                    if folder:
                        create_snapshot(
                            folder,
                            settings=self.app.snapshot_tab.settings_from_gui(),
                        )
                        state["last_run"] = today_key
                        state_path.write_text(
                            json.dumps(state, indent=2), encoding="utf-8"
                        )
                        self.app.status.set(
                            f"Daily archive snapshot created for {today_key}."
                        )
                        self.app.calendar_tab.refresh()
        except Exception as exc:
            self.app.status.set(f"Daily archive check failed: {exc}")

        self.app.window.after(60000, self.daily_check_loop)
