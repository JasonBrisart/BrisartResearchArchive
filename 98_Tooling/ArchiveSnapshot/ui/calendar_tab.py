"""
ui.calendar_tab
------------------

Calendar tab: browse months, see which days have snapshots, inspect a
selected date's snapshot details, and open a snapshot's generated files.
"""

from __future__ import annotations

import calendar
import datetime
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from engine.app_info import (
    DIFF_FILENAME,
    MANIFEST_FILENAME,
    PROJECT_CONTEXT_MANIFEST_FILENAME,
    PROJECT_CONTEXT_MD_FILENAME,
    PROJECT_CONTEXT_SUMMARY_FILENAME,
    SUMMARY_FILENAME,
    TREE_FILENAME,
)
from engine.project_context_import import project_context_display_text
from engine.snapshot_writer import human_bytes
from engine.snapshot_index import snapshots_by_date

from .path_actions import build_folder_picker, open_path


class CalendarTab:
    """
    The Calendar tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="Calendar")

        self.month_label: tk.Label | None = None
        self.calendar_grid: tk.Frame | None = None
        self.calendar_buttons: list[tk.Button] = []
        self.detail_text: tk.Text | None = None

        self.build()

    def build(self) -> None:
        """
        Build all widgets for the Calendar tab.
        """
        build_folder_picker(self.frame, self.app)

        nav = tk.Frame(self.frame)
        nav.pack(fill="x", padx=14, pady=(2, 8))

        tk.Button(nav, text="Previous Month", command=self.previous_month).pack(
            side="left"
        )
        tk.Button(nav, text="Today", command=self.jump_today).pack(
            side="left", padx=8
        )
        tk.Button(nav, text="Next Month", command=self.next_month).pack(side="left")

        self.month_label = tk.Label(nav, text="", font=("Segoe UI", 14, "bold"))
        self.month_label.pack(side="left", padx=24)

        tk.Button(
            nav,
            text="Create Snapshot Today",
            command=lambda: self.app.snapshot_tab.create_snapshot_from_gui(),
        ).pack(side="right")

        main = tk.Frame(self.frame)
        main.pack(fill="both", expand=True, padx=14, pady=8)

        calendar_frame = tk.LabelFrame(main, text="Archive Calendar")
        calendar_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.calendar_grid = tk.Frame(calendar_frame)
        self.calendar_grid.pack(fill="both", expand=True, padx=8, pady=8)

        right = tk.LabelFrame(
            main, text="Selected Date / Snapshot Details", width=360
        )
        right.pack(side="left", fill="both", padx=(8, 0))

        self.detail_text = tk.Text(right, height=18, wrap="word")
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=8)

        button_frame = tk.Frame(right)
        button_frame.pack(fill="x", padx=8, pady=(0, 8))

        tk.Button(
            button_frame,
            text="Open Snapshot Folder",
            command=self.open_selected_snapshot,
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open Summary",
            command=lambda: self.open_file_in_snapshot(SUMMARY_FILENAME),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open Manifest",
            command=lambda: self.open_file_in_snapshot(MANIFEST_FILENAME),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open Folder Tree",
            command=lambda: self.open_file_in_snapshot(TREE_FILENAME),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open Diff Report",
            command=lambda: self.open_file_in_snapshot(DIFF_FILENAME),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open Project Context Folder",
            command=self.open_project_context_folder,
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open PROJECT_CONTEXT.md",
            command=lambda: self.open_project_context_file(
                PROJECT_CONTEXT_MD_FILENAME
            ),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open PROJECT_SUMMARY.txt",
            command=lambda: self.open_project_context_file(
                PROJECT_CONTEXT_SUMMARY_FILENAME
            ),
        ).pack(fill="x", pady=2)

        tk.Button(
            button_frame,
            text="Open PROJECT_MANIFEST.json",
            command=lambda: self.open_project_context_file(
                PROJECT_CONTEXT_MANIFEST_FILENAME
            ),
        ).pack(fill="x", pady=2)

    def refresh(self) -> None:
        """
        Rebuild the calendar grid for the current month/year.
        """
        for widget in self.calendar_grid.winfo_children():
            widget.destroy()
        self.calendar_buttons.clear()

        month_name = calendar.month_name[self.app.current_month]
        self.month_label.config(text=f"{month_name} {self.app.current_year}")

        headers = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for col, name in enumerate(headers):
            tk.Label(
                self.calendar_grid,
                text=name,
                font=("Segoe UI", 10, "bold"),
                width=12,
                relief="ridge",
            ).grid(row=0, column=col, sticky="nsew")

        folder = self.app.selected_folder.get().strip()
        grouped = {}
        if folder:
            try:
                grouped = snapshots_by_date(Path(folder).expanduser().resolve())
            except Exception:
                grouped = {}

        cal = calendar.Calendar(firstweekday=6)
        month_days = cal.monthdatescalendar(
            self.app.current_year, self.app.current_month
        )

        for row_index, week in enumerate(month_days, start=1):
            for col_index, date_value in enumerate(week):
                date_key = date_value.strftime("%Y-%m-%d")
                in_month = date_value.month == self.app.current_month
                snapshots = grouped.get(date_key, [])

                label = str(date_value.day)
                if snapshots:
                    label += f"\n\u25cf {len(snapshots)}"

                button = tk.Button(
                    self.calendar_grid,
                    text=label,
                    height=4,
                    width=12,
                    relief="raised",
                    bg="#d9f2d9"
                    if snapshots
                    else ("#eeeeee" if in_month else "#f8f8f8"),
                    fg="black" if in_month else "#999999",
                    command=lambda key=date_key: self.select_date(key),
                )
                button.grid(
                    row=row_index, column=col_index, sticky="nsew", padx=1, pady=1
                )
                self.calendar_buttons.append(button)

        for index in range(7):
            self.calendar_grid.columnconfigure(index, weight=1)

    def select_date(self, date_key: str) -> None:
        """
        Show details for the latest snapshot on the selected date.
        """
        folder = self.app.selected_folder.get().strip()
        if not folder:
            return

        grouped = snapshots_by_date(Path(folder).expanduser().resolve())
        snapshots = grouped.get(date_key, [])

        if not snapshots:
            self.app.selected_snapshot = None
            self.show_detail(f"Selected Date: {date_key}\n\nNo snapshots found.")
            return

        self.app.selected_snapshot = snapshots[-1]

        project_context_text = "Project Context Helper bundle: none"
        if self.app.selected_snapshot.project_context_attached:
            project_context_text = project_context_display_text(
                self.app.selected_snapshot.snapshot_dir
            )

        text = (
            f"Selected Date: {date_key}\n\n"
            f"Snapshots on this date: {len(snapshots)}\n\n"
            f"Latest snapshot:\n"
            f"{self.app.selected_snapshot.snapshot_dir}\n\n"
            f"Created: {self.app.selected_snapshot.created}\n"
            f"Archive name: {self.app.selected_snapshot.archive_name}\n"
            f"Included files: {self.app.selected_snapshot.included_count}\n"
            f"Skipped files: {self.app.selected_snapshot.skipped_count}\n"
            f"Included size: "
            f"{human_bytes(self.app.selected_snapshot.included_bytes)}\n\n"
            f"{project_context_text}"
        )
        self.show_detail(text)

    def show_detail(self, text: str) -> None:
        """
        Display text in the snapshot detail panel.
        """
        if self.detail_text is None:
            return
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)

    def open_selected_snapshot(self) -> None:
        """
        Open the selected snapshot's folder.
        """
        if self.app.selected_snapshot is None:
            messagebox.showinfo(
                "No Snapshot", "Select a date with a snapshot first."
            )
            return
        open_path(self.app.selected_snapshot.snapshot_dir)

    def open_file_in_snapshot(self, filename: str) -> None:
        """
        Open one generated file from the selected snapshot.
        """
        if self.app.selected_snapshot is None:
            messagebox.showinfo(
                "No Snapshot", "Select a date with a snapshot first."
            )
            return

        path = self.app.selected_snapshot.snapshot_dir / filename
        if not path.exists():
            messagebox.showinfo("File Missing", f"File not found:\n{path}")
            return

        open_path(path)

    def open_project_context_folder(self) -> None:
        """
        Open the Project Context Helper folder attached to the selected
        snapshot.
        """
        if self.app.selected_snapshot is None:
            messagebox.showinfo(
                "No Snapshot", "Select a date with a snapshot first."
            )
            return

        if not self.app.selected_snapshot.project_context_dir:
            messagebox.showinfo(
                "No Project Context",
                "This snapshot has no Project Context Helper bundle.",
            )
            return

        open_path(self.app.selected_snapshot.project_context_dir)

    def open_project_context_file(self, filename: str) -> None:
        """
        Open one file from the Project Context Helper bundle attached to
        the selected snapshot.
        """
        if self.app.selected_snapshot is None:
            messagebox.showinfo(
                "No Snapshot", "Select a date with a snapshot first."
            )
            return

        if not self.app.selected_snapshot.project_context_dir:
            messagebox.showinfo(
                "No Project Context",
                "This snapshot has no Project Context Helper bundle.",
            )
            return

        path = self.app.selected_snapshot.project_context_dir / filename
        if not path.exists():
            messagebox.showinfo("File Missing", f"File not found:\n{path}")
            return

        open_path(path)

    def previous_month(self) -> None:
        """
        Move the calendar back one month.
        """
        self.app.current_month -= 1
        if self.app.current_month < 1:
            self.app.current_month = 12
            self.app.current_year -= 1
        self.refresh()

    def next_month(self) -> None:
        """
        Move the calendar forward one month.
        """
        self.app.current_month += 1
        if self.app.current_month > 12:
            self.app.current_month = 1
            self.app.current_year += 1
        self.refresh()

    def jump_today(self) -> None:
        """
        Jump the calendar to the current month.
        """
        today = datetime.datetime.now()
        self.app.current_year = today.year
        self.app.current_month = today.month
        self.refresh()
