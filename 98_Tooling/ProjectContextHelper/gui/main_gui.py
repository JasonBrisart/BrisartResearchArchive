"""
File: gui/main_gui.py

Purpose
-------
Create the desktop window, shared GUI state, four-tab notebook, status bar, and startup update
  callback.

Implemented responsibilities:
- run_gui: Create the Tk window, shared state, four notebook tabs, status bar, and delayed
  startup-check callback, then enter mainloop.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_URL.
- gui.builders: make_gui_state.
- gui.build_tab: create_build_tab.
- gui.options_tab: create_options_tab.
- gui.extras_tab: create_extras_tab.
- gui.about_tab: create_about_tab.

Consumers in the supplied source:
- cli/cli.py imports run_gui.

Settings / parameters
---------------------
Window starts at 860x760 with a 780x680 minimum. Tabs are Build, Options, Extras, and About;
  startup callback is scheduled after 500 milliseconds.

Function signatures (nested callbacks are scoped to their enclosing function):
- run_gui() -> None

Edge cases
----------
The update callback checks its preference before performing network work. The main guard allows
  direct module execution when package imports are resolvable.

The delayed callback is registered after tab construction and runs inside the same event loop.
  Missing tkinter/display errors are not caught by run_gui.

Known limitations
-----------------
Requires tkinter and a graphical display. Startup/build/update work is not moved to a worker
  thread. Use run.py as the supported source entry point.

No background worker, cancellation flow, or GUI startup exception wrapper is implemented here.

Examples
--------
Usage from the directory containing run.py:

    python run.py

    This enters run.py -> cli.cli.main -> run_cli -> run_gui when no root or
    standalone management action is supplied.
"""

import tkinter as tk
from tkinter import ttk

from core.constants import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_URL,
)
from gui.builders import make_gui_state
from gui.build_tab import create_build_tab
from gui.options_tab import create_options_tab
from gui.extras_tab import create_extras_tab
from gui.about_tab import create_about_tab


def run_gui() -> None:
    window = tk.Tk()
    window.title(f"{APP_NAME} v{APP_VERSION}")
    window.geometry("860x760")
    window.minsize(780, 680)
    state = make_gui_state()
    header = tk.Label(window, text=APP_NAME, font=("Segoe UI", 20, "bold"))
    header.pack(pady=(18, 4))
    subheader = tk.Label(
        window, text=(f"v{APP_VERSION} \u2022 {AUTHOR} \u2022 {REPOSITORY_URL}"), font=("Segoe UI", 9), fg="#555555",
    )
    subheader.pack(pady=(0, 12))
    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=24, pady=(0, 8))
    build_tab = tk.Frame(notebook)
    options_tab = tk.Frame(notebook)
    extras_tab = tk.Frame(notebook)
    about_tab = tk.Frame(notebook)
    notebook.add(build_tab, text="Build")
    notebook.add(options_tab, text="Options")
    notebook.add(extras_tab, text="Extras")
    notebook.add(about_tab, text="About")
    create_build_tab(parent=build_tab, window=window, state=state)
    create_options_tab(parent=options_tab, state=state)
    create_extras_tab(parent=extras_tab, state=state)
    startup_update_check = create_about_tab(parent=about_tab, window=window, state=state)
    status_bar = tk.Label(window, textvariable=state.status_text, anchor="w", relief="sunken", padx=8)
    status_bar.pack(side="bottom", fill="x")
    window.after(500, startup_update_check)
    window.mainloop()


if __name__ == "__main__":
    run_gui()

