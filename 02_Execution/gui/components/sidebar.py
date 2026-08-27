"""
Sidebar navigation - builds the left-hand nav column against
config.registries.NAV_ITEMS (top group) and SETTINGS_NAV_ITEM (bottom,
pinned), storing button references on app.nav so
main_window._update_nav_selection() can restyle the active page.

Settings is deliberately built as its own bottom-pinned section rather
than just another entry in the main list: it's a distinct category
(app-level configuration) rather than a content area like the other
four pages, so it's visually separated by an expanding spacer plus a
thin divider line above it.
"""
from __future__ import annotations

import tkinter as tk

from config.registries import NAV_ITEMS, SETTINGS_NAV_ITEM
from gui.theme import COLORS, FONT


def _build_nav_button(sidebar: tk.Frame, app, name: str, icon: str) -> tk.Label:
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
    button.bind("<Button-1>", lambda _event, page=name: app.show_page(page))
    return button


def build_sidebar(app) -> None:
    sidebar = tk.Frame(app, bg="#050812", width=210)
    sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
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
    ).pack(anchor="w", padx=18, pady=(20, 28))

    app.nav = {}

    # Main navigation group, top-down.
    for name, icon in NAV_ITEMS:
        button = _build_nav_button(sidebar, app, name, icon)
        button.pack(fill="x", padx=8, pady=2)
        app.nav[name] = button

    # Expanding spacer pushes everything below it to the bottom of the
    # sidebar column, regardless of how many main nav items exist above.
    spacer = tk.Frame(sidebar, bg="#050812")
    spacer.pack(fill="both", expand=True)

    # Thin divider so Settings reads as its own section, not just the
    # last item in the same list.
    tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(fill="x", padx=8, pady=(0, 8))

    settings_name, settings_icon = SETTINGS_NAV_ITEM
    settings_button = _build_nav_button(sidebar, app, settings_name, settings_icon)
    settings_button.pack(fill="x", padx=8, pady=(0, 12), side="bottom")
    app.nav[settings_name] = settings_button
