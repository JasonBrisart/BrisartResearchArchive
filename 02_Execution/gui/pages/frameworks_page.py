"""
gui/pages/frameworks_page.py
The Frameworks page: one card per framework in
config.registries.FRAMEWORK_REGISTRY, one card per row (matching
gui/pages/tooling_page.py's single-column layout), partitioned into
"Available" (top) and "Available to Download" (bottom) groups, each
sorted alphabetically by name. Registered as the "Frameworks" page in
config.registries.get_page_registry().

This is a pure re-partition of FRAMEWORK_REGISTRY on every render, NOT
a persisted ordering -- when a framework's status changes, the group
it leaves naturally closes up (grid positions are recomputed fresh
from the partitioned+sorted list every render, never remembered).

NO "FRAMEWORK LIBRARY" CARD, specifically:
This page used to open with a "Framework Library" card containing
"Run Selected Framework" / "View Results" / "Refresh Registry"
buttons. That card, and those three actions, have been removed
entirely from this page -- the page now goes straight from the
subtitle into the Available/Available to Download cards. Those three
actions are still reachable elsewhere (the Dashboard page still has
"Run Selected Framework" and "Analyze Results"; the Results page still
has its own actions), so nothing is lost app-wide, just no longer
duplicated here.

SECTION / BADGE / BODY-TEXT WORDING, specifically:
Mirrors gui/pages/tooling_page.py's naming convention exactly, for
consistency between the two "top group / bottom group" pages in the
app:
  - Tooling: "Installed" (top) / "Available to Download" (bottom);
    per-card body text says "Installed version: X" or "Not installed."
  - Frameworks: "Available" (top) / "Available to Download" (bottom);
    per-card body text says "Not installed." for anything in the
    bottom group, exactly matching Tooling's wording, instead of the
    framework's raw "status" field text (e.g. "Coming Soon"). That raw
    status field still exists in config.registries.RESERVED_FRAMEWORKS
    and any future FRAMEWORK_METADATA a discovered framework module
    supplies, and is still what determines WHICH group a framework
    falls into (_is_available() below still checks for the literal
    "available" value) -- only the DISPLAYED wording changed.

ONE CARD PER ROW, specifically:
Previously each group was rendered as a 2-column grid
(_build_framework_grid(), with index // 2 / index % 2 row/column
math). That grid layout is gone -- each group is now a plain vertical
stack, one framework per row, identical in structure to
gui/pages/tooling_page.py's _build_tool_card() loop.

BUTTON STATE PER FRAMEWORK, specifically:
  - Available: "Run" + "Results" buttons only. The previous "Select"
    button (which set app.selected_framework, the variable Dashboard's
    "Run Selected Framework" button reads) has been removed from this
    page entirely -- "Run" here always calls app.start_framework(fid)
    directly for THIS card's specific framework, bypassing the
    selected-framework variable altogether, so removing "Select" does
    not change what clicking "Run" on a given card actually does.
    app.selected_framework itself still exists and is still read by
    the Dashboard's "Run Selected Framework" button; it just can no
    longer be changed away from its persisted/default value from this
    page -- only from wherever else in the app still sets it, if
    anywhere.
  - Available to Download (not yet available): a single disabled
    button showing NOT_YET_AVAILABLE_LABEL, matching the disabled-
    button treatment this page already had before.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config import registries as framework_registry
from gui.theme import COLORS, FONT_HEAD
from gui.widgets.card import Card

# Displayed section header / per-card badge text for any framework NOT
# currently available -- shown regardless of that framework's actual
# underlying "status" string (e.g. "Coming Soon"). See the module
# docstring's SECTION / BADGE / BODY-TEXT WORDING section for why.
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

    # Body text now matches gui/pages/tooling_page.py's wording exactly:
    # "Not installed." for anything not currently available, instead of
    # the framework's raw description-only text with no state line.
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
