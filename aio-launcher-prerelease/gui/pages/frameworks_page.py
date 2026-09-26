"""
File: gui/pages/frameworks_page.py

Purpose:
Render one card per registered framework, split into an "Available"
group at the top and an "Available to Download" group at the bottom,
each sorted alphabetically by name.

Communication / relationships:
- Registered as "Frameworks" in config/registries.get_page_registry().
- Reads config/registries.FRAMEWORK_REGISTRY on every render.
- Run calls app.start_framework(framework_id), which reaches
  services/framework_service.py through SystemController.
- Results calls app.show_page("Results").

Settings / parameters:
- NOT_YET_AVAILABLE_LABEL: "Available to Download".
- A framework belongs to the top group when its status is "available"
  (case-insensitive).
- The features line shows the first four features.

Edge cases:
- Groups are recomputed on every render; nothing is persisted.
- The divider appears only when both groups are non-empty.
- Unavailable frameworks show "Not installed." and a disabled button,
  whatever their raw status text (for example "Coming Soon").

Known limitations:
- Run launches that card's framework directly, independent of
  app.selected_framework.
- The fixed 950-pixel wraplength does not reflow on resize.
- Reserved frameworks cannot actually be downloaded yet; the label
  describes future behavior.

Examples:
- app.show_page("Frameworks")
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from config import registries as framework_registry
from gui.theme import COLORS, FONT_HEAD
from gui.widgets.card import Card
# Displayed section header / per-card badge text for any framework NOT
# currently available -- shown regardless of its underlying "status"
# string (e.g. "Coming Soon").
NOT_YET_AVAILABLE_LABEL = "Available to Download"
def _sort_alphabetically(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda entry: str(entry.get("name", "")).casefold())
def _is_available(framework: dict) -> bool:
    return str(framework.get("status", "")).strip().casefold() == "available"
def _partition_registry_by_availability(registry: list[dict]) -> tuple[list[dict], list[dict]]:
    available = _sort_alphabetically([f for f in registry if _is_available(f)])
    not_yet_available = _sort_alphabetically([f for f in registry if not _is_available(f)])
    return available, not_yet_available
def _build_section_header(root: ttk.Frame, row: int, text: str) -> None:
    ttk.Label(root, text=text, style="CardTitle.TLabel").grid(
        row=row, column=0, sticky="w", padx=26, pady=(18, 6)
    )
def _build_divider(root: ttk.Frame, row: int) -> None:
    tk.Frame(root, bg=COLORS["border"], height=1).grid(
        row=row, column=0, sticky="ew", padx=26, pady=(4, 10)
    )
def render(app):
    root = app.page_shell(
        "Frameworks",
        "Select, inspect, and launch registered framework modules.",
    )
    registry = list(framework_registry.FRAMEWORK_REGISTRY)
    available_frameworks, not_yet_available_frameworks = _partition_registry_by_availability(registry)
    row = 2
    if available_frameworks:
        _build_section_header(root, row, "Available")
        row += 1
        for framework in available_frameworks:
            _build_framework_card(app, root, row=row, framework=framework)
            row += 1
    if available_frameworks and not_yet_available_frameworks:
        _build_divider(root, row)
        row += 1
    if not_yet_available_frameworks:
        _build_section_header(root, row, NOT_YET_AVAILABLE_LABEL)
        row += 1
        for framework in not_yet_available_frameworks:
            _build_framework_card(app, root, row=row, framework=framework)
            row += 1
def _build_framework_card(app, root, row: int, framework: dict) -> None:
    framework_id = framework["id"]
    is_available = _is_available(framework)
    status_label = "Available" if is_available else NOT_YET_AVAILABLE_LABEL
    status_color = COLORS["success"] if is_available else COLORS["warning"]
    card = Card(root)
    card.grid(row=row, column=0, sticky="ew", padx=26, pady=9)
    card.grid_columnconfigure(0, weight=1)
    header = ttk.Frame(card, style="Card.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    header.grid_columnconfigure(0, weight=1)
    tk.Label(
        header, text=framework_id, bg=COLORS["panel"], fg=COLORS["accent"],
        font=("Segoe UI", 18, "bold"),
    ).grid(row=0, column=0, sticky="w")
    tk.Label(
        header, text=status_label, bg=COLORS["panel"], fg=status_color,
        font=("Segoe UI", 10, "bold"),
    ).grid(row=0, column=1, sticky="e")
    tk.Label(
        card, text=framework["name"], bg=COLORS["panel"], fg=COLORS["text"], font=FONT_HEAD,
    ).grid(row=1, column=0, sticky="w", pady=(8, 0))
    # Anything not currently available gets an explicit "Not installed."
    # line under its description so the card never reads as runnable.
    body_text = framework["description"]
    if not is_available:
        body_text = f"{body_text}\n\nNot installed."
    ttk.Label(
        card, text=body_text, style="CardMuted.TLabel", wraplength=950, justify="left",
    ).grid(row=2, column=0, sticky="w", pady=(8, 10))
    if framework["features"]:
        feature_text = " | ".join(framework["features"][:4])
        ttk.Label(
            card, text=feature_text, style="Card.TLabel", wraplength=950, justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(0, 10))
    button_bar = ttk.Frame(card, style="Card.TFrame")
    button_bar.grid(row=4, column=0, sticky="w", pady=(4, 0))
    if is_available:
        ttk.Button(
            button_bar, text="Run", style="Accent.TButton",
            command=lambda fid=framework_id: app.start_framework(fid),
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            button_bar, text="Results", command=lambda: app.show_page("Results"),
        ).pack(side="left", padx=(0, 8))
    else:
        ttk.Button(button_bar, text=NOT_YET_AVAILABLE_LABEL, state="disabled").pack(side="left", padx=(0, 8))
