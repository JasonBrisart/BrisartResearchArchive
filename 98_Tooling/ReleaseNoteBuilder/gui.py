"""
Tkinter GUI for ReleaseNoteBuilder.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from constants import (
    APP_NAME,
    APP_VERSION,
    AUTHOR,
    REPOSITORY_NAME,
    REPOSITORY_URL,
    APPLICATION_TAGLINE,
)

from release_note_builder import create_release_notes


def run_gui() -> None:
    root = tk.Tk()
    root.title(f"{APP_NAME} v{APP_VERSION}")
    root.geometry("780x460")

    old_folder_var = tk.StringVar()
    new_folder_var = tk.StringVar()
    output_folder_var = tk.StringVar()
    version_var = tk.StringVar(value="v1.0.0")

    def browse_old():
        folder = filedialog.askdirectory(title="Select old version folder")
        if folder:
            old_folder_var.set(folder)

    def browse_new():
        folder = filedialog.askdirectory(title="Select new version folder")
        if folder:
            new_folder_var.set(folder)

    def browse_output():
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            output_folder_var.set(folder)

    def build():
        old_folder = old_folder_var.get().strip()
        new_folder = new_folder_var.get().strip()
        output_folder = output_folder_var.get().strip()
        version_label = version_var.get().strip() or "Unversioned Release"

        if not old_folder:
            messagebox.showerror(
                "Missing Folder",
                "Please select the old version folder.",
            )
            return

        if not new_folder:
            messagebox.showerror(
                "Missing Folder",
                "Please select the new version folder.",
            )
            return

        if not output_folder:
            output_folder = new_folder
            output_folder_var.set(output_folder)

        try:
            outputs = create_release_notes(
                old_folder=old_folder,
                new_folder=new_folder,
                output_folder=output_folder,
                version_label=version_label,
            )

            messagebox.showinfo(
                "Release Notes Created",
                "ReleaseNoteBuilder generated:\n\n"
                f"{outputs['release_notes']}\n"
                f"{outputs['changelog']}\n"
                f"{outputs['manifest']}",
            )

        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    padding = {"padx": 12, "pady": 8}

    title = tk.Label(
        root,
        text=f"{APP_NAME} v{APP_VERSION}",
        font=("Segoe UI", 18, "bold"),
    )
    title.pack(pady=(18, 4))

    subtitle = tk.Label(
        root,
        text=(
            "Part of BrisartDevTools\n\n"
            f"{APPLICATION_TAGLINE}"
        ),
        wraplength=700,
        justify="center",
    )
    subtitle.pack(pady=(0, 14))

    frame = tk.Frame(root)
    frame.pack(fill="x", padx=20)

    tk.Label(frame, text="Old Version Folder").grid(
        row=0,
        column=0,
        sticky="w",
        **padding,
    )

    tk.Entry(
        frame,
        textvariable=old_folder_var,
        width=72,
    ).grid(
        row=0,
        column=1,
        **padding,
    )

    tk.Button(
        frame,
        text="Browse",
        command=browse_old,
    ).grid(
        row=0,
        column=2,
        **padding,
    )

    tk.Label(frame, text="New Version Folder").grid(
        row=1,
        column=0,
        sticky="w",
        **padding,
    )

    tk.Entry(
        frame,
        textvariable=new_folder_var,
        width=72,
    ).grid(
        row=1,
        column=1,
        **padding,
    )

    tk.Button(
        frame,
        text="Browse",
        command=browse_new,
    ).grid(
        row=1,
        column=2,
        **padding,
    )

    tk.Label(frame, text="Output Folder").grid(
        row=2,
        column=0,
        sticky="w",
        **padding,
    )

    tk.Entry(
        frame,
        textvariable=output_folder_var,
        width=72,
    ).grid(
        row=2,
        column=1,
        **padding,
    )

    tk.Button(
        frame,
        text="Browse",
        command=browse_output,
    ).grid(
        row=2,
        column=2,
        **padding,
    )

    tk.Label(frame, text="Version Label").grid(
        row=3,
        column=0,
        sticky="w",
        **padding,
    )

    tk.Entry(
        frame,
        textvariable=version_var,
        width=72,
    ).grid(
        row=3,
        column=1,
        **padding,
    )

    button = tk.Button(
        root,
        text="Generate Release Notes",
        font=("Segoe UI", 12, "bold"),
        command=build,
        height=2,
    )
    button.pack(pady=22)

    footer = tk.Label(
        root,
        text=(
            f"{APP_NAME} v{APP_VERSION}\n"
            f"Author: {AUTHOR}\n"
            f"Part of {REPOSITORY_NAME}\n"
            f"{REPOSITORY_URL}"
        ),
        fg="gray",
        justify="center",
    )
    footer.pack(pady=(0, 8))

    root.mainloop()