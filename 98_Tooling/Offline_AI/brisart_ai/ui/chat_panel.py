r"""
File: brisart_ai/ui/chat_panel.py

Purpose
-------
Display the transcript and collect a single-line question.

The chat panel owns the visible transcript and editable question entry. It does not
store the durable topic history or calculate answers.

Public operations: ChatPanel.set_busy (self, busy); ChatPanel.append (self, text,
tag='assistant'); ChatPanel.append_user (self, text); ChatPanel.append_assistant (self,
text).

Public operations: ChatPanel.append_system (self, text); ChatPanel.focus_input (self).

Internal helpers include ChatPanel.__init__, ChatPanel._build, ChatPanel._submit.

Communication / relationships
-----------------------------
Sends a submission to the parent callback; the parent supplies reply and status
messages.

It invokes the application callback on submission and receives text and busy-state
updates from its owner.

Direct project imports: brisart_ai.ui.

Direct importing modules include brisart_ai/ui/app.py.

Concrete calls within this file include self._build, self.transcript.pack,
self.transcript.tag_configure, self.entry.pack, self.entry.bind, self.send.pack,
self.send.state, self.input_var.set, self.on_submit, self.transcript.configure,
self.transcript.insert, self.transcript.see.

Settings / parameters
---------------------
set_busy disables the Search button while leaving the draft editable.

Call signatures: ChatPanel.set_busy(self, busy); ChatPanel.append(self, text,
tag='assistant'); ChatPanel.append_user(self, text); ChatPanel.append_assistant(self,
text); ChatPanel.append_system(self, text).

Call signatures: ChatPanel.focus_input(self).

Edge cases
----------
Enter during an active search does not discard the draft.

Submitting during an active search must leave the draft intact; transcript output is not
itself the persisted research database.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
The visible transcript is a widget, not the persistent topic store.

Examples
--------
panel.append_assistant(answer)

Other callable entry points in this module include ChatPanel.append,
ChatPanel.append_user, ChatPanel.append_assistant, ChatPanel.append_system,
ChatPanel.focus_input.
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
