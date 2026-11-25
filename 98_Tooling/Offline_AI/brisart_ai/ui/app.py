r"""
File: brisart_ai/ui/app.py

Purpose
-------
Own the Tk workspace, search worker and application lifetime.

The Tk application owns layout, action routing, search-worker lifetime and the
active-source status shown to the user. It does not own retrieval algorithms or SQLite
schema.

Public operations: run (db_path=DEFAULT_DB).

Internal helpers include BrisartApp.__init__, BrisartApp._configure_style,
BrisartApp._build_layout, BrisartApp._refresh_status, BrisartApp._answer_question,
BrisartApp._poll_answer, BrisartApp._on_answer_ready, BrisartApp._on_chat_submit,
BrisartApp._ready_for_changes, BrisartApp._import_selected, BrisartApp._action_sources,
BrisartApp._action_remove, and 6 additional local helpers.

Communication / relationships
-----------------------------
Delegates research to BrisartService and composes the sidebar, transcript and dialogs.

The search worker returns a result through a queue; only the Tk event loop updates
widgets. Mutating actions are disabled while a query runs and closing waits for the
outstanding operation.

Direct project imports: brisart_ai.knowledge.index, brisart_ai.ui,
brisart_ai.ui.chat_panel, brisart_ai.ui.dialogs, brisart_ai.core.service,
brisart_ai.ui.sidebar, brisart_ai.version_info.

Direct importing modules include run.py.

Concrete calls within this file include messagebox.showerror, self.title, self.geometry,
self.minsize, self.configure, self._configure_style, self._build_layout,
self._refresh_status, self.chat.append_system, self.bind, self.protocol,
self.sidebar.pack.

Settings / parameters
---------------------
Shows active source scope; F1 opens Help and Ctrl+L focuses the question field.

Module configuration and named constants: HELP_TEXT='BrisartAI
Help\n--------------\nCore actions (left sidebar):\n Add Sources drop or browse for
files and folders to index\n Manage sources remove selected indexed files or notes\n Add
Note save observations and optionally quote an imported source\n Settings view/toggle
research sources\n Help show this message\n\nEnter submits a question. Ctrl+L focuses
the question field. F1 opens Help.\n\nBrisartAI answers from your imported files and
research notes.'.

Call signatures: run(db_path=DEFAULT_DB).

Edge cases
----------
Receives worker results through a queue on the Tk thread and defers closure while search
is busy.

The desktop requires Tk and a display. A queued answer is distinct from a submitted
draft; a second Enter during a search must not discard the user’s text.

Explicit exception branches or raised errors in this file include Exception,
tk.TclError, RuntimeError, Empty.

Known limitations
-----------------
Requires Tk and a live display. This module does not rank documents.

Examples
--------
python run.py
"""

from __future__ import annotations

import threading
from queue import Empty, SimpleQueue
import tkinter as tk
from tkinter import messagebox, ttk

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui import theme
from brisart_ai.ui.chat_panel import ChatPanel
from brisart_ai.ui.dialogs import AddSourcesDialog, RemoveSourcesDialog, SettingsDialog, SourceNoteDialog
from brisart_ai.core.service import BrisartService
from brisart_ai.ui.sidebar import Sidebar
from brisart_ai.version_info import APP_NAME, __version__

HELP_TEXT = """BrisartAI Help
--------------
Core actions (left sidebar):
  Add Sources     drop or browse for files and folders to index
  Manage sources  remove selected indexed files or notes
  Add Note        save observations and optionally quote an imported source
  Settings        view/toggle research sources
  Help            show this message

Enter submits a question. Ctrl+L focuses the question field. F1 opens Help.

BrisartAI answers from your imported files and research notes."""


class BrisartApp(tk.Tk):
    def __init__(self, db_path: str = DEFAULT_DB):
        super().__init__()
        try:
            self.service = BrisartService(db_path)
        except Exception:
            self.destroy()
            raise
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("980x640")
        self.minsize(760, 480)
        self.configure(bg=theme.BG_APP)
        self._busy = False
        self._close_pending = False
        self._answers = SimpleQueue()

        self._configure_style()
        self._build_layout()
        self._refresh_status()

        self.chat.append_system(
            f"{APP_NAME} {__version__} ready. Type a question below and "
            "press Enter -- I'll answer using your indexed files and notes."
        )
        self.bind("<F1>", self._action_help)
        self.bind("<Control-l>", lambda _event: self.chat.focus_input())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background=theme.BG_PANEL)
        style.configure("Sidebar.TFrame", background=theme.BG_SIDEBAR)
        style.configure("TSeparator", background=theme.BORDER)
        style.configure("Navigation.TButton", anchor="w", padding=(11, 7),
                        background=theme.BG_INPUT, foreground=theme.FG_TEXT)
        style.configure("Primary.TButton", padding=(11, 7), font=theme.FONT_UI_BOLD,
                        background=theme.FG_ACCENT, foreground=theme.BG_CHAT)
        for name in ("Navigation.TButton", "Primary.TButton"):
            style.map(name, background=[("disabled", theme.BG_PANEL), ("pressed", theme.FG_ACCENT_DIM),
                                       ("active", theme.FG_USER)],
                      foreground=[("disabled", theme.FG_MUTED), ("active", theme.BG_CHAT)])

    def _build_layout(self) -> None:
        actions = {
            "sources": self._action_sources,
            "remove": self._action_remove, "note": self._action_note,
            "settings": self._action_settings,
            "help": self._action_help,
        }
        self.sidebar = Sidebar(self, actions)
        self.sidebar.pack(side="left", fill="y")

        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(side="right", fill="both", expand=True, padx=theme.PAD, pady=theme.PAD)

        tk.Label(body, text="Research workspace", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_HEADING).pack(anchor="w", padx=8, pady=(8, 2))
        self.scope = tk.StringVar(master=self)
        tk.Label(body, textvariable=self.scope, bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                 font=theme.FONT_UI).pack(anchor="w", padx=8, pady=(0, 8))
        self.chat = ChatPanel(body, on_submit=self._on_chat_submit)
        self.chat.pack(fill="both", expand=True)
        self.chat.focus_input()

    def _refresh_status(self) -> None:
        total, files, web = self.service.counts()
        self.sidebar.set_status(files, total - files - web)
        active = [label for key, label in (("search_local_files", "local files"),
                  ("search_notes", "research notes")) if self.service.settings.get(key)]
        self.scope.set("Searching: " + " + ".join(active) if active else "Search is off. Enable sources in Search settings.")

    def _answer_question(self, question: str) -> None:
        question = question.strip()
        if not question or self._busy:
            return
        self._busy = True
        self.sidebar.set_busy(True)
        self.chat.set_busy(True)
        self.scope.set("Searching the offline library...")

        def worker() -> None:
            try:
                result = (self.service.ask(question), tuple(self.service.last_diagnostics))
            except Exception as exc:
                result = (f"Could not search the local library: {exc}", ())
            self._answers.put(result)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError:
            self._on_answer_ready("Could not start search. Try again.", ())
        else:
            self.after(40, self._poll_answer)

    def _poll_answer(self):
        try:
            answer, diagnostics = self._answers.get_nowait()
        except Empty:
            self.after(40, self._poll_answer)
        else:
            self._on_answer_ready(answer, diagnostics)

    def _on_answer_ready(self, answer: str, diagnostics) -> None:
        self._busy = False
        if self._close_pending:
            self._on_close()
            return
        self.sidebar.set_busy(False)
        self.chat.set_busy(False)
        self.chat.append_assistant(answer)
        for diagnostic_line in diagnostics:
            self.chat.append_system(diagnostic_line)
        self._refresh_status()

    def _on_chat_submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._busy:
            self.chat.append_system("Wait for the current answer before sending another question.")
            return
        self.chat.append_user(text)
        self._answer_question(text)

    def _ready_for_changes(self) -> bool:
        if self._busy:
            messagebox.showinfo("BrisartAI", "Wait for the current answer first.", parent=self)
            return False
        return True

    def _import_selected(self, paths, parent) -> bool:
        try:
            result = self.service.import_paths(paths)
        except Exception as exc:
            messagebox.showerror("Import Sources", str(exc), parent=parent)
            return False
        self.chat.append_system(result)
        self._refresh_status()
        return True

    def _action_sources(self) -> None:
        if self._ready_for_changes():
            AddSourcesDialog(self, self._import_selected)

    def _action_remove(self) -> None:
        if self._ready_for_changes():
            RemoveSourcesDialog(self, self.service, on_change=self._refresh_status)

    def _action_note(self) -> None:
        if self._ready_for_changes():
            SourceNoteDialog(self, self.service, self._on_note_saved)

    def _on_note_saved(self, result: str) -> None:
        self.chat.append_system(result)
        self._refresh_status()

    def _action_settings(self) -> None:
        if not self._ready_for_changes():
            return
        SettingsDialog(self, self.service, on_change=self._refresh_status)

    def _action_help(self, _event=None) -> None:
        if not self.grab_current():
            messagebox.showinfo("Help and shortcuts", HELP_TEXT, parent=self)

    def _on_close(self) -> None:
        if self._busy:
            self._close_pending = True
            return
        self.service.close()
        self.destroy()


def _show_startup_error(exc: Exception) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        f"{APP_NAME} could not start",
        "BrisartAI could not open its local database.\n\n"
        f"Details: {exc}\n\n"
        "This usually means the index file is locked by another running "
        "copy of BrisartAI, the folder that holds BrisartAI's saved data "
        "is read-only, or file permissions are blocking access. Close any "
        "other running copies of BrisartAI, confirm you can write to that "
        "folder, and try again.",
    )
    root.destroy()


def run(db_path: str = DEFAULT_DB) -> None:
    try:
        app = BrisartApp(db_path)
    except Exception as exc:
        _show_startup_error(exc)
        return
    app.mainloop()


__all__ = ["BrisartApp", "run"]
