import tkinter as tk

from gui.builders import GuiState
from gui.scroll_frame import create_scrollable_area


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
    checkbox_frame.pack(fill="x", padx=16, pady=(8, 16))
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
        tk.Label(checkbox_frame, text=help_text, fg="#666666", anchor="w", justify="left", wraplength=560).grid(row=index, column=1, sticky="w", padx=(12, 0), pady=2)
