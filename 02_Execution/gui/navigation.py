"""
File: gui/navigation.py

Purpose
-------
Define the sidebar entries and map page names to their render functions.
Replaces the framework registry: TFL is the only framework, so there is
nothing to discover.

Communication / relationships
-----------------------------
- gui/components/sidebar.py reads NAV_ITEMS and SETTINGS_NAV_ITEM.
- gui/main_window.py calls get_page_renderer() and normalize_page_name().
- Page modules under gui/pages/ are imported lazily on first use.

Settings / parameters
---------------------
- NAV_ITEMS: Dashboard, TFL, Results, Archive.
- SETTINGS_NAV_ITEM: pinned at the bottom of the sidebar.
- DEFAULT_PAGE: "Dashboard".
- PAGE_ALIASES: older names ("Frameworks", "System", "Home", ...) that
  still resolve, so a stale call cannot show a blank page.

Edge cases
----------
- An unknown name returns None; the main window shows an error dialog.

Known limitations
-----------------
- The page table is built once per process.

Examples
--------
- get_page_renderer("TFL")
"""
from __future__ import annotations

NAV_ITEMS = [
    ("Dashboard", "\u2302"),
    ("TFL", "\U0001F9EA"),
    ("Results", "\U0001F4CA"),
    ("Archive", "\U0001F4DA"),
]
SETTINGS_NAV_ITEM = ("Settings", "\u2699")
DEFAULT_PAGE = "Dashboard"
PAGE_ALIASES = {
    "Home": "Dashboard",
    "Frameworks": "TFL",
    "Execution": "TFL",
    "Analysis": "Results",
    "Documentation": "Archive",
    "System": "Settings",
}

_PAGES: dict | None = None


def normalize_page_name(name: str) -> str:
    return PAGE_ALIASES.get(name, name)


def get_page_renderer(name: str):
    global _PAGES
    if _PAGES is None:
        from gui.pages import archive_page, dashboard_page, results_page, settings_page, tfl_page
        _PAGES = {
            "Dashboard": dashboard_page.render,
            "TFL": tfl_page.render,
            "Results": results_page.render,
            "Archive": archive_page.render,
            "Settings": settings_page.render,
        }
    return _PAGES.get(normalize_page_name(name))


__all__ = ["NAV_ITEMS", "SETTINGS_NAV_ITEM", "DEFAULT_PAGE", "PAGE_ALIASES", "normalize_page_name", "get_page_renderer"]
