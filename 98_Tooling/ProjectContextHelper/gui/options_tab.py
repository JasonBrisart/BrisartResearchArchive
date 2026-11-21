"""
File: gui/options_tab.py

Purpose
-------
Build the scrollable Options tab: the output folder and size limits, the output-section and
  folder-opening checkboxes with a short description beside each, and the Advanced Filters
  section (included extensions, excluded folders, files, and suffixes, required completeness,
  and the Git history limit). Together with the Build and Extras tabs, every export setting
  has a control here or there, which is what lets a custom profile hold all of them. CPU
  Cores is on the Extras tab.

Communication / relationships
-----------------------------
Imports gui/state.py (GuiState, bind_visibility, optional_section) and gui/widgets.py
  (create_scrollable_area, create_text_field, MUTED). Imported by gui/window.py.

Settings / parameters
---------------------
The descriptions beside the checkboxes are the optional section options_help and the
  Advanced Filters box is options_advanced; the View tab can hide either, and hiding never
  changes a setting. The four lists are word-wrapped text boxes bound to GuiState's
  extensions_var, exclude_dirs_var, exclude_files_var, and exclude_suffixes_var; the text is
  parsed (and rejected if invalid) when a build or profile save starts, by gui/state.py.

Edge cases
----------
Typed size values and list contents are validated when a build starts, not while typing.
  Hiding the descriptions removes them from the grid and restores them in the same row.

Known limitations
-----------------
The output folder is checked for safety only when a build starts. The lists are shown as
  sorted comma-separated text, so a hand-written order or layout is not preserved.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.options_tab import create_options_tab
    from gui.state import make_gui_state

    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_options_tab(frame, make_gui_state())
    window.mainloop()
"""

import tkinter as tk

from gui.state import GuiState, bind_visibility, optional_section
from gui.widgets import MUTED, create_scrollable_area, create_text_field

def create_options_tab(
    parent: tk.Frame,
    state: GuiState,
) -> None:
    content = create_scrollable_area(parent)

    settings_frame = tk.LabelFrame(content, text="Export Settings", padx=12, pady=12)
    settings_frame.pack(fill="x", padx=16, pady=(16, 8))
    tk.Label(settings_frame, text="Output Folder:").grid(row=0, column=0, sticky="w", pady=4)
    tk.Entry(settings_frame, textvariable=state.output_dir_var, width=34).grid(row=0, column=1, sticky="w", pady=4)
    tk.Label(settings_frame, text="Max File MB:").grid(row=1, column=0, sticky="w", pady=4)
    tk.Entry(settings_frame, textvariable=state.max_file_mb_var, width=12).grid(row=1, column=1, sticky="w", pady=4)
    tk.Label(settings_frame, text="Max Total MB:").grid(row=2, column=0, sticky="w", pady=4)
    tk.Entry(settings_frame, textvariable=state.max_total_mb_var, width=12).grid(row=2, column=1, sticky="w", pady=4)
    tk.Label(settings_frame, text="Skipped Details Limit:").grid(row=3, column=0, sticky="w", pady=4)
    tk.Entry(settings_frame, textvariable=state.skipped_limit_var, width=12).grid(row=3, column=1, sticky="w", pady=4)

    checkbox_frame = tk.LabelFrame(content, text="Included Output Sections", padx=12, pady=12)
    checkbox_frame.pack(fill="x", padx=16, pady=(8, 8))
    options = [
        ("Create ZIP Snapshot", state.include_zip_var, "Creates PROJECT_SNAPSHOT.zip with generated files and included source files."),
        ("Redact Secret Lines", state.redact_var, "Replaces likely password/token/API-key lines with a redaction placeholder."),
        ("Include SHA256 Hashes", state.include_hashes_var, "Adds file checksums for integrity and archival verification."),
        ("Include Line Counts", state.include_line_counts_var, "Counts lines for included text files."),
        ("Include Folder Tree", state.include_tree_var, "Adds a readable project tree to PROJECT_CONTEXT.md."),
        ("Include File Index", state.include_index_var, "Adds a file table with size, lines, and optional hashes."),
        ("Include File Contents", state.include_contents_var, "Embeds the actual file contents into PROJECT_CONTEXT.md."),
        ("Include Skipped File Details", state.include_skipped_details_var, "Adds a capped skipped-file detail table to PROJECT_CONTEXT.md."),
        ("Timestamp Export Folder", state.timestamped_folder_var, "Creates a new timestamped export folder each run."),
        ("Open Export Folder After Build", state.open_after_build_var, "Opens the completed export folder when the build finishes."),
    ]
    for index, (label, variable, help_text) in enumerate(options):
        tk.Checkbutton(checkbox_frame, text=label, variable=variable).grid(row=index, column=0, sticky="w", pady=2)
        note = tk.Label(checkbox_frame, text=help_text, fg=MUTED, anchor="w", justify="left", wraplength=560)
        bind_visibility(
            state, "options_help",
            lambda note=note, row=index: note.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=2), note.grid_remove,
        )

    create_advanced_section(optional_section(state, "options_advanced", content, padx=16, pady=(0, 16)), state)


def create_advanced_section(parent: tk.Frame, state: GuiState) -> None:
    """Every setting without an everyday control: what is included, what is left out, and the strictness."""
    frame = tk.LabelFrame(parent, text="Advanced Filters", padx=12, pady=12)
    frame.pack(fill="x")
    frame.columnconfigure(1, weight=1)
    tk.Label(
        frame, fg=MUTED, anchor="w", justify="left", wraplength=640,
        text=(
            "Separate items with commas or new lines. Everything here is saved in custom profiles "
            "and in your remembered settings, and picking standard or archive on the Build tab "
            "restores the defaults."
        ),
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    fields = (
        ("Included extensions:", state.extensions_var, 4),
        ("Excluded folders:", state.exclude_dirs_var, 3),
        ("Excluded files:", state.exclude_files_var, 3),
        ("Excluded suffixes:", state.exclude_suffixes_var, 3),
    )
    for row, (label, variable, height) in enumerate(fields, start=1):
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", pady=4, padx=(0, 12))
        create_text_field(frame, variable, height).grid(row=row, column=1, sticky="ew", pady=4)
    tk.Checkbutton(
        frame, text="Stop the export if an eligible file cannot be captured", variable=state.require_complete_var,
    ).grid(row=len(fields) + 1, column=0, columnspan=2, sticky="w", pady=(8, 2))
    tk.Label(frame, text="Git History Limit:").grid(row=len(fields) + 2, column=0, sticky="w", pady=4)
    tk.Entry(frame, textvariable=state.git_limit_var, width=8).grid(row=len(fields) + 2, column=1, sticky="w", pady=4)
    tk.Label(
        frame, fg=MUTED, anchor="w", justify="left", wraplength=640,
        text=(
            "Removing an entry from Excluded files or Excluded folders removes its protection: "
            "clearing .env from the files list exports it."
        ),
    ).grid(row=len(fields) + 3, column=0, columnspan=2, sticky="w", pady=(6, 0))
