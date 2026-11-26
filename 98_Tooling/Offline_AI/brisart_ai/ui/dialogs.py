"""
File: brisart_ai/ui/dialogs.py

Purpose
-------
The Add Sources dialog presents file-count progress, elapsed time and a throughput-based ETA and a confirmed import-only cancellation with a separate stopping display.

Own import queues, source management, note composition and settings controls.

The dialogs own human-facing import queues, source removal, note annotation and settings
editing. Their responsibility is collecting valid input and confirmation, not directly
implementing indexing.

Public operations: ask_import_paths (master, kind) - Choose multiple files or one folder
explicitly; never open two pickers; AddSourcesDialog.destroy (self).

Internal helpers include RemoveSourcesDialog.__init__, RemoveSourcesDialog._refresh,
RemoveSourcesDialog._select_all, RemoveSourcesDialog._remove, AddSourcesDialog.__init__,
AddSourcesDialog._browse, AddSourcesDialog._enqueue, AddSourcesDialog._poll_drop,
AddSourcesDialog._unqueue, AddSourcesDialog._import, SourceNoteDialog.__init__,
SourceNoteDialog._field, and 10 additional local helpers.

Communication / relationships
-----------------------------
Calls the service for source previews and changes; adds the Explorer bridge only on
Windows.

The import dialog uses the reader registry and delegates to the service. Source-note
selection previews indexed text and validates the saved excerpt. Settings errors are
reflected back into the checkbox state.

Direct project imports: brisart_ai.core.settings, brisart_ai.io.readers,
brisart_ai.knowledge.index, brisart_ai.ui.

Direct importing modules include brisart_ai/ui/app.py.

Concrete calls within this file include filedialog.askdirectory, self.title,
self.transient, self.geometry, self.minsize, self.configure, self.query.trace_add,
self.tree.configure, self.tree.pack, self.tree.bind, self._refresh, self.bind.

Settings / parameters
---------------------
Browse uses the supported-file registry; the removal table filters title, path and type.

Call signatures: ask_import_paths(master, kind); AddSourcesDialog.destroy(self).

Edge cases
----------
Failed settings writes restore the checkbox; note excerpts remain separately stored.

Explorer drag-and-drop is optional and Windows-specific; Browse remains available.
Cancelled dialogs and failed writes must not claim to have changed application data.

Explicit exception branches or raised errors in this file include ValueError, Exception,
OSError.

Known limitations
-----------------
Browse is the fallback where Windows drop is unavailable. Removing an indexed file never
deletes the disk original.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
AddSourcesDialog(parent, on_import, on_cancel_import)

Other callable entry points in this module include AddSourcesDialog.destroy.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from time import monotonic
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from brisart_ai.core.settings import TOGGLE_LABELS
from brisart_ai.io.readers import SUPPORTED_EXTENSIONS, SUPPORTED_EXTENSIONLESS_NAMES, is_supported
from brisart_ai.knowledge.index import filter_source_rows
from brisart_ai.ui import theme
from brisart_ai.ui.import_progress import elapsed_label, progress_text


def ask_import_paths(master, kind: str) -> list[str]:
    """Choose multiple files or one folder explicitly; never open two pickers."""
    if kind == "files":
        return list(filedialog.askopenfilenames(
            parent=master, title="Choose supported files to import",
            filetypes=[("Supported documents", tuple("*" + ext for ext in sorted(SUPPORTED_EXTENSIONS))
                        + tuple(sorted(SUPPORTED_EXTENSIONLESS_NAMES))),
                       ("All files", "*.*")]))
    if kind == "folder":
        folder = filedialog.askdirectory(parent=master, title="Choose a folder to import")
        return [folder] if folder else []
    raise ValueError(f"Unknown import kind: {kind}")


class RemoveSourcesDialog(tk.Toplevel):
    """List indexed files and notes and remove selected entries after confirmation."""

    def __init__(self, master, service, on_change=None):
        super().__init__(master)
        self.title("Manage Sources")
        self.transient(master)
        self.geometry("760x420")
        self.minsize(520, 300)
        self.configure(bg=theme.BG_PANEL)
        self.service = service
        self.on_change = on_change
        self.query = tk.StringVar()
        search = tk.Frame(self, bg=theme.BG_PANEL)
        search.pack(fill="x", padx=theme.PAD, pady=(theme.PAD, 0))
        tk.Label(search, text="Search sources:", bg=theme.BG_PANEL,
                 fg=theme.FG_TEXT).pack(side="left")
        tk.Entry(search, textvariable=self.query).pack(side="left", fill="x", expand=True,
                                                       padx=theme.PAD_SMALL)
        self.query.trace_add("write", lambda *_: self._refresh())
        table = ttk.Frame(self)
        table.pack(fill="both", expand=True, padx=theme.PAD, pady=theme.PAD)
        self.tree = ttk.Treeview(table, columns=("type", "title", "location"),
                                 show="headings", selectmode="extended")
        for key, label, width in (("type", "Type", 80), ("title", "Title", 190),
                                  ("location", "Original location", 440)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        horizontal = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        horizontal.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Control-a>", self._select_all)
        self.tree.bind("<Control-A>", self._select_all)
        tk.Label(self, text="Ctrl/Shift-click to select multiple. Ctrl+A selects all visible sources.",
                 bg=theme.BG_PANEL, fg=theme.FG_MUTED).pack(anchor="w", padx=theme.PAD)
        tk.Label(self, text="Original files stay on disk. Selected saved notes are deleted.",
                 bg=theme.BG_PANEL, fg=theme.FG_MUTED).pack(anchor="w", padx=theme.PAD)
        bar = tk.Frame(self, bg=theme.BG_PANEL)
        bar.pack(fill="x", padx=theme.PAD, pady=theme.PAD)
        tk.Button(bar, text="Remove Selected", command=self._remove).pack(side="left")
        tk.Button(bar, text="Close", command=self.destroy).pack(side="right")
        self._refresh()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for source_id, kind, title, location in filter_source_rows(
                self.service.list_sources(), self.query.get()):
            self.tree.insert("", "end", iid=str(source_id), values=(kind, title, location))

    def _select_all(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _remove(self):
        ids = [int(item) for item in self.tree.selection()]
        if not ids:
            messagebox.showinfo("Remove Sources", "Select one or more sources first.", parent=self)
            return
        if not messagebox.askyesno("Confirm Removal",
                                   f"Remove {len(ids)} selected source(s) from BrisartAI?\n"
                                   "Saved notes selected here are also deleted.\n"
                                   "Original files will not be deleted.", parent=self):
            return
        try:
            removed = self.service.remove_sources(ids)
        except Exception as exc:
            messagebox.showerror("Remove Sources", str(exc), parent=self)
            return
        self._refresh()
        if self.on_change:
            self.on_change()
        messagebox.showinfo("Remove Sources", f"Removed {removed} source(s).", parent=self)


class AddSourcesDialog(tk.Toplevel):
    """Queue files and recursive folders before importing them together."""

    def __init__(self, master, on_import, on_cancel_import):
        super().__init__(master)
        self.title("Add Sources")
        self.transient(master)
        self.geometry("720x440")
        self.minsize(630, 370)
        self._running = False
        self._snapshot = None
        self._started = 0.0
        self._stopping = False
        self.on_import = on_import
        self.on_cancel_import = on_cancel_import
        self._paths = {}
        self._drop_timer = None
        self.status = tk.StringVar()
        self.instructions = tk.StringVar(master=self, value="Browse for supported files or entire folders.")
        ttk.Label(self, textvariable=self.instructions).pack(anchor="w", padx=12, pady=8)
        box = ttk.Frame(self)
        box.pack(fill="both", expand=True, padx=12)
        self.queue = tk.Listbox(box, selectmode="extended", exportselection=False)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.queue.yview)
        self.queue.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.queue.pack(side="left", fill="both", expand=True)
        ttk.Label(self, textvariable=self.status).pack(anchor="w", padx=12)
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100,
                                        style="Import.Horizontal.TProgressbar")
        self.progress.pack(fill="x", padx=12, pady=(8, 3))
        self.progress_detail = tk.StringVar(master=self)
        self.progress_label = ttk.Label(self, textvariable=self.progress_detail, wraplength=590)
        self.progress_label.pack(anchor="w", padx=12)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=10)
        self.edit_buttons = []
        for label, command in (("Browse Files", lambda: self._browse("files")),
                               ("Browse Folder", lambda: self._browse("folder")),
                               ("Remove from Queue", self._unqueue)):
            button = ttk.Button(bar, text=label, command=command)
            button.pack(side="left")
            self.edit_buttons.append(button)
        self.close_button = ttk.Button(bar, text="Close", command=self._request_close)
        self.close_button.pack(side="right", padx=(6, 0))
        self.import_button = ttk.Button(bar, text="Import Sources", command=self._import, state="disabled")
        self.import_button.pack(side="right")
        self.update_idletasks()
        if sys.platform == "win32":
            from brisart_ai.ui.windows_drop import ExplorerDrop
            try:
                self._drop = ExplorerDrop(self.queue.winfo_id())
            except OSError:
                instructions.set("Drag and drop unavailable. Use Browse Files or Browse Folder.")
            else:
                instructions.set("Drop files or folders into the list, or use the Browse buttons.")
                self._poll_drop()
        self.protocol("WM_DELETE_WINDOW", self._request_close)
        self.bind("<Escape>", self._request_close)
        self.grab_set()

    def _browse(self, kind):
        self._enqueue(ask_import_paths(self, kind))

    def _enqueue(self, paths):
        skipped = 0
        for value in paths:
            path = Path(value)
            if not (path.is_dir() or (path.is_file() and is_supported(path))):
                skipped += 1
                continue
            key = os.path.normcase(os.path.abspath(path))
            if key not in self._paths:
                self._paths[key] = str(path)
                self.queue.insert("end", str(path))
        self.import_button.configure(state="normal" if self._paths else "disabled")

        if paths:
            self.status.set(f"{len(self._paths)} queued; {skipped} unsupported or unavailable in last selection.")

    def _poll_drop(self):
        pending = self._drop.paths
        dropped = [pending.popleft() for _ in range(len(pending))]
        if not self._running:
            self._enqueue(dropped)
        self._drop_timer = self.after(125, self._poll_drop)

    def _unqueue(self):
        keys = list(self._paths)
        for index in reversed(self.queue.curselection()):
            del self._paths[keys[index]]
            self.queue.delete(index)
        self.status.set(f"{len(self._paths)} queued.")
        self.import_button.configure(state="normal" if self._paths else "disabled")

    def _import(self):
        if self._running or not self._paths:
            return
        self._running = True
        self._stopping = False
        self._started = monotonic()
        self._snapshot = None
        self.instructions.set("Selected files and folders in this batch.")
        self.progress.pack(fill="x", padx=12, pady=(8, 3), before=self.progress_label)
        self.status.set("Importing local sources...")
        self.progress.configure(mode="indeterminate", value=0)
        self.progress.start(75)
        self.update_import(None)
        self.close_button.configure(text="Cancel Import")
        for button in (*self.edit_buttons, self.import_button):
            button.state(["disabled"])
        self.on_import(list(self._paths.values()), self)

    def update_import(self, snapshot):
        if snapshot is not None:
            if self._snapshot is None and not self._stopping:
                self.progress.stop()
                self.progress.configure(mode="determinate")
            self._snapshot = snapshot
        now = monotonic()
        percent, text = progress_text(now, self._started, self._snapshot, stopping=self._stopping)
        if percent is not None:
            self.progress.configure(value=percent)
        self.progress_detail.set(text)

    def finish_import(self, ok, result, *, cancelled=False):
        self._running = False
        self.progress.stop()
        if ok and not cancelled:
            if self._snapshot and self._snapshot[1]:
                self.progress.configure(mode="determinate", value=100)
            self._paths.clear()
            self.queue.delete(0, "end")
        self.close_button.configure(text="Close")
        self.instructions.set("Original selection kept for retry. Nothing is importing." if cancelled
                              else "Browse for supported files or entire folders.")
        if cancelled:
            self.status.set("Import stopped. Indexed files were kept.")
            indexed = self._snapshot[2] if self._snapshot else 0
            elapsed = elapsed_label(monotonic() - self._started)
            self.progress_detail.set(f"{indexed:,} indexed  |  Elapsed {elapsed}")
        else:
            self.status.set(result if ok else "Import failed. Review the details below.")
        if not ok:
            self.progress_detail.set(f"{result} | Elapsed {elapsed_label(monotonic() - self._started)}")
        for button in (*self.edit_buttons, self.close_button):
            button.state(["!disabled"])
        self.import_button.state(["!disabled" if self._paths else "disabled"])
        self.close_button.focus_set()

    def show_stopping(self):
        self._stopping = True
        self.close_button.configure(text="Stopping...")
        self.close_button.state(["disabled"])
        self.progress.stop()
        self.progress.pack_forget()
        self.instructions.set("Batch canceled. The list below is the original selection, not active work.")
        self.status.set("Stopping import safely. The current file and worker cleanup may take a moment.")
        self.update_import(None)

    def _request_close(self, _event=None):
        if self._running:
            self.on_cancel_import()
        else:
            self.destroy()
        return "break"

    def destroy(self):
        self.progress.stop()
        if self._drop_timer is not None:
            self.after_cancel(self._drop_timer)
            self._drop_timer = None
        super().destroy()


class SourceNoteDialog(tk.Toplevel):
    """Capture one exact passage and the user's separate observations."""

    def __init__(self, master, service, on_saved):
        super().__init__(master)
        self.title("Add Note")
        self.transient(master)
        self.geometry("770x630")
        self.minsize(600, 480)
        self.service, self.on_saved = service, on_saved
        self.source_id = None
        self.passage = ""
        self.rows = [row for row in service.list_sources() if row[1] == "file"]
        self.query = tk.StringVar()
        self.title_value = tk.StringVar()
        self.choice = ttk.Combobox(self, state="readonly")
        self.choice.bind("<<ComboboxSelected>>", self._preview)
        self._field("Find an imported source (optional for a standalone note)", ttk.Entry(self, textvariable=self.query))
        self.choice.pack(fill="x", padx=12)
        self.preview = self._text("Indexed source preview", 11, expand=True)
        self.preview.configure(state="disabled", exportselection=False)
        self.caption = tk.StringVar(value="No passage attached.")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=12)
        ttk.Button(toolbar, text="Attach Highlighted Text", command=self._attach).pack(side="left")
        ttk.Button(toolbar, text="Clear Attachment", command=self._clear).pack(side="left")
        ttk.Label(self, textvariable=self.caption).pack(anchor="w", padx=12)
        self._field("Note title", ttk.Entry(self, textvariable=self.title_value))
        self.observations = self._text("Your observations", 5)
        ttk.Button(self, text="Save Note", command=self._save).pack(anchor="e", padx=12, pady=10)
        self.query.trace_add("write", lambda *_: self._filter())
        self._filter()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _field(self, title, widget, expand=False):
        ttk.Label(self, text=title).pack(anchor="w", padx=12, pady=(5, 1))
        widget.pack(fill="both" if expand else "x", expand=expand, padx=12)

    def _text(self, label, height, expand=False):
        from tkinter.scrolledtext import ScrolledText
        widget = ScrolledText(self, height=height, wrap="word")
        self._field(label, widget, expand)
        return widget

    def _filter(self):
        self.matches = filter_source_rows(self.rows, self.query.get())
        self.choice.configure(values=[f"{row[2]} | {row[3]}" for row in self.matches])
        self.choice.set("")
        self._show_text("")
        self.preview_id = None

    def _show_text(self, text):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _preview(self, _event):
        position = self.choice.current()
        if position < 0:
            return
        self.preview_id = self.matches[position][0]
        record = self.service.get_source_for_note(self.preview_id)
        self._show_text(record[2] if record else "Source is no longer indexed.")

    def _attach(self):
        if self.preview_id is None or not self.preview.tag_ranges("sel"):
            messagebox.showinfo("Add Note", "Choose a source and highlight a passage first.", parent=self)
            return
        passage = self.preview.get("sel.first", "sel.last").strip()
        if not passage:
            return
        self.source_id, self.passage = self.preview_id, passage
        self.caption.set(f"Attached {len(self.passage):,} characters from {self.choice.get()}"[:105])
        if not self.title_value.get().strip():
            self.title_value.set(self.matches[self.choice.current()][2])

    def _clear(self):
        self.source_id, self.passage = None, ""
        self.caption.set("No passage attached.")

    def _save(self):
        body = self.observations.get("1.0", "end-1c").strip()
        if not (body or self.passage):
            messagebox.showinfo("Add Note", "Write an observation or attach a passage.", parent=self)
            return
        try:
            if self.source_id is None:
                result = self.service.add_note(self.title_value.get(), body)
            else:
                result = self.service.add_source_note(self.title_value.get(), body, self.source_id, self.passage)
        except Exception as exc:
            messagebox.showerror("Add Note", str(exc), parent=self)
            return
        self.on_saved(result)
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Checkbox panel for BrisartAI research settings."""

    def __init__(self, master, service, on_change=None):
        super().__init__(master)
        self.title("Research Settings")
        self.configure(bg=theme.BG_PANEL)
        self.resizable(False, False)
        self.service = service
        self.on_change = on_change
        self.vars = {}
        self._build()
        self.transient(master)
        self.bind("<Escape>", lambda _event: self.destroy())
        self.grab_set()

    def _build(self) -> None:
        heading = tk.Label(self, text="Research Sources", bg=theme.BG_PANEL, fg=theme.FG_ACCENT, font=theme.FONT_HEADING)
        heading.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, theme.PAD_SMALL))

        for key, label in TOGGLE_LABELS.items():
            var = tk.BooleanVar(value=self.service.settings.get(key))
            self.vars[key] = var
            chk = tk.Checkbutton(
                self, text=label, variable=var, command=lambda k=key: self._toggle(k),
                bg=theme.BG_PANEL, fg=theme.FG_TEXT, selectcolor=theme.BG_INPUT,
                activebackground=theme.BG_PANEL, activeforeground=theme.FG_ACCENT,
                font=theme.FONT_UI, anchor="w",
            )
            chk.pack(fill="x", padx=theme.PAD, pady=2)

        note = tk.Label(
            self,
            text=(
                "Choose whether imported files and saved notes are\n"
                "included when answering questions."
            ),
            bg=theme.BG_PANEL, fg=theme.FG_MUTED, font=("Segoe UI", 8), justify="left",
        )
        note.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, theme.PAD))

        close_btn = tk.Button(
            self, text="Close", command=self.destroy, bg=theme.FG_ACCENT_DIM,
            fg="#0b0d10", relief="flat", font=theme.FONT_UI_BOLD, padx=14,
        )
        close_btn.pack(pady=(0, theme.PAD))

    def _toggle(self, key: str) -> None:
        try:
            self.service.settings.set(key, self.vars[key].get())
        except Exception as exc:
            self.vars[key].set(self.service.settings.get(key))
            messagebox.showerror("Could not save settings", str(exc), parent=self)
            return
        if self.on_change:
            self.on_change()


__all__ = ["ask_import_paths", "RemoveSourcesDialog", "AddSourcesDialog", "SourceNoteDialog", "SettingsDialog"]

