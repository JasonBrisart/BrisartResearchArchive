"""
UIController — the small mixin every page renders through. Provides
the two building blocks every page module uses: a titled page shell
with an action-button row, and a titled info/action card.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from gui.theme import COLORS
from gui.widgets.card import Card


class UIController:
    """Mixed into BrisartSuiteApp so pages can call app.page_shell()/app.add_card()."""

    def page_shell(self, title: str, subtitle: str) -> ttk.Frame:
        """
        Build a scrollable page shell. Previously this returned a plain
        ttk.Frame gridded directly into self.main with no scrolling
        mechanism at all - pages like System (7+ cards plus a 12-line
        text box) stack well over 1500px of content into a window whose
        default height is 780px, so the bottom cards were completely
        unreachable with no way to scroll to them. The canvas+scrollbar
        wrapper below is transparent to every page module: they keep
        calling app.add_card(root, row, ...) exactly as before, since
        `root` (the frame returned here) is still the grid parent they
        build into - it's just now embedded in a scrollable canvas
        instead of gridded straight into self.main.
        """
        canvas = tk.Canvas(self.main, bg=COLORS["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self.main, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        root = ttk.Frame(canvas, style="Bg.TFrame")
        root.grid_columnconfigure(0, weight=1)
        canvas_window = canvas.create_window((0, 0), window=root, anchor="nw")

        def _sync_scrollregion(_event=None) -> None:
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except tk.TclError:
                pass

        def _sync_inner_width(event) -> None:
            try:
                canvas.itemconfigure(canvas_window, width=event.width)
            except tk.TclError:
                pass

        root.bind("<Configure>", _sync_scrollregion)
        canvas.bind("<Configure>", _sync_inner_width)

        def _on_mousewheel(event) -> None:
            try:
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except tk.TclError:
                pass

        def _bind_mousewheel(_event=None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_mousewheel(_event=None) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        # Only steal the scroll wheel while the pointer is actually over
        # this page's canvas, so Text widgets nested inside cards (log
        # boxes, analysis output, etc.) keep their own native scrolling.
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

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
