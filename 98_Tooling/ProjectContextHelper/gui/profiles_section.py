"""
File: gui/profiles_section.py

Purpose
-------
Create named custom profile Save, Load, Delete, and Refresh controls on the Extras tab.

Implemented responsibilities:
- create_custom_profiles_section: Build profile-name selection and Save/Load/Delete/Refresh
  buttons with callbacks that use storage and GUI settings conversion.
- refresh_names: Reload saved profile names and replace the combobox's available values.
- save_current: Trim/validate the name, reject built-in names, validate current GUI settings,
  confirm overwrite, save through storage, refresh names, and display success.
- load_selected: Require a name, load settings or report missing data, apply the loaded profile
  to GUI state, and display confirmation.
- delete_selected: Require a name, confirm deletion, remove the profile, refresh names, and
  clear selection on success.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: PROFILE_ARCHIVE, PROFILE_STANDARD.
- gui.builders: GuiState, apply_custom_profile_to_state, build_settings_from_state.
- gui.dialogs: ask_yes_no, show_error, show_info, show_warning.
- services: storage.

Consumers in the supplied source:
- gui/extras_tab.py imports create_custom_profiles_section.

Settings / parameters
---------------------
Uses GuiState, GUI settings conversion, and services.storage. Names are trimmed; built-in names
  are reserved case-insensitively.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_custom_profiles_section(parent: tk.Frame, state: GuiState) -> None
- refresh_names() -> None
- save_current() -> None
- load_selected() -> None
- delete_selected() -> None

Edge cases
----------
Empty names and invalid settings show warnings. Existing profiles require overwrite
  confirmation. Missing profiles show errors; deletion requires confirmation.

Reserved-name checking is case-insensitive, but stored custom names are case-sensitive.
  Save/load trim whitespace. GUI save/delete callbacks catch selected validation errors, not
  every filesystem exception.

Known limitations
-----------------
Custom profile names remain case-sensitive after trimming. GUI serialization does not retain
  every hidden ScanSettings field. Some storage I/O errors are not caught by these callbacks.

Profile deletion changes only the named profile record, not last-used settings or export
  history. Loading changes the current GUI settings but does not immediately persist last-used
  settings.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.builders import make_gui_state
    from gui.profiles_section import create_custom_profiles_section

    window = tk.Tk()
    state = make_gui_state()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_custom_profiles_section(frame, state)
    window.mainloop()

    This constructs the component in an existing Tk application. For the complete
    four-tab interface, use python run.py rather than running this module directly.
"""

import tkinter as tk
from tkinter import ttk

from core.constants import PROFILE_ARCHIVE, PROFILE_STANDARD
from gui.builders import (
    GuiState,
    apply_custom_profile_to_state,
    build_settings_from_state,
)
from gui.dialogs import (
    ask_yes_no,
    show_error,
    show_info,
    show_warning,
)
from services import storage


def create_custom_profiles_section(
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
        fg="#666666",
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
            show_warning("Name Required", "Type a name for this custom profile first.")
            return
        if storage.is_reserved_name(name):
            show_warning(
                "Reserved Name",
                f"'{name}' is a built-in profile name ('{PROFILE_STANDARD}' / '{PROFILE_ARCHIVE}') "
                "and can't be used for a custom profile. Choose a different name.",
            )
            return
        try:
            settings = build_settings_from_state(state)
        except ValueError as exc:
            show_warning("Invalid Settings", str(exc))
            return
        if name in storage.list_profiles():
            if not ask_yes_no("Overwrite Profile", f"A custom profile named '{name}' already exists. Overwrite it with the current settings?"):
                return
        try:
            storage.save_profile(name, settings)
        except ValueError as exc:
            show_error("Could Not Save Profile", str(exc))
            return
        refresh_names()
        show_info("Profile Saved", f"Custom profile '{name}' saved.")

    def load_selected() -> None:
        name = state.custom_profile_var.get().strip()
        if not name:
            show_warning("No Profile Selected", "Choose a custom profile to load first.")
            return
        loaded = storage.load_profile(name)
        if loaded is None:
            show_error("Profile Not Found", f"No custom profile named '{name}' was found.")
            refresh_names()
            return
        apply_custom_profile_to_state(state, loaded)
        show_info("Profile Loaded", f"Custom profile '{name}' loaded.")

    def delete_selected() -> None:
        name = state.custom_profile_var.get().strip()
        if not name:
            show_warning("No Profile Selected", "Choose a custom profile to delete first.")
            return
        if not ask_yes_no("Delete Profile", f"Delete custom profile '{name}'? This cannot be undone."):
            return
        deleted = storage.delete_profile(name)
        refresh_names()
        if deleted:
            state.custom_profile_var.set("")
            show_info("Profile Deleted", f"Custom profile '{name}' deleted.")
        else:
            show_error("Profile Not Found", f"No custom profile named '{name}' was found.")

    button_row = tk.Frame(frame)
    button_row.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))
    tk.Button(button_row, text="Save Current As", command=save_current).pack(side="left")
    tk.Button(button_row, text="Load Selected", command=load_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Delete Selected", command=delete_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Refresh List", command=refresh_names).pack(side="left", padx=(8, 0))

