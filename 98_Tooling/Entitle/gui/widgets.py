"""
Entitle GUI Widgets

Shared Tkinter form-building helpers used by every tab in gui/tabs/.

Keeping this in one place means each tab module only has to describe *what* fields
it needs, not *how* to lay out a label/entry/checkbox row — so adding a new tab is
a matter of writing a small, focused file rather than copying layout boilerplate.
"""
import tkinter as tk
from tkinter import filedialog, ttk


class FormFrame(ttk.Frame):
    """A simple label/entry/checkbox form frame with an internal row counter."""

    def __init__(self, parent):
        super().__init__(parent, padding=12)
        self._row = 0
        self.vars = {}
        self.grid_columnconfigure(1, weight=1)

    def add_entry(self, key, label, *, default="", show=None, browse=None):
        ttk.Label(self, text=label).grid(row=self._row, column=0, sticky="w", pady=3)
        var = tk.StringVar(value=default)
        entry = ttk.Entry(self, textvariable=var, width=48, show=show or "")
        entry.grid(row=self._row, column=1, sticky="we", padx=6, pady=3)
        self.vars[key] = var
        if browse is not None:
            button = ttk.Button(self, text="Browse…", command=lambda: self._browse(var, browse))
            button.grid(row=self._row, column=2, padx=(0, 6))
        self._row += 1
        return var

    def add_checkbox(self, key, label, *, default=False):
        var = tk.BooleanVar(value=default)
        check = ttk.Checkbutton(self, text=label, variable=var)
        check.grid(row=self._row, column=0, columnspan=2, sticky="w", pady=2)
        self.vars[key] = var
        self._row += 1
        return var

    def add_int_entry(self, key, label, *, default=1):
        return self.add_entry(key, label, default=str(default))

    def next_row(self):
        row = self._row
        self._row += 1
        return row

    def _browse(self, var, mode):
        if mode == "open":
            path = filedialog.askopenfilename(title="Select file")
        elif mode == "save":
            path = filedialog.asksaveasfilename(title="Select output path")
        else:
            path = filedialog.askopenfilename(title="Select file")
        if path:
            var.set(path)

    def get(self, key):
        return self.vars[key].get()

    def get_int(self, key, default=1):
        raw = self.vars[key].get().strip()
        if not raw:
            return default
        return int(raw)

    def get_bool(self, key):
        return self.vars[key].get()
