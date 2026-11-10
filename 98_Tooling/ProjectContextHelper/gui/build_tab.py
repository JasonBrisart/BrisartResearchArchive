"""
File: gui/build_tab.py

Purpose
-------
Build the Build tab and run builds from the window: project folder selection, the built-in
  profile dropdown with its description, the Build Project Context button, and Open Last
  Export Folder. prepare_build validates on the Tk thread; execute_build runs the export on
  the background worker, then saves last-used settings and records history; the outcome
  becomes status bar text and dialogs.

Communication / relationships
-----------------------------
Imports export/pipeline.py (create_context, BuildResult), export/settings.py (profile names,
  ScanSettings), gui/state.py (GuiState, apply_profile_defaults, build_settings_from_state),
  gui/widgets.py (open_folder, show_build_complete, MUTED), and storage (save_last_settings,
  record_export). Imported by gui/window.py. Calls state.history_refresh, registered by
  gui/about_tab.py, after each successful build.

Settings / parameters
---------------------
Changing the profile applies that preset to every control. The worker queue is polled every
  80 ms. Open Export Folder After Build is read when the build starts.

Edge cases
----------
Validation errors (no folder, bad sizes) appear before any thread starts. During a build the
  button is disabled and the status bar shows the phase and file count. A ValueError from the
  build (such as a completeness stop) shows Build Stopped, cancellation only updates the
  status bar, and other errors show Build Failed. No dialogs appear while the window is
  closing. A failed build keeps the previous last-export folder and saves nothing.

Known limitations
-----------------
There is no Cancel button; closing the window cancels. The last export folder is remembered
  only for this session (history on the About tab persists). Edits made during a build apply
  to the next one. execute_build runs on the worker thread and must never touch Tk.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.build_tab import create_build_tab
    from gui.state import make_gui_state

    window = tk.Tk()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_build_tab(frame, window, make_gui_state())
    window.mainloop()
"""

from pathlib import Path
from threading import Event
from typing import Callable
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from export.pipeline import BuildResult, create_context
from export.settings import PROFILE_ARCHIVE, PROFILE_STANDARD, VALID_PROFILES, ScanSettings
from gui.state import GuiState, apply_profile_defaults, build_settings_from_state
from gui.widgets import MUTED, open_folder, show_build_complete
import storage


def profile_description(profile: str) -> str:
    if profile == PROFILE_STANDARD:
        return (
            "standard: quick everyday backup and project overview. "
            "Creates a ZIP snapshot, folder tree, and file index "
            "without hashes, line counts, full file contents, or "
            "skipped-file details."
        )
    if profile == PROFILE_ARCHIVE:
        return (
            "archive (default): maximum preservation mode. Includes "
            "all available export information with larger limits and "
            "enforced source completeness. Best for backups, long-term "
            "preservation, research archives, and full project records."
        )
    return "Unknown profile."


def prepare_build(state: GuiState) -> tuple[Path, ScanSettings]:
    folder = state.selected_folder.get().strip()
    if not folder:
        raise ValueError("Please select a project folder first.")
    return Path(folder), build_settings_from_state(state)


def execute_build(
    folder: Path,
    settings: ScanSettings,
    cancel: Event | None = None,
    progress: Callable | None = None,
) -> BuildResult:
    result = create_context(folder, settings=settings, cancel=cancel, progress=progress)
    storage.save_last_settings(settings)
    storage.record_export(result, settings)
    return result


def create_build_tab(
    parent: tk.Frame,
    window: tk.Tk,
    state: GuiState,
) -> None:
    folder_frame = tk.LabelFrame(parent, text="Project Folder", padx=12, pady=12)
    folder_frame.pack(fill="x", padx=16, pady=(16, 8))
    folder_entry = tk.Entry(folder_frame, textvariable=state.selected_folder)
    folder_entry.pack(side="left", fill="x", expand=True)

    def browse() -> None:
        folder = filedialog.askdirectory(title="Select project folder")
        if folder:
            state.selected_folder.set(folder)
            state.status_text.set("Folder selected.")
    tk.Button(folder_frame, text="Browse", command=browse).pack(side="left", padx=(8, 0))

    quick_frame = tk.LabelFrame(parent, text="Quick Export", padx=12, pady=12)
    quick_frame.pack(fill="x", padx=16, pady=(8, 8))
    tk.Label(quick_frame, text="Profile:").grid(row=0, column=0, sticky="w", pady=4)
    profile_menu = ttk.Combobox(
        quick_frame, textvariable=state.profile_var, values=sorted(VALID_PROFILES), state="readonly", width=18,
    )
    profile_menu.grid(row=0, column=1, sticky="w", pady=4)
    profile_description_var = tk.StringVar(value=profile_description(state.profile_var.get()))
    tk.Label(
        quick_frame, textvariable=profile_description_var, justify="left", anchor="w", fg=MUTED, wraplength=700,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def refresh_profile_description(*_args) -> None:
        apply_profile_defaults(state)
        profile_description_var.set(profile_description(state.profile_var.get()))
    state.profile_var.trace_add("write", refresh_profile_description)

    tk.Label(
        parent, justify="left", anchor="w", font=("Segoe UI", 10),
        text=(
            "Generated outputs:\n"
            "\u2022 PROJECT_CONTEXT.md\n"
            "\u2022 PROJECT_MANIFEST.json\n"
            "\u2022 PROJECT_SUMMARY.txt\n"
            "\u2022 PROJECT_CONTEXT_SETTINGS.json\n"
            "\u2022 PROJECT_SNAPSHOT.zip (optional)"
        ),
    ).pack(fill="x", padx=18, pady=(10, 0))

    build_button = tk.Button(
        parent, text="Build Project Context", height=2, font=("Segoe UI", 12, "bold"),
    )
    build_button.pack(pady=18)

    def finish(kind: str, payload: object, open_after: bool) -> None:
        build_button.config(state="normal")
        if state.closing:
            return
        if kind == "done":
            result = payload
            state.last_export_dir = result.export_dir
            state.status_text.set(f"Done. Included {result.included_count} files.")
            if state.history_refresh is not None:
                state.history_refresh()
            show_build_complete(result)
            if open_after:
                open_folder(result.export_dir)
        elif kind == "cancelled":
            state.status_text.set("Build cancelled.")
        elif isinstance(payload, ValueError):
            state.status_text.set("Build stopped.")
            messagebox.showwarning("Build Stopped", str(payload))
        else:
            state.status_text.set("Build failed.")
            messagebox.showerror("Build Failed", str(payload))

    def poll(open_after: bool) -> None:
        for kind, payload in state.jobs.drain():
            if kind == "progress":
                count = f" {payload.completed}/{payload.total}" if payload.total else ""
                state.status_text.set(f"Building project context... {payload.phase}{count}")
            else:
                finish(kind, payload, open_after)
                return
        window.after(80, lambda: poll(open_after))

    def build() -> None:
        if state.jobs.busy:
            return
        try:
            folder, settings = prepare_build(state)
        except ValueError as exc:
            state.status_text.set("Build stopped.")
            messagebox.showwarning("Build Stopped", str(exc))
            return
        except Exception as exc:
            state.status_text.set("Build failed.")
            messagebox.showerror("Build Failed", str(exc))
            return
        open_after = state.open_after_build_var.get()
        state.status_text.set("Building project context...")
        build_button.config(state="disabled")
        state.jobs.start(lambda cancel, emit: execute_build(folder, settings, cancel, emit))
        window.after(80, lambda: poll(open_after))

    build_button.config(command=build)

    def open_last_export() -> None:
        if state.last_export_dir is None:
            messagebox.showinfo("No Export Yet", "Build a project context export first.")
            return
        open_folder(state.last_export_dir)
    tk.Button(parent, text="Open Last Export Folder", command=open_last_export).pack(pady=(0, 8))
