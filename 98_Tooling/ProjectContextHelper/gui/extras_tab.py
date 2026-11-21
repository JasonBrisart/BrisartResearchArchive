"""
File: gui/extras_tab.py

Purpose
-------
Build the scrollable Extras tab, which holds everything a built-in profile never turns on
  or that most exports do not need to touch: the opt-in Include Git State checkbox, the
  Performance section (CPU Cores selector, core meter, and readout), Custom Profiles (save
  everything under a name, then load, delete, or refresh the list), and Recent
  Exports (open, refresh, clear). Each section can be hidden from the View tab; when all four
  are hidden, gui/window.py hides this whole tab.

Communication / relationships
-----------------------------
Imports export/settings.py (built-in profile names, MAX_WORKERS, resolve_workers,
  worker_limit), gui/state.py (GuiState, optional_section, the settings conversions and
  CPU Cores labels), gui/widgets.py (scrollable area, MUTED, open_folder), and application/storage.py
  (profiles and history). Imported by gui/window.py. Registers its history refresh as
  state.history_refresh so the Build tab refreshes Recent Exports after each export.

Settings / parameters
---------------------
Section visibility keys: extras_git, extras_performance, extras_profiles, extras_history.
  The CPU Cores selector is read-only and lists Auto plus only the counts this machine can
  run (a 4-core machine gets Auto and 1-4). Meter cells are 14 px, or 11 px above 16 cores
  so 32 still fit the minimum window width; used cells are ACCENT and idle cells IDLE.
  The meter uses the same resolve_workers rule as the scanner, so it always matches the
  count the export reports. A saved profile holds every ScanSettings field (including the
  Advanced Filters lists and the CPU Cores choice) and the window half: Open Export Folder
  After Build, which View sections are hidden, and, when Include the project folder is ticked
  (the default), the project folder. Loading applies all of it. Names are trimmed, and
  standard and archive are reserved in any case. Recent Exports shows the newest 20 history
  entries.

Edge cases
----------
This tab never shows an empty page: with every section hidden, gui/window.py removes the
  tab from the window until one is shown again. The meter and readout redraw
  whenever workers_var changes, including when a profile is applied. A machine reporting
  more than 32 cores gets a note that only 32 are used. An empty name, a reserved name, or
  invalid size fields or Advanced Filters entries show a warning before saving; saving over a name asks first; a busy
  settings folder or an unreadable custom_profiles.json shows an error and changes
  nothing. Opening an export whose folder was deleted shows an error; clearing history asks
  first and never deletes export folders.

Known limitations
-----------------
Hiding a section never changes its setting: Git State hidden while checked still adds Git
  State to exports. Profile names are case-sensitive after trimming. Loading a profile is
  not remembered as last-used until a build succeeds (its View choices and Open Export Folder
  After Build are, at once, because those autosave). A profile saved by the command line or by
  v4.2.0 has no window half; loading it leaves those choices as they are and says so. A stored
  project folder that does not exist on this computer is skipped with a note. The meter shows threads requested,
  not live CPU load. Recent Exports does not refresh on its own when another window or the
  command line records an export; use Refresh.

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

from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from export.settings import MAX_WORKERS, PROFILE_ARCHIVE, PROFILE_STANDARD, resolve_workers, worker_limit
from gui.state import (
    GuiState,
    apply_custom_profile_to_state,
    apply_profile_window,
    build_settings_from_state,
    core_label,
    current_profile_window,
    label_to_workers,
    optional_section,
    worker_choices,
)
from gui.widgets import MUTED, create_scrollable_area, open_folder
from application import storage

ACCENT = "#2f6fde"
IDLE = "#dde3ec"


def create_extras_tab(parent: tk.Frame, state: GuiState) -> None:
    content = create_scrollable_area(parent)
    tk.Label(
        content, fg=MUTED, anchor="w", justify="left", wraplength=680,
        text=(
            "Nothing on this tab is turned on by a built-in profile. Export settings are always "
            "remembered between sessions; to start fresh, pick 'standard' or 'archive' on the Build tab. "
            "Use the View tab to hide sections you do not need."
        ),
    ).pack(fill="x", padx=16, pady=(16, 8))

    create_git_section(optional_section(state, "extras_git", content, padx=16, pady=(0, 8)), state)
    create_performance_section(optional_section(state, "extras_performance", content, padx=16, pady=(0, 8)), state)
    create_profiles_section(optional_section(state, "extras_profiles", content, padx=16, pady=(0, 8)), state)
    create_history_section(optional_section(state, "extras_history", content, padx=16, pady=(0, 16)), state)


def create_git_section(parent: tk.Frame, state: GuiState) -> None:
    frame = tk.LabelFrame(parent, text="Git State", padx=12, pady=12)
    frame.pack(fill="x")
    tk.Checkbutton(frame, text="Include Git State", variable=state.include_git_state_var).grid(row=0, column=0, sticky="nw", pady=2)
    tk.Label(
        frame, fg=MUTED, anchor="w", justify="left", wraplength=560,
        text=(
            "Adds the branch, HEAD commit, clean or dirty working tree, and recent commits, read "
            "directly from .git (no git program is run). Projects without a .git folder just "
            "report that they are not tracked."
        ),
    ).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=2)


def core_usage_text(used: int, limit: int) -> str:
    if limit == 1:
        return "Using 1 core"
    if used == limit:
        return f"Using all {limit} cores"
    return f"Using {used} of {limit} cores"


def create_performance_section(parent: tk.Frame, state: GuiState) -> None:
    limit = worker_limit(state.cpu_cores)
    frame = tk.LabelFrame(parent, text="Performance", padx=12, pady=12)
    frame.pack(fill="x")
    frame.columnconfigure(2, weight=1)

    tk.Label(frame, text="CPU Cores:").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Combobox(
        frame, textvariable=state.workers_var, values=worker_choices(state.cpu_cores),
        state="readonly", width=16,
    ).grid(row=0, column=1, sticky="w", pady=4)
    usage = tk.StringVar()
    tk.Label(frame, textvariable=usage, fg=ACCENT, font=("Segoe UI", 9, "bold")).grid(
        row=0, column=2, sticky="w", padx=(12, 0), pady=4,
    )

    cell = 14 if limit <= 16 else 11
    gap = 4
    meter = tk.Canvas(
        frame, width=limit * (cell + gap) - gap + 2, height=cell + 2, highlightthickness=0, borderwidth=0,
    )
    meter.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 8))

    detected = f"This computer reports {core_label(state.cpu_cores)}."
    if state.cpu_cores > MAX_WORKERS:
        detected += f" Project Context Helper uses up to {MAX_WORKERS}."
    tk.Label(
        frame, fg=MUTED, anchor="w", justify="left", wraplength=680,
        text=(
            f"{detected} Cores read and hash project files and compress the ZIP in parallel, "
            "so more cores finish large exports faster. Auto always uses every available core "
            "on the computer it runs on. The core count never changes which files are included."
        ),
    ).grid(row=2, column=0, columnspan=3, sticky="w")

    def redraw(*_args) -> None:
        used = resolve_workers(label_to_workers(state.workers_var.get()), state.cpu_cores)
        meter.delete("all")
        for index in range(limit):
            x = 1 + index * (cell + gap)
            fill = ACCENT if index < used else IDLE
            meter.create_rectangle(x, 1, x + cell, 1 + cell, fill=fill, outline=fill)
        usage.set(core_usage_text(used, limit))

    state.workers_var.trace_add("write", redraw)
    redraw()


def create_profiles_section(parent: tk.Frame, state: GuiState) -> None:
    frame = tk.LabelFrame(parent, text="Custom Profiles", padx=12, pady=12)
    frame.pack(fill="x")

    tk.Label(
        frame, fg=MUTED, anchor="w", justify="left", wraplength=680,
        text=(
            "A profile saves everything: every export setting on the Build, Options, and Extras "
            "tabs, the Advanced Filters lists, Open Export Folder After Build, which sections the "
            "View tab shows, and (if ticked below) the project folder. Give each person or purpose "
            "its own name; loading one sets the whole window. Separate from the built-in 'standard' "
            "and 'archive' profiles, and from your automatically remembered last-used settings."
        ),
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

    tk.Label(frame, text="Profile Name:").grid(row=1, column=0, sticky="w", pady=4)
    name_combo = ttk.Combobox(frame, textvariable=state.custom_profile_var, width=30)
    name_combo.grid(row=1, column=1, columnspan=3, sticky="w", pady=4)
    tk.Checkbutton(
        frame, text="Include the project folder when saving", variable=state.profile_folder_var,
    ).grid(row=2, column=1, columnspan=3, sticky="w", pady=(0, 4))

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
            storage.save_profile(name, settings, window=current_profile_window(state, state.profile_folder_var.get()))
        except (ValueError, OSError) as exc:
            messagebox.showerror("Could Not Save Profile", str(exc))
            return
        refresh_names()
        messagebox.showinfo("Profile Saved", f"Custom profile '{name}' saved with every setting and your window choices.")

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
        window = storage.load_profile_window(name)
        if window is None:
            notes = ["It was saved without window choices (by the command line or an older version), so the View tab and Open Export Folder After Build were left as they are."]
        else:
            notes = apply_profile_window(state, window)
        messagebox.showinfo("Profile Loaded", "\n\n".join([f"Custom profile '{name}' loaded.", *notes]))

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
    button_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))
    tk.Button(button_row, text="Save Current As", command=save_current).pack(side="left")
    tk.Button(button_row, text="Load Selected", command=load_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Delete Selected", command=delete_selected).pack(side="left", padx=(8, 0))
    tk.Button(button_row, text="Refresh List", command=refresh_names).pack(side="left", padx=(8, 0))


def create_history_section(parent: tk.Frame, state: GuiState) -> None:
    frame = tk.LabelFrame(parent, text="Recent Exports", padx=8, pady=8)
    frame.pack(fill="x")
    tree_container = tk.Frame(frame)
    tree_container.pack(fill="both", expand=True)
    scrollbar = tk.Scrollbar(tree_container)
    scrollbar.pack(side="right", fill="y")

    columns = ("created", "profile", "included", "skipped", "git", "root")
    tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=8, yscrollcommand=scrollbar.set)
    for column, title, width, anchor in (
        ("created", "Created", 145, "w"), ("profile", "Profile", 65, "center"), ("included", "Included", 65, "center"),
        ("skipped", "Skipped", 65, "center"), ("git", "Git", 140, "center"), ("root", "Project Folder", 230, "w"),
    ):
        tree.heading(column, text=title)
        tree.column(column, width=width, anchor=anchor)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=tree.yview)

    entry_lookup: dict[str, storage.HistoryEntry] = {}

    def git_cell(entry: storage.HistoryEntry) -> str:
        if not entry.git_branch and not entry.git_commit_short:
            return ""
        branch = entry.git_branch or "(detached)"
        return f"{branch}@{entry.git_commit_short}" if entry.git_commit_short else branch

    def refresh_history() -> None:
        tree.delete(*tree.get_children())
        entry_lookup.clear()
        entries = storage.recent_entries(limit=20)
        if not entries:
            tree.insert("", "end", values=("No exports yet.", "", "", "", "", "Build a project context export to see it here."))
            return
        for entry in entries:
            item_id = tree.insert("", "end", values=(entry.created, entry.profile, entry.included_count, entry.skipped_count, git_cell(entry), entry.root))
            entry_lookup[item_id] = entry

    refresh_history()
    state.history_refresh = refresh_history

    def open_selected_export() -> None:
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Select a recent export first.")
            return
        entry = entry_lookup.get(selection[0])
        if entry is None:
            return
        export_dir = Path(entry.export_dir)
        if not export_dir.exists():
            messagebox.showerror("Folder Not Found", f"This export folder no longer exists:\n{export_dir}")
            return
        open_folder(export_dir)

    def clear_export_history() -> None:
        if not messagebox.askyesno("Clear History", "Remove all recorded export history?\n\nThis only clears this list. It does not delete any actual export files or folders."):
            return
        try:
            storage.clear_history()
        except Exception as exc:
            messagebox.showerror("Clear History Failed", str(exc))
            return
        refresh_history()

    buttons = tk.Frame(frame)
    buttons.pack(fill="x", pady=(8, 0))
    tk.Button(buttons, text="Open Selected Export Folder", command=open_selected_export).pack(side="left")
    tk.Button(buttons, text="Refresh", command=refresh_history).pack(side="left", padx=(8, 0))
    tk.Button(buttons, text="Clear History", command=clear_export_history).pack(side="left", padx=(8, 0))
