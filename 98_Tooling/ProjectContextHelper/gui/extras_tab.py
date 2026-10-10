"""
File: gui/extras_tab.py

Purpose
-------
Create the scrollable Extras tab containing optional Git State and custom profile controls.

Implemented responsibilities:
- create_extras_tab: Create a scrollable container, explanatory text, an Include Git State
  checkbox bound to shared state, and the custom profile section.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- gui.builders: GuiState.
- gui.profiles_section: create_custom_profiles_section.
- gui.scroll_frame: create_scrollable_area.

Consumers in the supplied source:
- gui/main_gui.py imports create_extras_tab.

Settings / parameters
---------------------
Receives a parent frame and GuiState. Git State is opt-in and off in both built-in presets.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_extras_tab(parent: tk.Frame, state: GuiState) -> None

Edge cases
----------
Delegates profile validation and management to gui.profiles_section and scrolling to
  gui.scroll_frame.

Saved last-used settings or a custom profile can restore Git State as enabled even though both
  built-in presets disable it.

Known limitations
-----------------
Git State inherits the parser limitations in core.git_state. The introductory UI text does not
  describe all hidden ScanSettings fields.

The introductory statement that nothing here is enabled by a preset does not mean custom
  profiles cannot restore previously enabled optional settings.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.builders import make_gui_state
    from gui.extras_tab import create_extras_tab

    window = tk.Tk()
    state = make_gui_state()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_extras_tab(frame, state)
    window.mainloop()

    This constructs the component in an existing Tk application. For the complete
    four-tab interface, use python run.py rather than running this module directly.
"""

import tkinter as tk

from gui.builders import GuiState
from gui.profiles_section import create_custom_profiles_section
from gui.scroll_frame import create_scrollable_area


def create_extras_tab(
    parent: tk.Frame,
    state: GuiState,
) -> None:
    content = create_scrollable_area(parent)

    intro = tk.Label(
        content,
        text=(
            "Extras and Custom Profiles are kept separate from the "
            "main Options tab: nothing here is enabled by a profile "
            "preset, and nothing here changes a build's core output "
            "unless you explicitly turn it on.\n\n"
            "Note: your export settings are always remembered "
            "automatically between sessions -- there's no toggle for "
            "that. To start fresh, just pick 'standard' or 'archive' "
            "from the profile dropdown on the Build tab."
        ),
        fg="#666666",
        anchor="w",
        justify="left",
        wraplength=680,
    )
    intro.pack(fill="x", padx=16, pady=(16, 8))

    extras_frame = tk.LabelFrame(content, text="Extras (Optional)", padx=12, pady=12)
    extras_frame.pack(fill="x", padx=16, pady=(0, 8))
    extras_options = [
        (
            "Include Git State",
            state.include_git_state_var,
            "Adds a 'Git State' section reporting branch, HEAD commit, "
            "dirty/clean working tree, and recent commits, by reading "
            ".git directly (no external git binary is invoked). Only "
            "useful for projects actually under git version control; "
            "otherwise the section just reports 'not tracked' and adds "
            "nothing else.",
        ),
    ]
    for index, (label, variable, help_text) in enumerate(extras_options):
        tk.Checkbutton(extras_frame, text=label, variable=variable).grid(row=index, column=0, sticky="w", pady=2)
        tk.Label(extras_frame, text=help_text, fg="#666666", anchor="w", justify="left", wraplength=560).grid(row=index, column=1, sticky="w", padx=(12, 0), pady=2)

    create_custom_profiles_section(content, state)

