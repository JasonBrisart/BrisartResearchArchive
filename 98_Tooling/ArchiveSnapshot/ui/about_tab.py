"""
ui.about_tab
--------------

About tab: application description and architecture overview.
"""

from __future__ import annotations

import tkinter as tk

from engine.app_info import APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_NAME


class AboutTab:
    """
    The About tab.
    """

    def __init__(self, app, notebook) -> None:
        self.app = app
        self.frame = tk.Frame(notebook)
        notebook.add(self.frame, text="About")

        self.build()

    def build(self) -> None:
        """
        Build the About tab content.
        """
        text = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "ArchiveSnapshot is a local-first calendar-based archival "
            "snapshot tool for preserving the state of important digital "
            "collections over time.\n\n"
            "It is designed to answer:\n\n"
            "What existed here on this date?\n"
            "How was it organized?\n"
            "What changed over time?\n"
            "Can the preserved files be verified?\n\n"
            "Architecture:\n\n"
            "engine/       \u2014 scanning, snapshot creation, timeline, diff, verify\n"
            "automation/   \u2014 headless daily snapshot runner (no GUI required)\n"
            "ui/           \u2014 this calendar interface\n\n"
            "How this differs from Project Context Helper:\n\n"
            "Project Context Helper explains a software project.\n"
            "ArchiveSnapshot preserves a historical record.\n\n"
            "Project Context Helper asks:\n"
            "What does this codebase look like right now?\n\n"
            "ArchiveSnapshot asks:\n"
            "What existed here on this date, and how did it change over "
            "time?\n\n"
            f"Created by {AUTHOR}\n"
            f"Part of {REPOSITORY_NAME}"
        )

        label = tk.Label(
            self.frame,
            text=text,
            justify="left",
            anchor="nw",
            wraplength=820,
        )
        label.pack(fill="both", expand=True, padx=22, pady=22)
