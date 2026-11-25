r"""
File: brisart_ai/ui/sidebar.py

Purpose
-------
Display local research actions and index status in the desktop.

Communication / relationships
-----------------------------
Receives action handlers from app.py and shows counts from the service.

Settings / parameters
---------------------
Actions are sources, remove, note, settings and help.

Edge cases
----------
Only files and notes count toward the displayed library. While searching,
mutating actions are disabled and Help remains available.

Known limitations
-----------------
The sidebar does not perform indexing or network access.

Examples
--------
Construct Sidebar(master, actions).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from brisart_ai.ui import theme
from brisart_ai.version_info import APP_NAME, __version__


class Sidebar(ttk.Frame):
    def __init__(self, master, actions: dict):
        super().__init__(master, style="Sidebar.TFrame", width=theme.SIDEBAR_WIDTH)
        self.pack_propagate(False)
        self.actions = actions
        self._build()

    def _build(self) -> None:
        title = tk.Label(self, text=APP_NAME, bg=theme.BG_SIDEBAR, fg=theme.FG_ACCENT, font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 0))

        version = tk.Label(self, text=__version__, bg=theme.BG_SIDEBAR, fg=theme.FG_MUTED, font=("Segoe UI", 9))
        version.pack(anchor="w", padx=theme.PAD, pady=(0, theme.PAD))

        self.buttons = {}
        for heading, actions in (
            ("LIBRARY", (("Add sources", "sources"), ("Add research note", "note"),
                         ("Manage sources", "remove"))),
            ("PREFERENCES", (("Search settings", "settings"), ("Help and shortcuts", "help"))),
        ):
            ttk.Separator(self, orient="horizontal").pack(fill="x", padx=theme.PAD, pady=6)
            tk.Label(self, text=heading, bg=theme.BG_SIDEBAR, fg=theme.FG_MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=theme.PAD, pady=3)
            for label, key in actions:
                self._make_button(label, key)
        self.status_var = tk.StringVar(value="Indexed: 0")
        status = tk.Label(
            self, textvariable=self.status_var, bg=theme.BG_SIDEBAR, fg=theme.FG_MUTED,
            font=("Segoe UI", 8), wraplength=theme.SIDEBAR_WIDTH - 2 * theme.PAD, justify="left",
        )
        status.pack(side="bottom", anchor="w", padx=theme.PAD, pady=theme.PAD)

    def _make_button(self, label: str, key: str) -> None:
        style = "Primary.TButton" if key == "sources" else "Navigation.TButton"
        button = ttk.Button(self, text=label, command=self.actions[key], style=style)
        button.pack(fill="x", padx=theme.PAD, pady=2)
        self.buttons[key] = button

    def set_busy(self, busy: bool) -> None:
        for key, button in self.buttons.items():
            if key != "help":
                button.state(["disabled" if busy else "!disabled"])

    def set_status(self, files: int, notes: int) -> None:
        self.status_var.set(f"OFFLINE LIBRARY\n{files:,} files   |   {notes:,} notes")


__all__ = ["Sidebar"]
