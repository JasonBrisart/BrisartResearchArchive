"""
gui/components/page_helpers.py
UIController -- the small mixin every page renders through, mixed into
BrisartSuiteApp (see gui/main_window.py) so page modules can call
app.page_shell(title, subtitle) to get a scrollable page container, and
app.add_card(root, row, title, body, actions) to drop a standard
info/action card into it. Every page module in gui/pages/ depends on
both; neither holds any state of its own beyond what it builds fresh on
each call.

MOUSEWHEEL SCROLLING
The general page area is scrolled by a single root-level handler in
gui/main_window.py (_on_global_mousewheel), which resolves the widget
under the cursor via winfo_containing() on live screen coordinates
rather than trusting Tk's internal pointer cache -- necessary because a
touchpad two-finger gesture moves the cursor zero pixels, leaving that
cache stale. This module contributes three supporting pieces:
  - mousewheel_units(): converts a raw <MouseWheel> delta into a signed
    unit count, guaranteeing at least one unit for any nonzero delta
    (trackpads send deltas well below 120, which integer-divide to zero).
  - widget_is_or_contains_text(): lets the handler defer to a Text
    widget's own native scrolling (Activity Log, Update Output, Results
    analysis box) instead of competing with it.
  - bind_text_widget_scroll_passthrough(): a Text widget has a built-in
    class-level <MouseWheel> binding that swallows the event even when
    the widget has nothing to scroll, blocking the page underneath from
    scrolling. This binds an instance-level handler (which runs before
    class bindings) that forwards the wheel to the page canvas when the
    Text content is already fully visible, and otherwise steps aside.
  - bind_scrolling_recursively(): a supplementary per-widget binding
    layer, confirmed working for a physical mouse wheel, kept as a
    defensive fallback.
Touchpad scrolling over the general page area remains an open issue even
with the global handler; see docs/KNOWN_ISSUES.md for status.

DYNAMIC TEXT WRAPPING
Tk's wraplength is a fixed pixel value it never recomputes on resize, so
a label sized for a wide window clips instead of reflowing when the
window is narrower. bind_dynamic_wraplength(label, container) binds
<Configure> on the container to recompute the label's wraplength from
the container's current width on every resize. Applied to page_shell()'s
subtitle and add_card()'s body label, which cover most body text.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable
from gui.theme import COLORS
from gui.widgets.card import Card
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
def _event_target_is_text_widget(event: object) -> bool:
    """Back-compat wrapper around widget_is_or_contains_text() for any
    caller still passing a raw event object instead of a widget."""
    return widget_is_or_contains_text(getattr(event, "widget", None))
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
# Back-compat alias (older code/tests may import the underscored name).
_mousewheel_units = mousewheel_units
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
def bind_scrolling_recursively(root_widget: tk.Misc, on_mousewheel: Callable) -> None:
    """
    Walk `root_widget` and every descendant, binding <MouseWheel>,
    <Button-4>, and <Button-5> directly on each one as an instance
    binding. A supplementary/defensive layer -- confirmed working for a
    physical mouse wheel -- while the primary mechanism for the general
    page area is the global handler in main_window.py. Safe to call on a
    widget tree still being built or partially destroyed mid-walk (each
    bind() is guarded); add="+" throughout so it never clobbers an
    existing binding.
    """
    def _walk(widget: tk.Misc) -> None:
        try:
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
            widget.bind("<Button-4>", on_mousewheel, add="+")
            widget.bind("<Button-5>", on_mousewheel, add="+")
        except tk.TclError:
            return
        try:
            children = widget.winfo_children()
        except tk.TclError:
            return
        for child in children:
            _walk(child)
    _walk(root_widget)
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
    "UIController", "COLORS", "bind_dynamic_wraplength", "bind_scrolling_recursively",
    "widget_is_or_contains_text", "mousewheel_units", "bind_text_widget_scroll_passthrough",
]
