"""
Tkinter GUI for AutoExeBuilder.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from build_profiles import BuildProfile
from constants import APP_NAME, APP_VERSION, APPLICATION_TAGLINE, AUTHOR, REPOSITORY_NAME, REPOSITORY_URL
from filesystem import ensure_output_folder, humanize_project_name, safe_exe_name, validate_project_folder
from project_scanner import get_entrypoint_options, scan_project
from pyinstaller_backend import is_pyinstaller_available
from auto_exe_builder import build_exe_from_profile


def run_gui() -> None:
    """
    Launch the AutoExeBuilder GUI.
    """
    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("820x620")
    root.minsize(760, 560)

    selected_project = tk.StringVar(value=str(Path.cwd()))
    selected_entrypoint = tk.StringVar(value="")
    output_folder = tk.StringVar(value="")
    exe_name = tk.StringVar(value="")
    icon_path = tk.StringVar(value="")

    onefile = tk.BooleanVar(value=True)
    windowed = tk.BooleanVar(value=True)
    clean_build = tk.BooleanVar(value=True)

    status = tk.StringVar(value="Select a project folder, scan it, then build the executable.")

    entrypoint_combo: ttk.Combobox | None = None

    def set_status(text: str) -> None:
        status.set(text)
        root.update_idletasks()

    def browse_project() -> None:
        folder = filedialog.askdirectory(
            initialdir=selected_project.get(),
            title="Select Python project folder",
        )
        if folder:
            selected_project.set(folder)
            output_folder.set("")
            exe_name.set("")
            selected_entrypoint.set("")
            set_status("Project selected. Click Scan Project.")

    def browse_output() -> None:
        folder = filedialog.askdirectory(
            initialdir=selected_project.get(),
            title="Select output folder",
        )
        if folder:
            output_folder.set(folder)

    def browse_icon() -> None:
        file_path = filedialog.askopenfilename(
            initialdir=selected_project.get(),
            title="Select optional .ico file",
            filetypes=[("Icon files", "*.ico"), ("All files", "*.*")],
        )
        if file_path:
            icon_path.set(file_path)

    def scan_selected_project() -> None:
        nonlocal entrypoint_combo

        try:
            project_root = validate_project_folder(selected_project.get())
            scan = scan_project(project_root)
            options = get_entrypoint_options(scan)

            if not exe_name.get().strip():
                exe_name.set(safe_exe_name(humanize_project_name(project_root)))

            if not output_folder.get().strip():
                output_folder.set(str(ensure_output_folder(project_root)))

            if entrypoint_combo is not None:
                entrypoint_combo["values"] = options

            if options:
                selected_entrypoint.set(scan.get("suggested_entrypoint") or options[0])
                set_status(
                    "Scan complete.\n"
                    f"Python files scanned: {scan.get('python_files_scanned')}\n"
                    f"Suggested entry point: {selected_entrypoint.get()}"
                )
            else:
                selected_entrypoint.set("")
                set_status("Scan complete, but no Python entry points were detected.")

        except Exception as exc:
            messagebox.showerror("Scan Error", str(exc))
            set_status(f"Scan failed: {exc}")

    def build_selected_project() -> None:
        try:
            project_root = validate_project_folder(selected_project.get())

            if not selected_entrypoint.get().strip():
                raise ValueError("No entry point selected. Scan the project or choose a Python file.")

            output_root = ensure_output_folder(project_root, output_folder.get().strip() or None)

            profile = BuildProfile(
                project_root=str(project_root),
                entrypoint=selected_entrypoint.get().strip(),
                output_folder=str(output_root),
                executable_name=safe_exe_name(exe_name.get()),
                onefile=onefile.get(),
                windowed=windowed.get(),
                clean_build=clean_build.get(),
                confirm_overwrite=False,
                icon_path=icon_path.get().strip(),
            )

            set_status("Building executable. The build output will appear when finished inside the app status area.")

            result = build_exe_from_profile(profile)

            if result["build_result"].get("success"):
                messagebox.showinfo(
                    "Build Complete",
                    "Executable build completed successfully.\n\n"
                    f"Expected executable:\n{result['outputs']['expected_executable']}",
                )
            else:
                messagebox.showwarning(
                    "Build Failed",
                    "AutoExeBuilder could not complete the executable build.\n\n"
                    "Review EXE_BUILD_NOTES.md for details.",
                )

            set_status(
                f"Build status: {'success' if result['build_result'].get('success') else 'failed'}\n"
                f"Expected executable: {result['outputs']['expected_executable']}\n"
                f"Build notes: {result['outputs']['notes']}"
            )

        except Exception as exc:
            messagebox.showerror("Build Error", str(exc))
            set_status(f"Build failed: {exc}")

    title = tk.Label(
        root,
        text=f"{APP_NAME} v{APP_VERSION}",
        font=("Segoe UI", 18, "bold"),
    )
    title.pack(pady=(16, 4))

    subtitle = tk.Label(
        root,
        text=APPLICATION_TAGLINE,
        wraplength=740,
        justify="center",
    )
    subtitle.pack(pady=(0, 8))

    backend_text = (
        "PyInstaller detected in current Python environment."
        if is_pyinstaller_available()
        else "PyInstaller not detected. Install with: py -m pip install pyinstaller"
    )

    backend_label = tk.Label(
        root,
        text=backend_text,
        fg="green" if is_pyinstaller_available() else "dark red",
        wraplength=740,
        justify="center",
    )
    backend_label.pack(pady=(0, 12))

    form = tk.Frame(root)
    form.pack(fill="x", padx=24)

    padding = {"padx": 8, "pady": 7}

    tk.Label(form, text="Project Folder").grid(row=0, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=selected_project, width=78).grid(row=0, column=1, sticky="ew", **padding)
    tk.Button(form, text="Browse", command=browse_project).grid(row=0, column=2, **padding)

    tk.Label(form, text="Entry Point").grid(row=1, column=0, sticky="w", **padding)
    entrypoint_combo = ttk.Combobox(form, textvariable=selected_entrypoint, width=75)
    entrypoint_combo.grid(row=1, column=1, sticky="ew", **padding)
    tk.Button(form, text="Scan Project", command=scan_selected_project).grid(row=1, column=2, **padding)

    tk.Label(form, text="Output Folder").grid(row=2, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=output_folder, width=78).grid(row=2, column=1, sticky="ew", **padding)
    tk.Button(form, text="Browse", command=browse_output).grid(row=2, column=2, **padding)

    tk.Label(form, text="Executable Name").grid(row=3, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=exe_name, width=78).grid(row=3, column=1, sticky="ew", **padding)

    tk.Label(form, text="Optional Icon").grid(row=4, column=0, sticky="w", **padding)
    tk.Entry(form, textvariable=icon_path, width=78).grid(row=4, column=1, sticky="ew", **padding)
    tk.Button(form, text="Browse", command=browse_icon).grid(row=4, column=2, **padding)

    options = tk.LabelFrame(root, text="Build Options")
    options.pack(fill="x", padx=24, pady=(14, 8))

    tk.Checkbutton(options, text="One-file executable", variable=onefile).pack(anchor="w", padx=12, pady=4)
    tk.Checkbutton(options, text="Windowed app / no console", variable=windowed).pack(anchor="w", padx=12, pady=4)
    tk.Checkbutton(options, text="Clean build cache before building", variable=clean_build).pack(anchor="w", padx=12, pady=4)

    build_button = tk.Button(
        root,
        text="Build EXE",
        command=build_selected_project,
        height=2,
        width=30,
        font=("Segoe UI", 11, "bold"),
    )
    build_button.pack(pady=(12, 8))

    status_label = tk.Label(
        root,
        textvariable=status,
        justify="left",
        anchor="w",
        wraplength=740,
    )
    status_label.pack(fill="x", padx=24, pady=(4, 10))

    footer = tk.Label(
        root,
        text=(
            f"Created by {AUTHOR}\n"
            f"Part of {REPOSITORY_NAME}\n"
            f"{REPOSITORY_URL}"
        ),
        fg="gray",
        justify="center",
        font=("Segoe UI", 8),
    )
    footer.pack(pady=(0, 8))

    form.columnconfigure(1, weight=1)

    root.mainloop()