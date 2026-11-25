r"""
File: brisart_ai/ui/app.py

Purpose
-------
Present the offline research desktop and its local evidence actions.

Communication / relationships
-----------------------------
Calls BrisartService from the Tk event loop and worker thread.

Settings / parameters
---------------------
Add Sources, Remove Sources, Add Note, Settings and Help are the sidebar actions.

Edge cases
----------
Questions with no eligible evidence return a local-only explanation.

Known limitations
-----------------
Requires a working Tk installation and display.

Examples
--------
Run python run.py.
"""

from __future__ import annotations

import threading
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
  Remove Sources  remove selected indexed files or notes
  Add Note        save observations and optionally quote an imported source
  Settings        view/toggle research sources
  Help            show this message

Just type a question in the chat box below and press Enter.

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

        self._configure_style()
        self._build_layout()
        self._refresh_status()

        self.chat.append_system(
            f"{APP_NAME} {__version__} ready. Type a question below and "
            "press Enter -- I'll answer using your indexed files and notes."
        )
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

        self.chat = ChatPanel(body, on_submit=self._on_chat_submit)
        self.chat.pack(fill="both", expand=True)
        self.chat.focus_input()

    def _refresh_status(self) -> None:
        total, files, web = self.service.counts()
        self.sidebar.set_status(total, files, web)

    def _answer_question(self, question: str) -> None:
        question = question.strip()
        if not question or self._busy:
            return
        self._busy = True
        self.chat.append_system("Searching your imported files and notes...")

        def worker() -> None:
            try:
                answer = self.service.ask(question)
            except Exception as exc:
                answer = f"Something went wrong answering that: {exc}"
            self.after(0, self._on_answer_ready, answer)

        threading.Thread(target=worker, daemon=True).start()

    def _on_answer_ready(self, answer: str) -> None:
        self._busy = False
        if self._close_pending:
            self._on_close()
            return
        self.chat.append_assistant(answer)
        for diagnostic_line in self.service.last_diagnostics:
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

    def _action_help(self) -> None:
        self.chat.append_system(HELP_TEXT)

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
