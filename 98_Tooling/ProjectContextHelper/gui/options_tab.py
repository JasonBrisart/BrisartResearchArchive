"""
File: gui/options_tab.py

Purpose
-------
Create the scrollable Options tab: export-size/output controls, the Performance section (CPU-core
  selector with a live core meter), and output-section/preference checkboxes.

Implemented responsibilities:
- create_options_tab: Create a scrollable settings panel with output folder, decimal-MB limits,
  detail cap, the Performance section, and ten bound output/preference checkboxes.
- create_performance_section: Build the CPU Cores selector (Auto plus 1..this machine's core
  limit), a row of core cells that fill to show how many cores the build will use, a usage
  readout, and an explanation; redraw both whenever the selection changes, including when a
  built-in or custom profile is applied.
- core_usage_text: Return the readout for a resolved count, e.g. "Using all 8 cores" or
  "Using 3 of 8 cores".
- redraw: Nested trace callback: resolve the selection with the same rule the scanner uses,
  repaint the meter cells, and update the readout.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: MAX_WORKERS.
- core.utils: resolve_workers, worker_limit.
- gui.builders: GuiState, core_label, label_to_workers, worker_choices.
- gui.scroll_frame: create_scrollable_area.

Consumers in the supplied source:
- gui/main_gui.py imports create_options_tab.
- tests/test_gui_wiring.py drives the selector through state.workers_var.

Settings / parameters
---------------------
Binds output folder, decimal-MB size limits, skipped-detail limit, CPU cores, ZIP, redaction,
  hashes, line counts, tree, index, contents, timestamps, and folder-opening controls to
  GuiState. The selector lists only counts this machine can run (a 4-core machine shows Auto and
  1-4, never 5-32). Meter cells are 14 px, or 11 px above 16 cores so 32 cells still fit the
  minimum window width; filled cells use ACCENT, idle cells use IDLE.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_options_tab(parent: tk.Frame, state: GuiState) -> None
- create_performance_section(parent: tk.Frame, state: GuiState) -> None
- core_usage_text(used: int, limit: int) -> str
- redraw(*_args) -> None

Module constants and expressions:
- ACCENT = '#2f6fde'
- IDLE = '#dde3ec'
- MUTED = '#666666'

Edge cases
----------
Input validation occurs when settings are built, not while typing. Scroll support is delegated
  to gui.scroll_frame. The CPU selector is read-only, so it cannot hold a value outside its list.

The output-folder field is stripped at build time and defaults to EXPORTS_DIRNAME when blank.
  The Open Export Folder checkbox is an application preference, not a serialized ScanSettings
  field. A one-core machine shows Auto (1 core) and 1 core. A machine reporting more than
  MAX_WORKERS cores shows a note that only MAX_WORKERS are used.

Known limitations
-----------------
Does not expose extension/exclusion sets, require_complete_source, or the Git history limit.
  Redaction does not remove original content from ZIP snapshots.

The options UI does not validate output path containment or update exclusion rules when the
  output folder name changes. Core counts are logical processors as reported by the OS; the
  meter shows threads requested, not live CPU load.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.builders import make_gui_state
    from gui.options_tab import create_options_tab

    window = tk.Tk()
    state = make_gui_state()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_options_tab(frame, state)
    window.mainloop()

    This constructs the component in an existing Tk application. For the complete
    four-tab interface, use python run.py rather than running this module directly.
"""

import tkinter as tk
from tkinter import ttk

from core.constants import MAX_WORKERS
from core.utils import resolve_workers, worker_limit
from gui.builders import (
    GuiState,
    core_label,
    label_to_workers,
    worker_choices,
)
from gui.scroll_frame import create_scrollable_area

ACCENT = "#2f6fde"
IDLE = "#dde3ec"
MUTED = "#666666"


def core_usage_text(used: int, limit: int) -> str:
    if limit == 1:
        return "Using 1 core"
    if used == limit:
        return f"Using all {limit} cores"
    return f"Using {used} of {limit} cores"


def create_performance_section(parent: tk.Frame, state: GuiState) -> None:
    limit = worker_limit(state.cpu_cores)
    frame = tk.LabelFrame(parent, text="Performance", padx=12, pady=12)
    frame.pack(fill="x", padx=16, pady=(8, 8))
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
            f"{detected} Each core reads project files in parallel, so more cores finish large "
            "exports faster. Auto always uses every available core on the computer it runs on. "
            "The core count never changes which files are included."
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

    create_performance_section(content, state)

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
        tk.Label(checkbox_frame, text=help_text, fg=MUTED, anchor="w", justify="left", wraplength=560).grid(row=index, column=1, sticky="w", padx=(12, 0), pady=2)

