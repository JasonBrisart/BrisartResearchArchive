"""
Sidebar navigation — builds the left-hand nav column against
config.registries.NAV_ITEMS, storing button references on app.nav so
main_window._update_nav_selection() can restyle the active page.
"""
from __future__ import annotations

import tkinter as tk

from config.registries import NAV_ITEMS
from gui.theme import COLORS, FONT, FONT_SMALL


def build_sidebar(app) -> None:
    sidebar = tk.Frame(app, bg="#050812", width=210)
    sidebar.grid(row=0, column=0, rowspan=2, sticky="nsw")
    sidebar.grid_propagate(False)
    app.sidebar = sidebar

    tk.Label(
        sidebar, text=app.app_name, bg="#050812", fg=COLORS["accent"],
        font=("Segoe UI", 13, "bold"), wraplength=180, justify="left",
    ).pack(anchor="w", padx=18, pady=(20, 4))
    tk.Label(
        sidebar, text=f"v{app.app_version}", bg="#050812", fg=COLORS["muted"], font=FONT_SMALL,
    ).pack(anchor="w", padx=18, pady=(0, 20))

    app.nav = {}
    for name, icon in NAV_ITEMS:
        button = tk.Label(
            sidebar, text=f"  {icon}   {name}", bg="#050812", fg=COLORS["muted"],
            font=FONT, anchor="w", padx=12, pady=10, cursor="hand2",
        )
        button.pack(fill="x", padx=8, pady=2)
        button.bind("<Button-1>", lambda _event, page=name: app.show_page(page))
        app.nav[name] = button
