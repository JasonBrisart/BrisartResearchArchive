"""
File: gui/build_tab.py

Purpose
-------
Build folder selection, built-in profile selection, export execution, and last-export-folder
  controls.

Implemented responsibilities:
- create_build_tab: Bind folder/profile widgets to shared state, register the profile-change
  callback, create build/open buttons, and define their session-local callbacks.
- browse: Open a directory chooser; on a nonempty selection, update selected_folder and
  status_text.
- refresh_profile_description: Respond to profile variable writes by applying built-in defaults
  and updating the explanatory profile label.
- build: On the Tk thread, validate inputs with prepare_build (showing Build Stopped/Build Failed
  immediately on bad input), disable the button, and start execute_build on the JobRunner.
- poll: Every 80 ms, drain worker events: show phase progress in the status bar; on completion
  re-enable the button, refresh Recent Exports, show the v3.1.4 dialogs, and optionally open the
  folder. Keeps polling while a close-time cancellation is in progress.
- finish: Map the worker outcome to the original dialogs: done -> Build Complete, ValueError ->
  Build Stopped, cancelled -> status only, anything else -> Build Failed.
- open_last_export: Show a no-export message when this session has no successful build;
  otherwise open state.last_export_dir.

Communication / relationships
-----------------------------
Internal imports and exchanged symbols:
- core.constants: VALID_PROFILES.
- gui.builders: GuiState, apply_profile_defaults, execute_build, prepare_build,
  profile_description.
- gui.dialogs: open_folder, show_build_complete, show_error, show_info, show_warning.

Consumers in the supplied source:
- gui/main_gui.py imports create_build_tab.

Settings / parameters
---------------------
Uses GuiState and the shared builder. Changing the built-in profile applies preset defaults;
  open_after_build is read when the build starts and controls post-build folder opening. Layout,
  labels, and dialogs are unchanged from v3.1.4.

Function signatures (nested callbacks are scoped to their enclosing function):
- create_build_tab(parent: tk.Frame, window: tk.Tk, state: GuiState) -> None
- browse() -> None
- refresh_profile_description(*_args) -> None
- finish(kind: str, payload: object, open_after: bool) -> None
- poll(open_after: bool) -> None
- build() -> None
- open_last_export() -> None

Edge cases
----------
An empty folder selection is rejected downstream. ValueError produces a build-stopped warning;
  other build exceptions show an error. Opening the last export requires a prior successful
  build in this session.

Canceling the folder chooser leaves state unchanged. The profile trace is attached after widget
  construction. A failed build does not replace the last successful session export path.
  Clicking Build while a build runs does nothing (the button is disabled). Dialogs are
  suppressed while the window is closing.

Known limitations
-----------------
Last-export-folder state is session-local, separate from persisted export history. There is no
  Cancel button (the v3.1.4 layout is kept); closing the window is the way to cancel a running
  build. Settings edits made while a build runs apply to the next build only.

Examples
--------
Usage from the directory containing run.py:

    import tkinter as tk
    from gui.builders import make_gui_state
    from gui.build_tab import create_build_tab

    window = tk.Tk()
    state = make_gui_state()
    frame = tk.Frame(window)
    frame.pack(fill="both", expand=True)
    create_build_tab(frame, window, state)
    window.mainloop()

    This constructs the component in an existing Tk application. For the complete
    four-tab interface, use python run.py rather than running this module directly.
"""

import tkinter as tk
from tkinter import filedialog, ttk

from core.constants import VALID_PROFILES
from gui.builders import (
    GuiState,
    apply_profile_defaults,
    execute_build,
    prepare_build,
    profile_description,
)
from gui.dialogs import (
    open_folder,
    show_build_complete,
    show_error,
    show_info,
    show_warning,
)


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
        quick_frame, textvariable=profile_description_var, justify="left", anchor="w", fg="#555555", wraplength=700,
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
            show_warning("Build Stopped", str(payload))
        else:
            state.status_text.set("Build failed.")
            show_error("Build Failed", str(payload))

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
            show_warning("Build Stopped", str(exc))
            return
        except Exception as exc:
            state.status_text.set("Build failed.")
            show_error("Build Failed", str(exc))
            return
        open_after = state.open_after_build_var.get()
        state.status_text.set("Building project context...")
        build_button.config(state="disabled")
        state.jobs.start(lambda cancel, emit: execute_build(folder, settings, cancel, emit))
        window.after(80, lambda: poll(open_after))

    build_button.config(command=build)

    def open_last_export() -> None:
        if state.last_export_dir is None:
            show_info("No Export Yet", "Build a project context export first.")
            return
        open_folder(state.last_export_dir)
    tk.Button(parent, text="Open Last Export Folder", command=open_last_export).pack(pady=(0, 8))

