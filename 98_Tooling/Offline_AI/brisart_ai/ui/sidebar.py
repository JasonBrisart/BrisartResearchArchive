r"""
File: brisart_ai/ui/sidebar.py

Purpose
-------
Display Library and Preferences controls and offline library counts.

The sidebar is the desktop navigation owner. It groups library actions and preferences
without duplicating the application service.

Public operations: Sidebar.set_busy (self, busy); Sidebar.set_status (self, files,
notes).

Internal helpers include Sidebar.__init__, Sidebar._build, Sidebar._make_button.

Communication / relationships
-----------------------------
The desktop supplies named action callbacks; theme defines presentation constants.

Action keys map to callbacks supplied by app.py. Counts and busy state are presentation
inputs, not independent queries into SQLite.

Direct project imports: brisart_ai.ui, brisart_ai.version_info.

Direct importing modules include brisart_ai/ui/app.py.

Concrete calls within this file include self.pack_propagate, self._build,
self.buttons.items, self.status_var.set, self._make_button.

Settings / parameters
---------------------
set_status displays file and note counts; set_busy disables mutations and settings.

Call signatures: Sidebar.set_busy(self, busy); Sidebar.set_status(self, files, notes).

Edge cases
----------
Help remains available while search is busy.

Help remains available while source-mutating controls are disabled. Displayed counts
describe stored local files and notes, not guaranteed relevant matches.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
Counts are stored sources, not the number eligible for a particular question.

Examples
--------
sidebar.set_status(files=3, notes=2)

Other callable entry points in this module include Sidebar.set_status.
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
