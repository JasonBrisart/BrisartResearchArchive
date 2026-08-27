"""
Sidebar navigation - builds the left-hand nav column against
config.registries.NAV_ITEMS (top group) and TOOLING_NAV_ITEM /
SETTINGS_NAV_ITEM (bottom, pinned), storing button references on
app.nav so main_window._update_nav_selection() can restyle the active
page.

Tooling and Settings are deliberately built as their own bottom-pinned
section rather than just more entries in the main list: both are
app-level/utility pages (browsing+managing external programs, and
app configuration, respectively) rather than primary content pages
like the four in NAV_ITEMS.

DIVIDER POSITION, specifically (FIX 1):
The divider line is placed BETWEEN Tooling and Settings -- i.e. the
bottom-pinned section reads, top to bottom: Tooling, divider line,
Settings. It previously sat above BOTH Tooling and Settings (as a
single divider separating the whole bottom-pinned group from the main
NAV_ITEMS list above it), which did not match the intended layout.

STACKING ORDER, specifically: Tk's pack() stacks side="bottom" widgets
in packing order, with the FIRST widget packed that way claiming the
bottom-most slot and each subsequent one stacking above it. To get the
required top-to-bottom visual order (Tooling, divider, Settings), the
three bottom-pinned widgets are packed in THIS order:
  1. Settings button  -- packed FIRST -> claims the very bottom slot.
  2. Divider line      -- packed SECOND -> stacks directly above Settings.
  3. Tooling button    -- packed THIRD -> stacks directly above the divider.
This order must be preserved if this file is ever edited again: simply
reordering these three pack() calls will silently change which side of
the divider each button ends up on.
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

    # Bottom-pinned section -- packed in the specific order described
    # in this module's docstring (FIX 1 / STACKING ORDER) so the final
    # top-to-bottom visual layout reads: Tooling, divider, Settings.

    # 1. Settings packed FIRST with side="bottom" -- claims the very
    #    bottom-most slot in the sidebar.
    settings_name, settings_icon = SETTINGS_NAV_ITEM
    settings_button = _build_nav_button(sidebar, app, settings_name, settings_icon)
    settings_button.pack(fill="x", padx=8, pady=(0, 12), side="bottom")
    app.nav[settings_name] = settings_button

    # 2. Divider packed SECOND with side="bottom" -- stacks directly
    #    above Settings, below Tooling.
    tk.Frame(sidebar, bg=COLORS["border"], height=1).pack(
        fill="x", padx=8, pady=(8, 8), side="bottom"
    )

    # 3. Tooling packed THIRD with side="bottom" -- stacks directly
    #    above the divider.
    tooling_name, tooling_icon = TOOLING_NAV_ITEM
    tooling_button = _build_nav_button(sidebar, app, tooling_name, tooling_icon)
    tooling_button.pack(fill="x", padx=8, pady=(0, 2), side="bottom")
    app.nav[tooling_name] = tooling_button
