import tkinter as tk
from tkinter import ttk

from gui.theme import COLORS, FONT_MONO
from gui.widgets.card import Card


def render(app):
    root = app.page_shell(
        "System",
        "Application configuration, update management, output paths, framework registry, and advanced platform options.",
    )
    app.add_card(
        root, 2, "General",
        (
            f"Application: {app.app_name}\n"
            f"Version: {app.app_version}\n"
            f"Execution Folder:\n{app.execution_dir}\n\n"
            f"Selected Framework: {app.selected_framework.get()}"
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

    registry_card = Card(root)
    registry_card.grid(row=4, column=0, sticky="ew", padx=26, pady=9)
    registry_card.grid_columnconfigure(0, weight=1)
    ttk.Label(registry_card, text="Framework Registry", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        registry_card,
        text=(
            "Refresh framework discovery after adding, removing, or editing "
            "framework modules. Useful for plugin-style development without "
            "restarting the whole GUI."
        ),
        style="CardMuted.TLabel", wraplength=950, justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(7, 10))
    ttk.Button(
        registry_card, text="Refresh Framework Registry", command=app.refresh_framework_registry,
        style="Accent.TButton",
    ).grid(row=2, column=0, sticky="w")

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
        root, 7, "Framework Paths",
        (
            "Future location for installed framework discovery, "
            "framework-module paths, private institutional modules, "
            "and archive-wide plugin configuration."
        ),
    )
    app.add_card(
        root, 8, "ARLA Standards",
        (
            "Future location for:\n\n"
            "- ARLA Data Standard\n"
            "- ARLA Assay Standard\n"
            "- ARLA Validation Standard\n"
            "- ARLA Analyzer Standard"
        ),
    )
    app.add_card(
        root, 9, "Advanced",
        (
            "Future configuration may include framework registry toggles, "
            "private module paths, institutional profile settings, local "
            "export preferences, update channels, and lab-specific runtime "
            "defaults."
        ),
    )
