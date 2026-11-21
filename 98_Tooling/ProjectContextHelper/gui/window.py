"""
File: gui/window.py

Purpose
-------
Open the desktop window: title, header and attribution, the Build, Options, Extras, View,
  and About tabs, the status bar, safe closing while an export is running, and hiding the
  Extras tab when every one of its sections has been hidden.

Communication / relationships
-----------------------------
Imports application/identity.py (attribution), gui/state.py (make_gui_state, SECTIONS,
  has_visible_sections), gui/build_tab.py,
  gui/options_tab.py, gui/extras_tab.py, gui/view_tab.py, gui/about_tab.py (one
  create_*_tab each), and
  gui/widgets.py (MUTED). Imported only by cli.py, and only when no project folder is given, so command-line
  exports never load tkinter.

Settings / parameters
---------------------
The window opens at 860x760 with a 780x680 minimum. The window is never resized to fit its
  content; it keeps the size the user chose.

Edge cases
----------
The Extras tab is set to the notebook state "hidden" when every Extras section is hidden
  and back to "normal" when one is shown, so it keeps its place between Options and View. It
  is evaluated at startup too, from the remembered choice. The tab can only be hidden from
  the View tab, which is always shown, so the user is never left without a way back.
  Closing while idle closes at once. Closing during a build asks first; if confirmed, it
  cancels the build, waits for the worker to remove the staging folder, then closes, checking
  every 100 ms.

Known limitations
-----------------
Requires tkinter and a display; a missing one fails when the window is created. Cancellation
  is cooperative, so a file read or ZIP write in progress finishes before the window closes.

Examples
--------
From the directory containing run.py:

    python run.py
"""

import tkinter as tk
from tkinter import messagebox, ttk

from application.identity import AFFILIATION, APP_NAME, APP_VERSION, AUTHOR
from gui.state import SECTIONS, has_visible_sections, make_gui_state
from gui.build_tab import create_build_tab
from gui.options_tab import create_options_tab
from gui.extras_tab import create_extras_tab
from gui.view_tab import create_view_tab
from gui.about_tab import create_about_tab
from gui.widgets import MUTED


def run_gui() -> None:
    window = tk.Tk()
    window.title(f"{APP_NAME} v{APP_VERSION}")
    window.geometry("860x760")
    window.minsize(780, 680)
    state = make_gui_state()
    header = tk.Label(window, text=APP_NAME, font=("Segoe UI", 20, "bold"))
    header.pack(pady=(18, 4))
    subheader = tk.Label(
        window, text=(f"v{APP_VERSION} \u2022 {AUTHOR} \u2022 {AFFILIATION}"), font=("Segoe UI", 9), fg=MUTED,
    )
    subheader.pack(pady=(0, 12))
    notebook = ttk.Notebook(window)
    notebook.pack(fill="both", expand=True, padx=24, pady=(0, 8))
    build_tab = tk.Frame(notebook)
    options_tab = tk.Frame(notebook)
    extras_tab = tk.Frame(notebook)
    view_tab = tk.Frame(notebook)
    about_tab = tk.Frame(notebook)
    notebook.add(build_tab, text="Build")
    notebook.add(options_tab, text="Options")
    notebook.add(extras_tab, text="Extras")
    notebook.add(view_tab, text="View")
    notebook.add(about_tab, text="About")
    create_build_tab(parent=build_tab, window=window, state=state)
    create_options_tab(parent=options_tab, state=state)
    create_extras_tab(parent=extras_tab, state=state)
    create_view_tab(parent=view_tab, state=state)
    create_about_tab(parent=about_tab)
    def sync_extras_tab(*_args) -> None:
        # "hidden" keeps the tab's slot, so it returns between Options and View, not at the end.
        notebook.tab(extras_tab, state="normal" if has_visible_sections(state, "Extras") else "hidden")

    for key, tab, _label in SECTIONS:
        if tab == "Extras":
            state.section_vars[key].trace_add("write", sync_extras_tab)
    sync_extras_tab()

    status_bar = tk.Label(window, textvariable=state.status_text, anchor="w", relief="sunken", padx=8)
    status_bar.pack(side="bottom", fill="x")

    def close() -> None:
        if not state.jobs.busy:
            window.destroy()
            return
        if not messagebox.askyesno("Build In Progress", "A build is still running. Cancel it and close once cleanup finishes?"):
            return
        state.closing = True
        state.jobs.cancel.set()
        state.status_text.set("Cancelling build before closing...")
        wait_for_worker()

    def wait_for_worker() -> None:
        if state.jobs.busy:
            window.after(100, wait_for_worker)
        else:
            window.destroy()

    window.protocol("WM_DELETE_WINDOW", close)
    window.mainloop()
