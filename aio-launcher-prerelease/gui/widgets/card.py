"""
Card — the standard panel widget used throughout the Archive GUI:
dashboard tiles, framework tiles, and every info block inside a
framework trial screen.
"""
from __future__ import annotations

from tkinter import ttk


class Card(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        kwargs.setdefault("style", "Card.TFrame")
        kwargs.setdefault("padding", (16, 14))
        super().__init__(parent, *args, **kwargs)


__all__ = ["Card"]
