"""
File: gui/components/card.py

Purpose
-------
Provide Card, the standard padded panel used across the GUI and the TFL
screens.

Communication / relationships
-----------------------------
- Used by gui/components/page_helpers.add_card(),
  gui/pages/settings_page.py, gui/pages/tfl_page.py,
  frameworks/TFL/gui_options.py, and frameworks/TFL/gui_screens.py.
- The "Card.TFrame" style is defined in gui/theme.apply_theme().

Settings / parameters
---------------------
- Default style "Card.TFrame" and padding (16, 14); caller keyword
  arguments override both.

Edge cases
----------
- Before apply_theme() runs, the frame uses the default ttk look.

Known limitations
-----------------
- A plain container with no built-in title or action row.

Examples
--------
- card = Card(root); card.grid(row=2, column=0, sticky="ew")
"""
from __future__ import annotations

from tkinter import ttk


class Card(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        kwargs.setdefault("style", "Card.TFrame")
        kwargs.setdefault("padding", (16, 14))
        super().__init__(parent, *args, **kwargs)


__all__ = ["Card"]
