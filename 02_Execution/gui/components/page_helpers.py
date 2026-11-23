"""
File: gui/components/page_helpers.py

Purpose
-------
Provide the UIController mixin (page_shell and add_card) that every page
renders through, plus the mouse-wheel and text-wrapping helpers.

Communication / relationships
-----------------------------
- Mixed into gui/main_window.BrisartSuiteApp.
- Every module in gui/pages/ calls app.page_shell() and app.add_card().
- gui/main_window.py uses mousewheel_units() and
  widget_is_or_contains_text() in its global wheel handler.
- gui/pages/settings_page.py and gui/pages/results_page.py call
  bind_text_widget_scroll_passthrough().
- Uses Card from gui/components/card.py.

Settings / parameters
---------------------
- MIN_DYNAMIC_WRAPLENGTH (220): lowest wraplength while a container
  briefly reports a near-zero width during layout.
- page_shell() stores the scrollable canvas on app._page_canvas so the
  global wheel handler knows what to scroll.
- add_card(root, row, title, body, actions): actions is a list of
  (label, command, is_primary) tuples.

Edge cases
----------
- mousewheel_units() returns at least one unit for any nonzero delta,
  because trackpads send deltas below 120.
- The Text passthrough forwards the wheel to the page only when the
  Text content already fits; otherwise Tk's own Text scrolling runs.
- Wraplength is recalculated after idle, so rebuilt pages wrap
  immediately.

Known limitations
-----------------
- Touchpad two-finger scrolling over the general page area does not
  work, although a physical mouse wheel does. Per-widget bindings, small-
  delta handling, and a global handler resolving the widget under the
  cursor (the current mechanism) have been tried. Next step: log every
  wheel event Tk receives during a touchpad scroll; if none arrive, the
  fix is outside the Archive.

Examples
--------
- root = app.page_shell("Results", "Analyze TFL sessions.")
- app.add_card(root, 2, "Title", "Body", [("Run", app.start_tfl, True)])
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable
from gui.theme import COLORS
from gui.components.card import Card

# Minimum sensible wraplength, in pixels, so a container that briefly
# reports a near-zero width during initial layout never collapses a
# label's wrapping down to an unreadably narrow column.
MIN_DYNAMIC_WRAPLENGTH = 220


def widget_is_or_contains_text(widget: tk.Misc | None) -> bool:
    """
    True if `widget` is a tk.Text widget, or is nested inside one. Used
    so the page-level scroll handler defers to a Text widget's own native
    scrolling (Activity Log, Update Output, Results analysis box) instead
    of competing with it.
    """
    while widget is not None:
        if isinstance(widget, tk.Text):
            return True
        widget = getattr(widget, "master", None)
    return False


def mousewheel_units(event: object) -> int:
    """
    Convert a raw <MouseWheel> event into a signed integer number of
    scroll units, guaranteeing at least 1 unit of movement for any
    nonzero delta -- event.delta is a clean multiple of 120 only for a
    mechanical wheel; trackpads send much smaller deltas that would
    otherwise integer-divide straight to zero.
    """
    delta = getattr(event, "delta", 0)
    if delta == 0:
        return 0
    steps = int(delta / 120)
    if steps == 0:
        steps = 1 if delta > 0 else -1
    return -steps


def bind_dynamic_wraplength(label: ttk.Label, container: tk.Misc, margin: int = 0) -> None:
    """
    Keep `label`'s wraplength in sync with `container`'s current width
    instead of a fixed pixel constant, so text reflows at any window
    size. `margin` is subtracted from the measured width (e.g. for the
    container's own padding) so wrapped text never touches the edge.
    """

    def _update_wraplength(_event=None) -> None:
        try:
            if not label.winfo_exists() or not container.winfo_exists():
                return
            width = container.winfo_width() - margin
            if width < MIN_DYNAMIC_WRAPLENGTH:
                width = MIN_DYNAMIC_WRAPLENGTH
            label.configure(wraplength=width)
        except tk.TclError:
            pass
    # add="+" so this never clobbers other <Configure> handlers already
    # bound on the same container (scrollregion sync, canvas-width sync).
    container.bind("<Configure>", _update_wraplength, add="+")
    # The container may already have a real width when this label is
    # created (e.g. re-rendering an existing page) -- run once after the
    # current geometry pass settles so the label isn't stuck at its
    # default wraplength until the next resize.
    try:
        container.after_idle(_update_wraplength)
    except tk.TclError:
        pass


def bind_text_widget_scroll_passthrough(text_widget: tk.Text, app: tk.Misc) -> None:
    """
    Forward the mouse wheel to the page canvas when this Text widget's
    own content is already fully visible.

    A tk.Text widget has a built-in class-level <MouseWheel> binding that
    intercepts the wheel event and stops its propagation even when the
    widget has nothing to scroll, which would otherwise block the event
    from reaching the page-level scroll handler in gui/main_window.py.
    This binds an instance-level handler (instance bindings run before
    class bindings) that, when the Text content is fully in view, scrolls
    app._page_canvas instead and returns "break"; when the Text genuinely
    has overflow, it returns None and lets Tk's normal Text scrolling
    behave as usual.

    Call once, right after creating the Text widget -- see
    gui/pages/settings_page.py (update_box, log_box) and
    gui/pages/results_page.py (analysis_box) for the call sites.
    """

    def _handler(event):
        try:
            top_fraction, bottom_fraction = text_widget.yview()
        except tk.TclError:
            return None
        content_fully_visible = top_fraction <= 0.0001 and bottom_fraction >= 0.9999
        if not content_fully_visible:
            return None  # real overflow exists -- let Tk's own Text scrolling handle it
        canvas = getattr(app, "_page_canvas", None)
        if canvas is None:
            return "break"
        try:
            if not canvas.winfo_exists():
                return "break"
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            else:
                units = mousewheel_units(event)
                if units != 0:
                    canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass
        return "break"
    text_widget.bind("<MouseWheel>", _handler)
    text_widget.bind("<Button-4>", _handler)
    text_widget.bind("<Button-5>", _handler)


class UIController:
    """Mixed into BrisartSuiteApp so pages can call app.page_shell()/app.add_card()."""

    def page_shell(self, title: str, subtitle: str) -> ttk.Frame:
        """
        Build a scrollable page shell. The returned frame is the grid
        parent every page module builds its cards into via
        app.add_card(root, row, ...); it's embedded inside a scrollable
        Canvas rather than gridded straight into self.main, so pages
        taller than the window remain fully reachable. The canvas is
        stashed on self._page_canvas so main_window.py's global
        mousewheel handler always knows which canvas to scroll.
        """
        canvas = tk.Canvas(self.main, bg=COLORS["bg"], highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self.main, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._page_canvas = canvas
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
        root.bind("<Configure>", _sync_scrollregion, add="+")
        canvas.bind("<Configure>", _sync_inner_width, add="+")
        title_label = ttk.Label(root, text=title, style="Title.TLabel")
        title_label.grid(row=0, column=0, sticky="w", padx=26, pady=(24, 4))
        subtitle_label = ttk.Label(
            root, text=subtitle, style="Muted.TLabel", justify="left",
        )
        subtitle_label.grid(row=1, column=0, sticky="w", padx=26, pady=(0, 16))
        bind_dynamic_wraplength(subtitle_label, canvas, margin=52)
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
        body_label = ttk.Label(card, text=body, style="CardMuted.TLabel", justify="left")
        body_label.grid(row=1, column=0, sticky="w", pady=(7, 10))
        # Bound to the card itself (not the outer page canvas) so the
        # wraplength tracks this specific card's width -- correct even in
        # multi-column layouts where a card is narrower than the page.
        bind_dynamic_wraplength(body_label, card, margin=32)
        if actions:
            button_bar = ttk.Frame(card, style="Card.TFrame")
            button_bar.grid(row=2, column=0, sticky="w")
            for index, (label, command, is_primary) in enumerate(actions):
                style_name = "Accent.TButton" if is_primary else "TButton"
                ttk.Button(button_bar, text=label, command=command, style=style_name).grid(
                    row=0, column=index, padx=(0, 8)
                )
        return card


__all__ = [
    "UIController", "bind_dynamic_wraplength",
    "widget_is_or_contains_text", "mousewheel_units", "bind_text_widget_scroll_passthrough",
]

