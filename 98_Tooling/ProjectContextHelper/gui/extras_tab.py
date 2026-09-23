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
