"""
File: gui/components/sidebar.py

Purpose:
Build the application sidebar and connect each navigation entry to the
corresponding registered page.

Communication / relationships:
- Reads NAV_ITEMS and SETTINGS_NAV_ITEM from config/registries.py.
- Calls app.show_page() when a navigation entry is selected.
- Stores navigation widgets in app.nav for active-page highlighting.
- Is called once by gui/main_window.py during layout construction.

Settings / parameters:
- The sidebar width is fixed at 210 pixels.
- NAV_ITEMS are rendered in the upper navigation group.
- SETTINGS_NAV_ITEM is pinned at the bottom beneath a divider.

Edge cases:
- Navigation callbacks resolve page names only when clicked.
- The expanding spacer keeps Settings pinned to the bottom regardless
  of the number of primary navigation entries.

Known limitations:
- The sidebar does not collapse or resize independently.
- Icons depend on the active system font supporting their characters.

Examples:
- build_sidebar(app)
"""

from __future__ import annotations

import tkinter as tk

from config.registries import NAV_ITEMS, SETTINGS_NAV_ITEM
from gui.theme import COLORS, FONT


def _build_nav_button(
    sidebar: tk.Frame,
    app,
    name: str,
    icon: str,
) -> tk.Label:
    button = tk.Label(
        sidebar,
        text=f"  {icon}   {name}",
        bg="#050812",
        fg=COLORS["muted"],
        font=FONT,
        anchor="w",
        padx=12,
        pady=10,
        cursor="hand2",
    )

    button.bind(
        "<Button-1>",
        lambda _event, page=name: app.show_page(page),
    )

    return button


def build_sidebar(app) -> None:
    sidebar = tk.Frame(
        app,
        bg="#050812",
        width=210,
    )
    sidebar.grid(
        row=0,
        column=0,
        rowspan=2,
        sticky="nsw",
    )
    sidebar.grid_propagate(False)

    app.sidebar = sidebar

    tk.Label(
        sidebar,
        text=app.app_name,
        bg="#050812",
        fg=COLORS["accent"],
        font=("Segoe UI", 13, "bold"),
        wraplength=180,
        justify="left",
    ).pack(
        anchor="w",
        padx=18,
        pady=(20, 28),
    )

    app.nav = {}

    for name, icon in NAV_ITEMS:
        button = _build_nav_button(
            sidebar,
            app,
            name,
            icon,
        )
        button.pack(
            fill="x",
            padx=8,
            pady=2,
        )
        app.nav[name] = button

    spacer = tk.Frame(
        sidebar,
        bg="#050812",
    )
    spacer.pack(
        fill="both",
        expand=True,
    )

    settings_name, settings_icon = SETTINGS_NAV_ITEM

    settings_button = _build_nav_button(
        sidebar,
        app,
        settings_name,
        settings_icon,
    )
    settings_button.pack(
        fill="x",
        padx=8,
        pady=(0, 12),
        side="bottom",
    )
    app.nav[settings_name] = settings_button

    tk.Frame(
        sidebar,
        bg=COLORS["border"],
        height=1,
    ).pack(
        fill="x",
        padx=8,
        pady=(8, 8),
        side="bottom",
    )


__all__ = ["build_sidebar"]