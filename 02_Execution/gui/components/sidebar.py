"""
File: gui/components/sidebar.py

Purpose
-------
Build the application sidebar and connect each entry to its page.

Communication / relationships
-----------------------------
- Reads NAV_ITEMS and SETTINGS_NAV_ITEM from gui/navigation.py.
- Calls app.show_page() when an entry is clicked.
- Stores the entry widgets in app.nav; gui/main_window.show_page() uses
  them to highlight the active page.
- Reads app.app_name for the title and COLORS (including the sidebar
  background) and FONT from gui/theme.py.

Settings / parameters
---------------------
- Fixed width of 210 pixels, pinned to the left of the window.
- NAV_ITEMS fill the upper group; SETTINGS_NAV_ITEM is pinned at the bottom
  under a divider.

Edge cases
----------
- An expanding spacer keeps Settings at the bottom whatever the number of
  upper entries.

Known limitations
-----------------
- Entries are labels that respond to the mouse only; they cannot be
  reached with the Tab key or activated from the keyboard.
- The sidebar does not collapse.
- Icons depend on the system font supporting the characters.

Examples
--------
- build_sidebar(app)
"""
from __future__ import annotations

import tkinter as tk

from gui.navigation import NAV_ITEMS, SETTINGS_NAV_ITEM
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
        bg=COLORS["sidebar"],
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
        bg=COLORS["sidebar"],
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
        bg=COLORS["sidebar"],
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
        bg=COLORS["sidebar"],
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

