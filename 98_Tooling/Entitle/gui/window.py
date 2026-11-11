"""
File: gui/window.py

Purpose
-------
Be Entitle's desktop window shell: the main window, the notebook that holds the workflow tabs,
  the shared output pane, and the one place a button's result or error is shown. It turns every
  error into a message in the pane plus a dialog, so a mistake never closes the window.

Communication / relationships
-----------------------------
Imports tkinter (tk, ttk, messagebox, ScrolledText), entitle/common.py (EntitleError),
  gui/tabs.py (TABS) and version.py (the title). Imported only by cli.py, through launch(), and
  only when the window is opened (the gui command, or no command at all), so the other commands
  never load tkinter. The tabs call back into the window through the app object they are given:
  app.shared (fields shared between tabs) and app.run(action). Covered by tests/test_gui.py,
  which runs it against tests/fake_tk.py.

Settings / parameters
---------------------
Title "Entitle <version> — Software Rights Management". The window opens at 880x640 or, when
  its tallest tab needs more room, at the size the content asks for, never more than the screen
  minus 60 px across and 120 px down (title bar and taskbar). The minimum is 760x560, or the
  starting size on a smaller screen. The output pane is 8 lines high. app.run(action) wraps a
  button's function: a string result is shown as text, anything else as indented JSON (dates
  and other non-JSON values via str), and an exception as "ERROR: <type>: <message>" in the
  pane plus an error dialog.

Edge cases
----------
Every exception from a button is caught, including EncryptionNotFoundError when 97_Encryption
  cannot be linked, so the window stays open and usable. launch() turns a Tk that cannot open a
  display (tk.TclError, for example on a headless machine) into EntitleError, which cli.py
  prints as one error line. The output pane is read-only; each result replaces the last. The
  size is measured after every tab exists, because the notebook is as tall as its tallest tab;
  measuring earlier would under-size the window. On a screen too small for the content, the
  output pane (packed last) is the part that gets squeezed.

Known limitations
-----------------
One window per process, no menus, no remembered size or position, and no keyboard shortcuts
  beyond what Tk provides. Long-running work (such as a large record log) blocks the window
  until it finishes, because buttons run on the Tk thread.

Examples
--------
From the directory containing run.py:

    python run.py

(python run.py gui does the same) or, from Python:

    from gui.window import launch

    launch()
"""

import json
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from entitle.common import EntitleError
from gui.tabs import TABS
from version import __version__

START_WIDTH = 880
START_HEIGHT = 640
MIN_WIDTH = 760
MIN_HEIGHT = 560
SCREEN_MARGIN_X = 60  # room left beside the window
SCREEN_MARGIN_Y = 120  # room left for the title bar and the taskbar


class EntitleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Entitle {__version__} — Software Rights Management")
        self.shared = {}
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)
        self.output = ScrolledText(self, height=8, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=False, padx=8, pady=(0, 8))
        for title, build in TABS:
            notebook.add(build(notebook, self), text=title)
        self._fit_to_content()

    def _fit_to_content(self):
        self.update_idletasks()
        width = min(max(START_WIDTH, self.winfo_reqwidth()), self.winfo_screenwidth() - SCREEN_MARGIN_X)
        height = min(max(START_HEIGHT, self.winfo_reqheight()), self.winfo_screenheight() - SCREEN_MARGIN_Y)
        self.geometry(f"{width}x{height}")
        self.minsize(min(MIN_WIDTH, width), min(MIN_HEIGHT, height))

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
