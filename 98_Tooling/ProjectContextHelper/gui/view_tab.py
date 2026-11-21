"""
File: gui/view_tab.py

Purpose
-------
Build the View tab ("What do you want to see?"): one checkbox per optional part of the
  window, grouped by the tab it lives on. Unselecting one removes it at once and everything
  below it moves up; selecting it brings it back in its original place. A Show Everything
  button turns them all back on.

Communication / relationships
-----------------------------
Imports gui/state.py (GuiState, SECTIONS). Imported by gui/window.py. The checkboxes edit
  state.section_vars; the tabs that own each section (gui/build_tab.py,
  gui/options_tab.py, gui/extras_tab.py) react through gui/state.py's bind_visibility and
  optional_section, gui/window.py hides the Extras tab when none of its sections is shown,
  and gui/state.py saves the choice to app_settings.json on every change.

Settings / parameters
---------------------
The list of sections and their labels is gui/state.py's SECTIONS; this tab adds no keys
  of its own. Everything is visible by default.

Edge cases
----------
Hiding a section never changes a setting: a hidden Git State checkbox that is on still
  adds Git State to every export, and the tab says so. Hiding every Extras section hides the
  Extras tab itself (gui/window.py does that); this tab is never hidden, so the way back is
  always there.

Known limitations
-----------------
Only optional sections can be hidden; the project folder, profile, Build button, export
  settings, and the output-section checkboxes are always shown.

Examples
--------
Usage from the directory containing run.py:
    import tkinter as tk
    from gui.state import make_gui_state
    from gui.view_tab import create_view_tab
    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_view_tab(frame, make_gui_state())
    window.mainloop()
"""

import tkinter as tk

from gui.state import SECTIONS, GuiState
from gui.widgets import MUTED


def create_view_tab(parent: tk.Frame, state: GuiState) -> None:
    tk.Label(parent, text="What do you want to see?", font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x", padx=16, pady=(16, 2))
    tk.Label(
        parent, fg=MUTED, anchor="w", justify="left", wraplength=680,
        text=(
            "Unselect anything to hide it. Everything below it moves up to fill the space, a "
            "scrollbar appears only when a tab is taller than the window, and a tab with nothing "
            "left (Extras) disappears. Hiding only changes what is on screen: every setting "
            "behind a hidden section still applies to your builds. Your choice is remembered."
        ),
    ).pack(fill="x", padx=16, pady=(0, 8))

    for tab in dict.fromkeys(tab for _key, tab, _label in SECTIONS):
        group = tk.LabelFrame(parent, text=f"{tab} tab", padx=12, pady=8)
        group.pack(fill="x", padx=16, pady=(0, 8))
        for key, section_tab, label in SECTIONS:
            if section_tab == tab:
                tk.Checkbutton(group, text=label, variable=state.section_vars[key]).pack(anchor="w")

    def show_everything() -> None:
        for variable in state.section_vars.values():
            variable.set(True)

    tk.Button(parent, text="Show Everything", command=show_everything).pack(anchor="w", padx=16, pady=(4, 16))
