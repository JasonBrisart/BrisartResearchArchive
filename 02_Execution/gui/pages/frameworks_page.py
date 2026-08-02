from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import registries as framework_registry
from gui.theme import COLORS, FONT_HEAD
from gui.widgets.card import Card


def render(app):
    root = app.page_shell(
        "Frameworks",
        "Select, inspect, and launch registered framework modules.",
    )
    app.add_card(
        root, 2, "Framework Library",
        (
            "Available frameworks can be selected and launched directly. "
            "Reserved frameworks remain visible as planned platform modules."
        ),
        [
            ("Run Selected Framework", app.start_selected_framework, True),
            ("View Results", lambda: app.show_page("Results"), False),
            ("Refresh Registry", app.refresh_framework_registry, False),
        ],
    )

    grid = ttk.Frame(root, style="Bg.TFrame")
    grid.grid(row=3, column=0, sticky="ew", padx=26, pady=(4, 12))
    grid.grid_columnconfigure(0, weight=1)
    grid.grid_columnconfigure(1, weight=1)

    registry = list(framework_registry.FRAMEWORK_REGISTRY)
    for index, framework in enumerate(registry):
        row = index // 2
        column = index % 2
        card = Card(grid)
        card.grid(row=row, column=column, sticky="nsew", padx=(0, 9) if column == 0 else (9, 0), pady=9)
        card.grid_columnconfigure(0, weight=1)
        build_framework_card(app=app, card=card, framework=framework)


def build_framework_card(app, card, framework):
    framework_id = framework["id"]
    status = framework["status"]
    status_color = COLORS["success"] if status == "Available" else COLORS["warning"]

    header = ttk.Frame(card, style="Card.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    header.grid_columnconfigure(0, weight=1)
    tk.Label(
        header, text=framework_id, bg=COLORS["panel"], fg=COLORS["accent"],
        font=("Segoe UI", 18, "bold"),
    ).grid(row=0, column=0, sticky="w")
    tk.Label(
        header, text=status, bg=COLORS["panel"], fg=status_color,
        font=("Segoe UI", 10, "bold"),
    ).grid(row=0, column=1, sticky="e")

    tk.Label(
        card, text=framework["name"], bg=COLORS["panel"], fg=COLORS["text"], font=FONT_HEAD,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))
    ttk.Label(
        card, text=framework["description"], style="CardMuted.TLabel", wraplength=430, justify="left",
    ).grid(row=2, column=0, sticky="w", pady=(8, 10))

    if framework["features"]:
        feature_text = " | ".join(framework["features"][:4])
        ttk.Label(
            card, text=feature_text, style="Card.TLabel", wraplength=430, justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(0, 10))

    button_bar = ttk.Frame(card, style="Card.TFrame")
    button_bar.grid(row=4, column=0, sticky="w", pady=(4, 0))
    ttk.Button(
        button_bar, text="Select", command=lambda fid=framework_id: app.select_framework(fid),
        style="Accent.TButton" if status == "Available" else "TButton",
    ).pack(side="left", padx=(0, 8))
    if status == "Available":
        ttk.Button(
            button_bar, text="Run", command=lambda fid=framework_id: app.start_framework(fid),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_bar, text="Results", command=lambda: app.show_page("Results"),
        ).pack(side="left", padx=(0, 8))
    else:
        ttk.Button(button_bar, text="Reserved", state="disabled").pack(side="left", padx=(0, 8))
