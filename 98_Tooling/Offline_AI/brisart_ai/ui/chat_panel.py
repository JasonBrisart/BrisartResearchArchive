"""
File: brisart_ai/ui/chat_panel.py

Purpose
-------
Keep the query composer above Results and Activity.

This desktop presentation component defines `ChatPanel`. Its scope is deliberately limited to
the responsibilities visible in this file rather than duplicating the application-wide
workflow. Callers use these declarations through the module interface; the file is not a
separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
The app supplies an acceptance callback and routes questions, results and diagnostics.

The direct in-project imports visible in this module are `brisart_ai.ui`. Public entry points
`set_busy`, `append`, `append_user`, `append_assistant`, `append_system`; this identifies
where behavior is invoked without implying a separate hidden dependency. Higher-level
coordination remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Enter submits; an accepted query clears the draft and selects Results.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Empty, busy and rejected submissions preserve the draft.

The behaviors documented above must be read together with the actual branches in
chat_panel.py; a caller must not infer success from an empty, rejected, or unsupported result.
Error handling, input validation, and early returns remain the responsibility of the concrete
functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
The transcript is session-only.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
panel.append_assistant(answer)

For a concrete entry point, inspect `ChatPanel`; invoke it through the existing application
entry point or its documented caller. The example above is illustrative of this file's present
interface; do not treat it as an instruction to create additional state or call private
functions directly.
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
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        tk.Label(self, text="Ask your archive", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_HEADING).grid(row=0, column=0, sticky="w", pady=(0, 4))
        row = ttk.Frame(self, style="Panel.TFrame")
        row.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        row.columnconfigure(0, weight=1)
        self.input_var = tk.StringVar(master=self)
        self.entry = tk.Entry(row, textvariable=self.input_var, bg=theme.BG_INPUT,
                              fg=theme.FG_TEXT, insertbackground=theme.FG_TEXT, font=theme.FONT_UI,
                              relief="flat", highlightthickness=1, highlightbackground=theme.BORDER,
                              highlightcolor=theme.FG_ACCENT)
        self.entry.grid(row=0, column=0, sticky="ew", ipady=7, padx=(0, 8))
        self.entry.bind("<Return>", self._submit)
        self.send = ttk.Button(row, text="Search library", command=self._submit, style="Primary.TButton")
        self.send.grid(row=0, column=1)
        self.busy = False
        self.views = ttk.Notebook(self, style="Workspace.TNotebook", takefocus=True)
        self.views.grid(row=2, column=0, sticky="nsew")
        self.transcript = self._text_tab("Results")
        self.activity_log = self._text_tab("Activity")
        self.transcript.tag_configure("user", foreground=theme.FG_USER, font=theme.FONT_UI_BOLD, spacing3=4)
        self.activity_log.tag_configure("system", foreground=theme.FG_MUTED)
        self.views.enable_traversal()
        self.append_assistant("Ask a question to find evidence in your indexed files and research notes. "
                              "Use Activity to review library changes and search diagnostics.")

    def _text_tab(self, label):
        page = ttk.Frame(self.views, style="Panel.TFrame")
        self.views.add(page, text=label)
        text = scrolledtext.ScrolledText(page, wrap="word", bg=theme.BG_CHAT, fg=theme.FG_TEXT,
            font=theme.FONT_UI, borderwidth=0, highlightthickness=1, highlightbackground=theme.BORDER,
            highlightcolor=theme.FG_ACCENT, padx=14, pady=10, height=8, width=30, state="disabled")
        text.pack(fill="both", expand=True)
        return text

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send.state(["disabled" if busy else "!disabled"])

    def _submit(self, _event=None) -> str:
        text = self.input_var.get().strip()
        if not text or self.busy:
            return "break"
        if self.on_submit(text):
            self.input_var.set("")
            self.views.select(0)
        return "break"

    def append(self, text: str, tag: str = "assistant") -> None:
        target = self.activity_log if tag == "system" else self.transcript
        target.configure(state="normal")
        try:
            if target.index("end-1c") != "1.0":
                target.insert("end", "\n\n")
            target.insert("end", text, tag)
        finally:
            target.configure(state="disabled")
        target.see("end")

    def append_user(self, text: str) -> None:
        self.append(f"You: {text}", "user")

    def append_assistant(self, text: str) -> None:
        self.append(text, "assistant")

    def append_system(self, text: str) -> None:
        self.append(text, "system")

    def focus_input(self) -> None:
        self.entry.focus_set()


__all__ = ["ChatPanel"]

