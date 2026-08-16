import tkinter as tk
from tkinter import ttk

from gui.theme import COLORS, FONT_MONO
from gui.widgets.card import Card


def render(app):
    root = app.page_shell(
        "System",
        "Application configuration, update management, output paths, and activity log.",
    )
    app.add_card(
        root, 2, "General",
        (
            f"Application: {app.app_name}\n"
            f"Version: {app.app_version}\n"
            f"Execution Folder:\n{app.execution_dir}"
        ),
    )
    output_card = Card(root)
    output_card.grid(row=3, column=0, sticky="ew", padx=26, pady=9)
    output_card.grid_columnconfigure(1, weight=1)
    ttk.Label(output_card, text="Output Directory", style="CardTitle.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w"
    )
    ttk.Label(
        output_card,
        text="Default location for future archive-wide outputs, reports, and exports.",
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 10))
    ttk.Entry(output_card, textvariable=app.output_folder).grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(0, 4)
    )
    ttk.Button(output_card, text="Browse", command=app.browse_output_folder).grid(
        row=2, column=2, padx=(8, 0), pady=(0, 4)
    )
    ttk.Button(output_card, text="Open Folder", command=app.open_output_folder).grid(
        row=3, column=2, padx=(8, 0), pady=(0, 8)
    )
    updates_card = Card(root)
    updates_card.grid(row=5, column=0, sticky="ew", padx=26, pady=9)
    updates_card.grid_columnconfigure(0, weight=1)
    ttk.Label(updates_card, text="Updates", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        updates_card,
        text="Update checks are user-controlled. If disabled, the GUI update service will not contact GitHub.",
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=1, column=0, sticky="w", pady=(7, 10))
    ttk.Checkbutton(
        updates_card, text="Enable update checks", variable=app.enable_update_checks,
    ).grid(row=2, column=0, sticky="w", pady=(0, 10))
    ttk.Button(
        updates_card, text="Check Updates", command=app.check_updates, style="Accent.TButton",
    ).grid(row=3, column=0, sticky="w")
    app.update_box = tk.Text(
        root, height=12, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.update_box.grid(row=6, column=0, sticky="ew", padx=26, pady=10)
    app.update_box.insert("end", "Update output will appear here.\n")
    app.add_card(
        root, 7, "Activity Log",
        "Recent application activity: framework launches, autosaves, registry refreshes, and errors.",
    )
    app.log_box = tk.Text(
        root, height=10, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.log_box.grid(row=8, column=0, sticky="ew", padx=26, pady=(0, 10))
    app.log_box.insert("end", "Activity log ready.\n")
