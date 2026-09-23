"""
gui/components/sidebar.py
Sidebar navigation -- builds the left-hand nav column against
config.registries.NAV_ITEMS (top group) and TOOLING_NAV_ITEM /
SETTINGS_NAV_ITEM (bottom, pinned), storing button references on app.nav
so main_window._update_nav_selection() can restyle the active page.

Tooling and Settings are deliberately built as their own bottom-pinned
section rather than more entries in the main list: both are
app-level/utility pages (browsing+managing external programs, and app
configuration) rather than primary content pages like the four in
NAV_ITEMS.

Bottom-section layout: the divider sits BETWEEN Tooling and Settings, so
the pinned group reads top-to-bottom as: Tooling, divider, Settings.
Tk's pack(side="bottom") stacks widgets bottom-up -- the first packed
claims the lowest slot -- so the three widgets are packed in this order,
and that order must be preserved:
  1. Settings button -> packed first  -> claims the very bottom slot.
  2. Divider line     -> packed second -> stacks directly above Settings.
  3. Tooling button   -> packed third  -> stacks directly above the divider.
Reordering these three pack() calls silently changes which side of the
divider each button lands on.
"""
from __future__ import annotations
import tkinter as tk
from config.registries import NAV_ITEMS, SETTINGS_NAV_ITEM, TOOLING_NAV_ITEM
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
    # Bottom-pinned section -- packed in the order described in this
    # module's docstring so the final layout reads: Tooling, divider,
    # Settings.
    settings_name, settings_icon = SETTINGS_NAV_ITEM
    settings_button = _build_nav_button(sidebar, app, settings_name, settings_icon)
    settings_button.pack(fill="x", padx=8, pady=(0, 12), side="bottom")
    app.nav[settings_name] = settings_button
    tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(
        fill="x", padx=8, pady=(8, 8), side="bottom"
    )
    tooling_name, tooling_icon = TOOLING_NAV_ITEM
    tooling_button = _build_nav_button(sidebar, app, tooling_name, tooling_icon)
    tooling_button.pack(fill="x", padx=8, pady=(0, 2), side="bottom")
    app.nav[tooling_name] = tooling_button
