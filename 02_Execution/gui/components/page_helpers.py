"""
UIController — the small mixin every page renders through. Provides
the two building blocks every page module uses: a titled page shell
with an action-button row, and a titled info/action card.
"""
from __future__ import annotations

from tkinter import ttk
from typing import Callable

from gui.theme import COLORS
from gui.widgets.card import Card


class UIController:
    """Mixed into BrisartSuiteApp so pages can call app.page_shell()/app.add_card()."""

    def page_shell(self, title: str, subtitle: str) -> ttk.Frame:
        root = ttk.Frame(self.main, style="Bg.TFrame")
        root.grid(row=0, column=0, sticky="nsew")
        root.grid_columnconfigure(0, weight=1)
        ttk.Label(root, text=title, style="Title.TLabel").grid(
            row=0, column=0, sticky="w", padx=26, pady=(24, 4)
        )
        ttk.Label(
            root, text=subtitle, style="Muted.TLabel", wraplength=980, justify="left",
        ).grid(row=1, column=0, sticky="w", padx=26, pady=(0, 16))
        return root

    def add_card(
        self,
        root: ttk.Frame,
        row: int,
        title: str,
        body: str,
        actions: list[tuple[str, Callable, bool]] | None = None,
    ) -> Card:
        card = Card(root)
        card.grid(row=row, column=0, sticky="ew", padx=26, pady=9)
        card.grid_columnconfigure(0, weight=1)
        ttk.Label(card, text=title, style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            card, text=body, style="CardMuted.TLabel", wraplength=950, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(7, 10))
        if actions:
            button_bar = ttk.Frame(card, style="Card.TFrame")
            button_bar.grid(row=2, column=0, sticky="w")
            for index, (label, command, is_primary) in enumerate(actions):
                style_name = "Accent.TButton" if is_primary else "TButton"
                ttk.Button(button_bar, text=label, command=command, style=style_name).grid(
                    row=0, column=index, padx=(0, 8)
                )
        return card


__all__ = ["UIController", "COLORS"]
