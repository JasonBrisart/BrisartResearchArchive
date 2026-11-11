"""
File: gui/window.py

Purpose
-------
Be Entitle's desktop window shell: the main window, the notebook that holds the workflow tabs,
  the shared output pane, and the one place a button's result or error is shown. It turns every
  error into a message in the pane plus a dialog, so a mistake never closes the window.

Communication / relationships
-----------------------------
Imports tkinter (tk, ttk, messagebox, ScrolledText), the entitle package root (EntitleError),
  gui/tabs.py (TABS) and version.py (the title). Imported only by cli.py's gui command, through
  launch(), so the other commands never load tkinter. The tabs call back into the window through
  the app object they are given: app.shared (fields shared between tabs) and app.run(action).
  Covered by tests/test_gui.py, which runs it against tests/fake_tk.py.

Settings / parameters
---------------------
Title "Entitle <version> — Software Rights Management", size 880x640, minimum 760x560, output
  pane 10 lines high. app.run(action) wraps a button's function: a string result is shown as
  text, anything else as indented JSON (dates and other non-JSON values via str), and an
  exception as "ERROR: <type>: <message>" in the pane plus an error dialog.

Edge cases
----------
Every exception from a button is caught, including EncryptionNotFoundError when 97_Encryption
  cannot be linked, so the window stays open and usable. launch() turns a Tk that cannot open a
  display (tk.TclError, for example on a headless machine) into EntitleError, which cli.py
  prints as one error line. The output pane is read-only; each result replaces the last.

Known limitations
-----------------
One window per process, no menus, no remembered size or position, and no keyboard shortcuts
  beyond what Tk provides. Long-running work (such as a large record log) blocks the window
  until it finishes, because buttons run on the Tk thread.

Examples
--------
From the directory containing main.py:

    python main.py gui

or, from Python:

    from gui.window import launch
    launch()
"""

import json
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from entitle import EntitleError
from gui.tabs import TABS
from version import __version__

class EntitleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Entitle {__version__} — Software Rights Management")
        self.geometry("880x640")
        self.minsize(760, 560)
        self.shared = {}
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.output = ScrolledText(self, height=10, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        for title, build in TABS:
            notebook.add(build(notebook, self), text=title)

    def show_text(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.configure(state="disabled")

    def show_json(self, data):
        self.show_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    def show_error(self, exc):
        self.show_text(f"ERROR: {type(exc).__name__}: {exc}")
        messagebox.showerror("Entitle", f"{type(exc).__name__}: {exc}")

    def run(self, action):
        def command():
            try:
                result = action()
            except Exception as exc:
                self.show_error(exc)
                return
            if isinstance(result, str):
                self.show_text(result)
            else:
                self.show_json(result)

        return command


def launch():
    try:
        app = EntitleApp()
    except tk.TclError as exc:
        raise EntitleError(f"Could not open a window: {exc}") from exc
    app.mainloop()
