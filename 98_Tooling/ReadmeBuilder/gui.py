"""
Tkinter GUI for ReadmeBuilder.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from constants import APP_NAME, APP_VERSION, AUTHOR, REPOSITORY_NAME, REPOSITORY_URL
from readme_builder import create_readme_draft


def run_gui() -> None:
    """
    Launch the Tkinter GUI.
    """
    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("700x455")
    root.minsize(630, 420)

    selected_dir = tk.StringVar(value=str(Path.cwd()))
    status = tk.StringVar(value="Select a project folder, then click Build README Draft.")

    def browse() -> None:
        folder = filedialog.askdirectory(
            initialdir=selected_dir.get(),
            title="Select project folder",
        )

        if folder:
            selected_dir.set(folder)

    def build() -> None:
        try:
            folder = Path(selected_dir.get())
            readme_path, analysis_path, manifest_path = create_readme_draft(folder)

            status.set(
                "Created:\n"
                f"{readme_path}\n"
                f"{analysis_path}\n"
                f"{manifest_path}"
            )

            messagebox.showinfo(
                "Done",
                "README draft and analysis files created successfully.",
            )

        except Exception as exc:
            status.set(f"Error: {exc}")
            messagebox.showerror("Error", str(exc))

    title = tk.Label(
        root,
        text=APP_NAME,
        font=("Segoe UI", 16, "bold"),
    )
    title.pack(pady=(14, 4))

    version = tk.Label(
        root,
        text=f"v{APP_VERSION}",
        font=("Segoe UI", 9),
    )
    version.pack(pady=(0, 2))

    author_label = tk.Label(
        root,
        text=f"Created by {AUTHOR}",
        font=("Segoe UI", 8),
        fg="gray",
        justify="center",
    )
    author_label.pack(pady=(0, 2))

    repo_label = tk.Label(
        root,
        text=f"{REPOSITORY_NAME}\n{REPOSITORY_URL}",
        font=("Segoe UI", 8),
        fg="gray",
        justify="center",
    )
    repo_label.pack(pady=(0, 8))

    info = tk.Label(
        root,
        text=(
            "Generate a GitHub-focused README_DRAFT.md plus a separate "
            "README_ANALYSIS.md for technical scan details."
        ),
        wraplength=630,
        justify="center",
    )
    info.pack(pady=6)

    frame = tk.Frame(root)
    frame.pack(pady=12, fill="x", padx=24)

    entry = tk.Entry(frame, textvariable=selected_dir)
    entry.pack(side="left", fill="x", expand=True)

    browse_button = tk.Button(frame, text="Browse", command=browse)
    browse_button.pack(side="left", padx=(8, 0))

    build_button = tk.Button(
        root,
        text="Build README Draft",
        command=build,
        height=2,
        width=30,
    )
    build_button.pack(pady=12)

    status_label = tk.Label(
        root,
        textvariable=status,
        wraplength=630,
        justify="left",
        anchor="w",
    )
    status_label.pack(pady=10, padx=24, fill="x")

    root.mainloop()