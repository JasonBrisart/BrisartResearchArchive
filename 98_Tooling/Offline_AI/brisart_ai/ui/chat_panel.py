"""
File: brisart_ai/ui/chat_panel.py

Purpose
-------
Keep the query composer above Results and Activity.

Communication / relationships
-----------------------------
The app supplies an acceptance callback and routes questions, results and diagnostics.

Settings / parameters
---------------------
Enter submits; an accepted query clears the draft and selects Results.

Edge cases
----------
Empty, busy and rejected submissions preserve the draft.

Known limitations
-----------------
The transcript is session-only.

Examples
--------
panel.append_assistant(answer)
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
