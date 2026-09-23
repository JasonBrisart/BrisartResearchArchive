import tkinter as tk
from tkinter import filedialog, ttk

from core.constants import VALID_PROFILES
from gui.builders import (
    GuiState,
    apply_profile_defaults,
    profile_description,
    run_project_build,
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

    def build() -> None:
        state.status_text.set("Building project context...")
        window.update_idletasks()
        try:
            result = run_project_build(state)
        except ValueError as exc:
            state.status_text.set("Build stopped.")
            show_warning("Build Stopped", str(exc))
            return
        except Exception as exc:
            state.status_text.set("Build failed.")
            show_error("Build Failed", str(exc))
            return
        state.status_text.set(f"Done. Included {result.included_count} files.")
        show_build_complete(result)
        if state.open_after_build_var.get():
            open_folder(result.export_dir)
    tk.Button(
        parent, text="Build Project Context", command=build, height=2, font=("Segoe UI", 12, "bold"),
    ).pack(pady=18)

    def open_last_export() -> None:
        if state.last_export_dir is None:
            show_info("No Export Yet", "Build a project context export first.")
            return
        open_folder(state.last_export_dir)
    tk.Button(parent, text="Open Last Export Folder", command=open_last_export).pack(pady=(0, 8))
