"""
File: brisart_ai/ui/app.py

Purpose
-------
Compose the offline research workspace and coordinate search and shutdown.

This desktop presentation component defines `run`, `BrisartApp`. Its scope is deliberately
limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Tk owns widget updates; BrisartService owns search and state. Workers publish results and import counts to Tk.

The direct in-project imports visible in this module are `brisart_ai.knowledge.index`,
`brisart_ai.ui`, `brisart_ai.ui.chat_panel`, `brisart_ai.ui.import_progress`,
`brisart_ai.ui.dialogs`. Public entry points `run`, `BrisartApp`; this identifies where
behavior is invoked without implying a separate hidden dependency. Higher-level coordination
remains with the calling layer rather than being introduced here.

Settings / parameters
---------------------
Scope and elapsed time stay visible during search. Ctrl+L focuses the query and F1 opens Help.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Focus stays with modal dialogs; a close request during import cancels only the import.

The behaviors documented above must be read together with the actual branches in app.py; a
caller must not infer success from an empty, rejected, or unsupported result. Error handling,
input validation, and early returns remain the responsibility of the concrete functions in
this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Search is not cancellable. Confirmed import cancellation stops after the selected file and keeps the app open.
An import thread owns service access until completion; Tk polls its progress.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
run(db_path)

For a concrete entry point, inspect `run`, `BrisartApp`; invoke it through the existing
application entry point or its documented caller. The example above is illustrative of this
file's present interface; do not treat it as an instruction to create additional state or call
private functions directly.
"""

from __future__ import annotations

from collections import deque
import threading
from time import monotonic
from queue import Empty, SimpleQueue
import tkinter as tk
from tkinter import messagebox, ttk

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui import theme
from brisart_ai.ui.chat_panel import ChatPanel
from brisart_ai.ui.import_progress import elapsed_label
from brisart_ai.ui.dialogs import AddSourcesDialog, RemoveSourcesDialog, SettingsDialog, SourceNoteDialog
from brisart_ai.core.service import BrisartService
from brisart_ai.ui.sidebar import Sidebar
from brisart_ai.version_info import APP_NAME, __version__

HELP_TEXT = """BrisartAI Help
--------------
Library actions (left sidebar):
  Add Sources     drop or browse for files and folders to index
  Manage sources  remove selected indexed files or notes
  Add Note        save observations and optionally quote an imported source
  Settings        view/toggle research sources (workspace header)
  Activity        review imports, saved notes and diagnostics

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
        self.geometry("1080x700")
        self.minsize(800, 490)
        self.configure(bg=theme.BG_APP)
        self._busy = False
        self._close_pending = False
        self._import_stop = None
        self._import_dialog = None
        self._confirming_cancel = False
        self._answers = SimpleQueue()

        self._configure_style()
        self._build_layout()
        self._refresh_status()

        self.chat.append_system(f"{APP_NAME} {__version__} ready.")
        self.bind("<F1>", self._action_help)
        self.bind("<Control-l>", self._focus_query)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background=theme.BG_PANEL)
        style.configure("Sidebar.TFrame", background=theme.BG_SIDEBAR)
        style.configure("Workspace.TNotebook", background=theme.BG_PANEL, borderwidth=0)
        style.configure("Workspace.TNotebook.Tab", padding=(13, 6), font=theme.FONT_UI_BOLD)
        style.map("Workspace.TNotebook.Tab",
                  background=[("selected", theme.BG_CHAT), ("!selected", theme.BG_PANEL)],
                  foreground=[("selected", theme.FG_TEXT), ("!selected", theme.FG_MUTED)])
        style.configure("Import.Horizontal.TProgressbar", background=theme.FG_ACCENT,
                        troughcolor=theme.BG_INPUT)
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
        }
        self.sidebar = Sidebar(self, actions)
        self.sidebar.pack(side="left", fill="y")
        body = ttk.Frame(self, style="Panel.TFrame", padding=16)
        body.pack(side="right", fill="both", expand=True, padx=theme.PAD, pady=theme.PAD)
        header = ttk.Frame(body, style="Panel.TFrame")
        header.pack(fill="x")
        self.settings_button = ttk.Button(header, text="Search settings", command=self._action_settings,
                                          style="Navigation.TButton")
        self.settings_button.pack(side="right", padx=(6, 0))
        ttk.Button(header, text="Help", command=self._action_help,
                   style="Navigation.TButton").pack(side="right")
        tk.Label(header, text="Research workspace", bg=theme.BG_PANEL, fg=theme.FG_TEXT,
                 font=theme.FONT_TITLE).pack(side="left")

        self.scope = tk.StringVar(master=self)
        scope_row = tk.Frame(body, bg=theme.BG_INPUT)
        scope_row.pack(fill="x", pady=(10, 12))
        tk.Label(scope_row, text="SEARCH SCOPE", bg=theme.BG_INPUT, fg=theme.FG_ACCENT,
                 font=theme.FONT_UI_BOLD).pack(side="left", padx=10, pady=6)
        tk.Label(scope_row, textvariable=self.scope, bg=theme.BG_INPUT, fg=theme.FG_TEXT,
                 font=theme.FONT_UI).pack(side="left", pady=6)
        self.activity = tk.StringVar(master=self)
        tk.Label(body, textvariable=self.activity, bg=theme.BG_PANEL, fg=theme.FG_MUTED,
                 font=theme.FONT_UI, anchor="w").pack(side="bottom", fill="x", pady=(7, 0))
        self.chat = ChatPanel(body, on_submit=self._on_chat_submit)
        self.chat.pack(fill="both", expand=True)
        self.after_idle(self._focus_query)

    def _focus_query(self, _event=None):
        if self.grab_current() is None and not self._close_pending:
            self.chat.focus_input()
        return "break"

    def _refresh_status(self) -> None:
        total, files, web = self.service.counts()
        notes = total - files - web
        self.sidebar.set_status(files, notes)
        enabled = [(label, count) for key, label, count in (
            ("search_local_files", "Local files", files),
            ("search_notes", "Research notes", notes),
        ) if self.service.settings.get(key)]
        self.scope.set(" + ".join(label for label, _ in enabled) or "Off: enable sources in Search settings")
        if not enabled:
            self.activity.set("No source types enabled.")
        elif not any(count for _, count in enabled):
            self.activity.set("No indexed items in scope. Add sources or change your scope.")
        else:
            self.activity.set("Ready")

    def _answer_question(self, question: str) -> bool:
        question = question.strip()
        if not question or self._busy:
            return False
        self._busy = True
        self.sidebar.set_busy(True)
        self.chat.set_busy(True)
        self.settings_button.state(["disabled"])
        self._search_started = monotonic()
        self.activity.set("Searching the offline library...  |  Elapsed 0:00")

        def worker() -> None:
            try:
                result = (self.service.ask(question), tuple(self.service.last_diagnostics))
            except Exception as exc:
                result = (f"Could not search the local library: {exc}", ())
            self._answers.put(result)

        try:
            threading.Thread(target=worker, daemon=True).start()
        except RuntimeError:
            self._on_answer_ready("Could not start search. Your draft is still available.", ())
            return False
        self.chat.append_user(question)
        self.after(40, self._poll_answer)
        return True

    def _poll_answer(self):
        try:
            answer, diagnostics = self._answers.get_nowait()
        except Empty:
            if not self._close_pending:
                elapsed = elapsed_label(monotonic() - self._search_started)
                self.activity.set(f"Searching the offline library...  |  Elapsed {elapsed}")
            self.after(100, self._poll_answer)
        else:
            self._on_answer_ready(answer, diagnostics)

    def _on_answer_ready(self, answer: str, diagnostics) -> None:
        self._busy = False
        if self._close_pending:
            self._on_close()
            return
        self.sidebar.set_busy(False)
        self.settings_button.state(["!disabled"])
        self.chat.set_busy(False)
        self.chat.append_assistant(answer)
        for diagnostic_line in diagnostics:
            self.chat.append_system(diagnostic_line)
        self._refresh_status()

    def _on_chat_submit(self, text: str) -> bool:
        if not text.strip() or self._close_pending:
            return False
        return self._answer_question(text)

    def _ready_for_changes(self) -> bool:
        return not self._busy and self.grab_current() is None

    def _import_selected(self, paths, dialog) -> None:
        latest = deque(maxlen=1)
        outcome = SimpleQueue()
        stop = threading.Event()
        self._import_stop = stop
        self._import_dialog = dialog
        self._busy = True
        self.sidebar.set_busy(True)
        self.chat.set_busy(True)
        self.settings_button.state(["disabled"])
        self.activity.set("Importing local sources...")

        discovered_at = None

        def publish(processed, total, indexed):
            nonlocal discovered_at
            if discovered_at is None:
                discovered_at = monotonic()
            latest.append((processed, total, indexed, discovered_at))

        def worker():
            try:
                result = self.service.import_paths(paths, on_progress=publish, should_stop=stop.is_set)
            except Exception as exc:
                outcome.put((False, str(exc), False))
            else:
                outcome.put((True, result, stop.is_set()))

        def poll():
            try:
                finished = outcome.get_nowait()
            except Empty:
                finished = None
            try:
                snapshot = latest.popleft()
            except IndexError:
                snapshot = None
            dialog.update_import(snapshot)
            if finished is None:
                self.after(125, poll)
                return
            self._busy = False
            self._import_stop = None
            self._import_dialog = None
            if self._close_pending:
                self._on_close()
                return
            self.sidebar.set_busy(False)
            self.chat.set_busy(False)
            self.settings_button.state(["!disabled"])
            ok, result, cancelled = finished
            self.chat.append_system(f"Import stopped. {result}" if cancelled else
                                    result if ok else f"Import failed: {result}")
            dialog.finish_import(ok, result, cancelled=cancelled)
            self._refresh_status()
            if cancelled:
                self.activity.set("Import stopped. Indexed files were kept.")

        try:
            threading.Thread(target=worker, daemon=False).start()
        except RuntimeError as exc:
            outcome.put((False, f"Could not start import: {exc}", False))
        self.after(0, poll)

    def _action_sources(self) -> None:
        if self._ready_for_changes():
            AddSourcesDialog(self, self._import_selected, self._request_import_cancel)

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

    def _request_import_cancel(self) -> None:
        stop = self._import_stop
        dialog = self._import_dialog
        if stop is None or dialog is None or stop.is_set() or self._confirming_cancel:
            return
        self._confirming_cancel = True
        try:
            confirmed = messagebox.askyesno(
                "Cancel import?",
                "The current file will finish indexing, if one is in progress. "
                "The rest of the import will be canceled. Files already indexed will be kept. "
                "BrisartAI will stay open.\n\nCancel this import?",
                default=messagebox.NO, parent=dialog,
            )
        finally:
            self._confirming_cancel = False
        # A modal prompt can process Tk callbacks while it is open.
        if confirmed and self._import_stop is stop:
            stop.set()
            dialog.show_stopping()
            self.activity.set("Stopping import safely. Waiting for the current file and workers...")

    def _on_close(self) -> None:
        if self._import_stop is not None:
            self._request_import_cancel()
            return
        if self._busy:
            if not self._close_pending:
                self._close_pending = True
                self.activity.set("Closing after the current operation finishes...")
            return
        try:
            self.service.close()
        finally:
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
