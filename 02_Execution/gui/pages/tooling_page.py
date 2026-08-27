"""
gui/pages/tooling_page.py
The Tooling page: one card per program listed in config/tooling_catalog.py.
Registered as the "Tooling" page in config.registries.get_page_registry()
and rendered by gui.main_window.BrisartSuiteApp.show_page("Tooling").

INSTALLED / NOT-INSTALLED GROUPING + ALPHABETICAL ORDER, specifically:
Every catalog entry is partitioned into "Installed" (top) and
"Available to Download" (bottom) groups on every render(), each sorted
alphabetically by name. This is a pure re-partition of
config.tooling_catalog.TOOLING_CATALOG on every render, NOT a
persisted ordering -- there is no separate "sort order" state to keep
in sync. When an entry moves between groups, the group that lost it
naturally closes up (every remaining card's row shifts by one) on this
same render pass, since grid rows are assigned by enumerating the
freshly partitioned+sorted list, never by a remembered position.

NO MANUAL "CHECK FOR UPDATES" CONTROL ON THIS PAGE, specifically:
This page used to have its own "Check for Tool Updates" button. It was
removed because Tooling update checking is governed entirely by the
same auto-update settings on the Settings page that govern the
Archive's own self-updates ("Enable update checks", "Notify me about
updates", "Automatically download and install updates") -- see
gui/main_window.py's TOOLING UPDATE CHECK docstring section and
controllers/system_controller.py's check_tool_updates() for exactly
how that gating works. Having a second, independent "check now" button
here -- one that ran regardless of the Settings page's "Enable update
checks" toggle -- would have silently contradicted that master switch:
turning update checks off in Settings should mean off everywhere,
including Tooling, not "off, except still available here." If a
manual on-demand recheck is ever wanted again, it should be added back
here as a call to app.check_tool_updates() specifically because that
method now already honors the Settings-page gate.

BUTTON STATE PER PROGRAM, specifically:
  - Not installed: single "Download" button.
  - Installed, no known update: "Run" + "Open Folder" buttons.
  - Installed, WITH a known update (present in
    app.tool_update_availability): "Update to vX.Y.Z" + "Run" +
    "Open Folder" -- the update is offered as an ADDITIONAL button
    alongside Run/Open Folder, not a replacement, so an already-useful
    install is never hidden behind an update prompt.
Since this page's widgets are destroyed and fully rebuilt on every
show_page("Tooling") call (see gui/main_window.py's clear()/show_page()
pattern, used identically by every other page), a state change (a
download completing, an update finishing) is reflected simply by
calling app.show_page("Tooling") again after the background operation
finishes -- there is no in-place widget mutation to keep in sync.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config.tooling_catalog import TOOLING_CATALOG
from config.tooling_state import get_tool_record, is_tool_installed
from gui.theme import COLORS
from gui.widgets.card import Card


def _sort_alphabetically(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda entry: str(entry.get("name", "")).casefold())


def _partition_catalog_by_install_state(catalog: list[dict]) -> tuple[list[dict], list[dict]]:
    installed_entries = _sort_alphabetically([e for e in catalog if is_tool_installed(e["id"])])
    not_installed_entries = _sort_alphabetically([e for e in catalog if not is_tool_installed(e["id"])])
    return installed_entries, not_installed_entries


def _build_section_header(root: ttk.Frame, row: int, text: str) -> None:
    ttk.Label(root, text=text, style="CardTitle.TLabel").grid(
        row=row, column=0, sticky="w", padx=26, pady=(18, 6)
    )


def _build_divider(root: ttk.Frame, row: int) -> None:
    tk.Frame(root, bg=COLORS["border"], height=1).grid(
        row=row, column=0, sticky="ew", padx=26, pady=(4, 10)
    )


def _build_tool_card(app, root, row: int, catalog_entry: dict) -> None:
    tool_id = catalog_entry["id"]
    name = catalog_entry["name"]
    installed = is_tool_installed(tool_id)

    if installed:
        record = get_tool_record(tool_id)
        version_line = f"Installed version: {record['installed_version']}"
    else:
        version_line = "Not installed."
    body_text = f"{catalog_entry['description']}\n\n{version_line}"

    card = Card(root)
    card.grid(row=row, column=0, sticky="ew", padx=26, pady=9)
    card.grid_columnconfigure(0, weight=1)
    ttk.Label(card, text=name, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    ttk.Label(
        card, text=body_text, style="CardMuted.TLabel", wraplength=950, justify="left",
    ).grid(row=1, column=0, sticky="w", pady=(7, 10))

    button_bar = ttk.Frame(card, style="Card.TFrame")
    button_bar.grid(row=2, column=0, sticky="w")

    column_index = 0
    if not installed:
        ttk.Button(
            button_bar, text="Download", style="Accent.TButton",
            command=lambda: app.download_tool(tool_id),
        ).grid(row=0, column=column_index, padx=(0, 8))
        column_index += 1
    else:
        update_info = getattr(app, "tool_update_availability", {}).get(tool_id)
        if update_info is not None:
            ttk.Button(
                button_bar, text=f"Update to v{update_info['available_version']}", style="Accent.TButton",
                command=lambda: app.download_tool(tool_id),
            ).grid(row=0, column=column_index, padx=(0, 8))
            column_index += 1
        ttk.Button(
            button_bar, text="Run", command=lambda: app.run_tool(tool_id),
        ).grid(row=0, column=column_index, padx=(0, 8))
        column_index += 1
        ttk.Button(
            button_bar, text="Open Folder", command=lambda: app.open_tool_folder(tool_id),
        ).grid(row=0, column=column_index, padx=(0, 8))
        column_index += 1

        if update_info is not None and update_info.get("changelog"):
            ttk.Label(
                card,
                text=f"What's new in v{update_info['available_version']}:\n{update_info['changelog']}",
                style="CardMuted.TLabel", wraplength=950, justify="left",
            ).grid(row=3, column=0, sticky="w", pady=(8, 0))


def render(app) -> None:
    root = app.page_shell(
        "Tooling",
        (
            "Download, run, and keep every Brisart-family program up to date, all from one place. "
            "Updates are checked automatically according to the Enable update checks / Notify me "
            "about updates / Automatically download and install updates settings on the Settings page."
        ),
    )

    installed_entries, not_installed_entries = _partition_catalog_by_install_state(TOOLING_CATALOG)

    row = 2

    if installed_entries:
        _build_section_header(root, row, "Installed")
        row += 1
        for catalog_entry in installed_entries:
            _build_tool_card(app, root, row=row, catalog_entry=catalog_entry)
            row += 1

    if installed_entries and not_installed_entries:
        _build_divider(root, row)
        row += 1

    if not_installed_entries:
        _build_section_header(root, row, "Available to Download")
        row += 1
        for catalog_entry in not_installed_entries:
            _build_tool_card(app, root, row=row, catalog_entry=catalog_entry)
            row += 1
