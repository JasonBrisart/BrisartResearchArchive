r"""
File: brisart_ai/ui/chat_panel.py

Purpose
-------
Render the transcript and compose the question-entry area of the desktop.

Communication / relationships
-----------------------------
- brisart_ai/ui/app.py: constructs ChatPanel and calls append_*().
- Imports brisart_ai.ui.theme for every color/font constant used.

Settings / parameters
---------------------
- on_submit: callback invoked with stripped, non-empty input text.

Edge cases
----------
- The transcript is read-only outside append(). Drafts stay editable and
are not cleared when Enter is pressed during an active search.
- append() auto-scrolls to the bottom after every message.

Known limitations
-----------------
This header update does not establish complete behavioral, platform, or
security validation.

Examples
--------
Inspect the definitions below and the project documentation for supported
usage.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from brisart_ai.ui import theme


class ChatPanel(ttk.Frame):
    """Scrollable message transcript plus a single-line input box."""

    def __init__(self, master, on_submit):
        super().__init__(master, style="Panel.TFrame")
        self.on_submit = on_submit
        self._build()

    def _build(self) -> None:
        self.transcript = scrolledtext.ScrolledText(
            self, wrap="word", bg=theme.BG_CHAT, fg=theme.FG_TEXT,
            insertbackground=theme.FG_TEXT, font=theme.FONT_UI,
            borderwidth=0, highlightthickness=0, padx=theme.PAD, pady=theme.PAD,
            state="disabled",
        )
        self.transcript.pack(side="top", fill="both", expand=True)
        self.transcript.tag_configure("user", foreground=theme.FG_USER, font=theme.FONT_MONO_BOLD)
        self.transcript.tag_configure("assistant", foreground=theme.FG_ASSISTANT)
        self.transcript.tag_configure("system", foreground=theme.FG_SYSTEM, font=("Consolas", 9, "italic"))

        input_row = ttk.Frame(self, style="Panel.TFrame")
        input_row.pack(side="bottom", fill="x", pady=(theme.PAD_SMALL, 0))

        self.input_var = tk.StringVar()
        self.entry = tk.Entry(
            input_row, textvariable=self.input_var, bg=theme.BG_INPUT,
            fg=theme.FG_TEXT, insertbackground=theme.FG_TEXT, font=theme.FONT_UI,
            relief="flat",
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, theme.PAD_SMALL))
        self.entry.bind("<Return>", self._submit)

        self.send = ttk.Button(input_row, text="Search", command=self._submit, style="Primary.TButton")
        self.send.pack(side="right")
        self.busy = False

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send.state(["disabled" if busy else "!disabled"])

    def _submit(self, _event=None) -> str:
        text = self.input_var.get().strip()
        if not text or self.busy:
            return "break"
        self.input_var.set("")
        self.on_submit(text)
        return "break"

    def append(self, text: str, tag: str = "assistant") -> None:
        self.transcript.configure(state="normal")
        if self.transcript.index("end-1c") != "1.0":
            self.transcript.insert("end", "\n\n")
        self.transcript.insert("end", text, tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def append_user(self, text: str) -> None:
        self.append(f"You: {text}", "user")

    def append_assistant(self, text: str) -> None:
        self.append(text, "assistant")

    def append_system(self, text: str) -> None:
        self.append(text, "system")

    def focus_input(self) -> None:
        self.entry.focus_set()


__all__ = ["ChatPanel"]
