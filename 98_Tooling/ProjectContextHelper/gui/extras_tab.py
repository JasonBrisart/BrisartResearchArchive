"""
File: gui/extras_tab.py

Purpose
-------
Build the scrollable Extras tab: the opt-in Include Git State checkbox and the Custom
  Profiles section (save the current settings under a name, then load, delete, or refresh
  the list).

Communication / relationships
-----------------------------
Imports export/settings.py (built-in profile names), gui/state.py (GuiState,
  build_settings_from_state, apply_custom_profile_to_state), gui/widgets.py, and storage
  (profile persistence). Imported by gui/window.py.

Settings / parameters
---------------------
A saved profile is the complete ScanSettings, including values the window does not show and
  the CPU Cores choice. Names are trimmed; standard and archive are reserved in any case.

Edge cases
----------
An empty name, a reserved name, or invalid size fields show a warning before saving. Saving
  over an existing name asks first. Loading a missing name shows an error and refreshes the
  list. Deleting asks for confirmation. A busy settings folder or an unreadable
  custom_profiles.json shows an error and changes nothing.

Known limitations
-----------------
Names are case-sensitive after trimming. Loading a profile changes the controls but is not
  remembered as last-used until a build succeeds. Built-in profiles never turn Git State on,
  but a custom profile or last-used settings can.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.extras_tab import create_extras_tab
    from gui.state import make_gui_state

    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_extras_tab(frame, make_gui_state())
    window.mainloop()
"""

import tkinter as tk
from tkinter import messagebox, ttk

from export.settings import PROFILE_ARCHIVE, PROFILE_STANDARD
from gui.state import GuiState, apply_custom_profile_to_state, build_settings_from_state
from gui.widgets import MUTED, create_scrollable_area
import storage


def create_extras_tab(parent: tk.Frame, state: GuiState) -> None:
    content = create_scrollable_area(parent)
    tk.Label(
        content, fg=MUTED, anchor="w", justify="left", wraplength=680,
        text=(
            "Nothing on this tab is turned on by a built-in profile. Export settings are always "
            "remembered between sessions; to start fresh, pick 'standard' or 'archive' on the Build tab."
        ),
    ).pack(fill="x", padx=16, pady=(16, 8))

    git_frame = tk.LabelFrame(content, text="Extras (Optional)", padx=12, pady=12)
    git_frame.pack(fill="x", padx=16, pady=(0, 8))
    tk.Checkbutton(git_frame, text="Include Git State", variable=state.include_git_state_var).grid(row=0, column=0, sticky="nw", pady=2)
    tk.Label(
        git_frame, fg=MUTED, anchor="w", justify="left", wraplength=560,
        text=(
            "Adds the branch, HEAD commit, clean or dirty working tree, and recent commits, read "
            "directly from .git (no git program is run). Projects without a .git folder just "
            "report that they are not tracked."
        ),
    ).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=2)

    create_profiles_section(content, state)


def create_profiles_section(
    parent: tk.Frame,
    state: GuiState,
) -> None:
    frame = tk.LabelFrame(parent, text="Custom Profiles", padx=12, pady=12)
    frame.pack(fill="x", padx=16, pady=(8, 16))
    intro = tk.Label(
        frame,
        text=(
            "Save the exact combination of settings on the Options "
            "and Extras tabs under a name you choose, then reload or "
            "delete it later. Separate from the built-in 'standard' "
            "and 'archive' profiles, and from your automatically "
            "remembered last-used settings, which have no name and "
            "can't be listed or deleted individually."
        ),
        fg=MUTED,
        anchor="w",
        justify="left",
        wraplength=680,
    )
    intro.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
    tk.Label(frame, text="Profile Name:").grid(row=1, column=0, sticky="w", pady=4)
    name_combo = ttk.Combobox(frame, textvariable=state.custom_profile_var, width=30)
    name_combo.grid(row=1, column=1, columnspan=3, sticky="w", pady=4)

    def refresh_names() -> None:
        name_combo["values"] = storage.list_profiles()

    refresh_names()

    def save_current() -> None:
        name = state.custom_profile_var.get().strip()
        if not name:
            messagebox.showwarning("Name Required", "Type a name for this custom profile first.")
            return
        if storage.is_reserved_name(name):
            messagebox.showwarning(
                "Reserved Name",
                f"'{name}' is a built-in profile name ('{PROFILE_STANDARD}' / '{PROFILE_ARCHIVE}') "
                "and can't be used for a custom profile. Choose a different name.",
            )
            return
        try:
            settings = build_settings_from_state(state)
        except ValueError as exc:
            messagebox.showwarning("Invalid Settings", str(exc))
            return
        if name in storage.list_profiles():
            if not messagebox.askyesno("Overwrite Profile", f"A custom profile named '{name}' already exists. Overwrite it with the current settings?"):
                return
        try:
            storage.save_profile(name, settings)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Could Not Save Profile", str(exc))
            return
        refresh_names()
        messagebox.showinfo("Profile Saved", f"Custom profile '{name}' saved.")

    def load_selected() -> None:
        name = state.custom_profile_var.get().strip()
        if not name:
            messagebox.showwarning("No Profile Selected", "Choose a custom profile to load first.")
            return
        loaded = storage.load_profile(name)
        if loaded is None:
            messagebox.showerror("Profile Not Found", f"No custom profile named '{name}' was found.")
            refresh_names()
            return
        apply_custom_profile_to_state(state, loaded)
        messagebox.showinfo("Profile Loaded", f"Custom profile '{name}' loaded.")

    def delete_selected() -> None:
        name = state.custom_profile_var.get().strip()
        if not name:
            messagebox.showwarning("No Profile Selected", "Choose a custom profile to delete first.")
            return
        if not messagebox.askyesno("Delete Profile", f"Delete custom profile '{name}'? This cannot be undone."):
            return
        try:
            deleted = storage.delete_profile(name)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Could Not Delete Profile", str(exc))
            return
        refresh_names()
        if deleted:
            state.custom_profile_var.set("")
            messagebox.showinfo("Profile Deleted", f"Custom profile '{name}' deleted.")
        else:
            messagebox.showerror("Profile Not Found", f"No custom profile named '{name}' was found.")

    button_row = tk.Frame(frame)
    button_row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
    tk.Button(button_row, text="Save Current As", command=save_current).pack(side="left")
    tk.Button(button_row, text="Load Selected", command=load_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Delete Selected", command=delete_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Refresh List", command=refresh_names).pack(side="left", padx=(8, 0))
