"""
File: brisart_ai/ui/sidebar.py

Purpose
-------
Show library actions and counts in a fixed-width rail.

This desktop presentation component defines `Sidebar`. Its scope is deliberately limited to
the responsibilities visible in this file rather than duplicating the application-wide
workflow. Callers use these declarations through the module interface; the file is not a
separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
BrisartApp supplies callbacks and counts.

The direct in-project imports visible in this module are `brisart_ai.ui`,
`brisart_ai.version_info`. Public entry points `set_busy`, `set_status`; this identifies where
behavior is invoked without implying a separate hidden dependency. Higher-level coordination
remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Import is the emphasized library action.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Library mutations are disabled while search runs.

The behaviors documented above must be read together with the actual branches in sidebar.py; a
caller must not infer success from an empty, rejected, or unsupported result. Error handling,
input validation, and early returns remain the responsibility of the concrete functions in
this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Counts reflect the full local library, not the current search scope.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
sidebar.set_status(files=2, notes=1)

For a concrete entry point, inspect `Sidebar`; invoke it through the existing application
entry point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
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

        version = tk.Label(self, text=f"OFFLINE RESEARCH  /  {__version__}", bg=theme.BG_SIDEBAR, fg=theme.FG_MUTED, font=("Segoe UI", 9))
        version.pack(anchor="w", padx=theme.PAD, pady=(0, theme.PAD))

        self.buttons = {}
        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=theme.PAD, pady=10)
        tk.Label(self, text="LIBRARY", bg=theme.BG_SIDEBAR, fg=theme.FG_MUTED,
                 font=theme.FONT_UI_BOLD).pack(anchor="w", padx=theme.PAD, pady=3)
        for label, key in (("Add sources", "sources"), ("Add research note", "note"),
                           ("Manage sources", "remove")):
            self._make_button(label, key)
        self.status_var = tk.StringVar(master=self, value="Indexed: 0")
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
        for button in self.buttons.values():
            button.state(["disabled" if busy else "!disabled"])

    def set_status(self, files: int, notes: int) -> None:
        self.status_var.set(f"INDEXED LIBRARY\n{files:,} files   |   {notes:,} notes")


__all__ = ["Sidebar"]

