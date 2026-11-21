"""
File: gui/about_tab.py

Purpose
-------
Build the About tab: what Project Context Helper does, its version, and attribution.

Communication / relationships
-----------------------------
Imports application/identity.py (name, version, author, affiliation). Imported by gui/window.py. Recent
  Exports, which lived here until v4.2.0, is now a section of gui/extras_tab.py.

Settings / parameters
---------------------
None; the text comes from application/identity.py.

Edge cases
----------
None; the tab is static.

Known limitations
-----------------
The description is fixed text; it is not generated from the export settings.

Examples
--------
Usage from the directory containing run.py:
    import tkinter as tk
    from gui.about_tab import create_about_tab
    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_about_tab(frame)
    window.mainloop()
"""

import tkinter as tk

from application.identity import AFFILIATION, APP_NAME, APP_VERSION, AUTHOR


def create_about_tab(parent: tk.Frame) -> None:
    tk.Label(
        parent, justify="left", anchor="nw", wraplength=760,
        text=(
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "A no-dependency utility that packages a project folder into a "
            "readable Markdown context file, JSON manifest, summary file, "
            "settings record, and optional ZIP snapshot.\n\n"
            f"Author: {AUTHOR}\n{AFFILIATION}"
        ),
    ).pack(fill="x", padx=18, pady=(18, 8))
