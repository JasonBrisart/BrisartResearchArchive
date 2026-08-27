"""
gui/components/page_helpers.py
UIController -- the small mixin every page renders through, mixed into
BrisartSuiteApp (see gui/main_window.py) so page modules can call
app.page_shell(title, subtitle) to get a scrollable page container, and
app.add_card(root, row, title, body, actions) to drop a standard info/
action card into that container. Every page module in gui/pages/
depends on both of these; neither has any state of its own beyond what
it builds fresh on each call.

MOUSEWHEEL SCROLLING, specifically -- full history, in the order each
fix was actually attempted (FIX 1 first, chronologically down to the
most recent). The current, actually-correct mechanism for a physical
mouse wheel is FIX 6 (wired from gui/main_window.py -- see that
module's docstring for how it's bound) plus FIX 7 (see
bind_text_widget_scroll_passthrough() below). FIX 1 through FIX 5 are
kept as historical record of what was tried and why each attempt was
insufficient on its own -- do not remove them when adding a future fix;
append below FIX 7 instead, in the same chronological, oldest-first
order.

  FIX 1 -- binding timing (superseded): the wheel handler used to be
  gated behind the canvas's own <Enter>/<Leave> hover events, which
  never worked because the canvas is entirely covered by its own child
  widgets, so <Leave> fired almost immediately after <Enter>.

  FIX 2 -- delta-to-units conversion (still required, unrelated to
  FIX 5/6): event.delta is only a clean multiple of 120 for a
  traditional mechanical mouse wheel. Laptop trackpads and Precision
  Touchpads send much smaller deltas (sometimes +/-1 to +/-40), and
  int(-1 * (event.delta / 120)) truncates anything smaller straight
  to 0 -- a guaranteed no-op scroll. Fixed by guaranteeing at least 1
  unit of scroll for any nonzero delta.

  FIX 3/4 (superseded) -- the focus-following approach (<Enter>/
  <ButtonRelease-1> pulling keyboard focus onto the canvas) assumed
  <MouseWheel> routes by keyboard focus on Windows. That assumption
  turned out to be wrong, or at least insufficient, once tested.

  FIX 5 (superseded by FIX 6, kept for the Text-widget-detection
  helper below, which FIX 6 also reuses) -- bind the wheel handler
  directly on every widget instead of relying on canvas.bind_all() +
  focus. This is genuinely correct and necessary for a physical mouse
  (verified working), but insufficient alone for touchpads -- see
  FIX 6 below for why.

  FIX 6 (current mechanism for the general page area) -- see
  main_window.py's _on_global_mousewheel(). Root cause hypothesis: Tk
  keeps an internal cache of "which widget is currently under the
  pointer," used to decide which widget a <MouseWheel> event
  dispatches to. That cache is only updated by real <Motion> events
  (the cursor physically moving). A mouse wheel is almost always
  preceded by tiny cursor jitter, which keeps that cache correct. A
  touchpad two-finger scroll gesture moves the cursor ZERO pixels by
  design -- the OS deliberately separates "finger scroll" from
  "pointer position" -- so if the cursor was already resting somewhere
  before the gesture started, Tk's cached "current widget" is stale
  (or simply wrong), and the wheel event dispatches to whatever widget
  that stale cache says, not the widget actually visually under the
  touchpad-controlled cursor. This is why FIX 5 (above) worked
  perfectly for a physical mouse wheel but did nothing at all for a
  touchpad, no matter which widget was hovered: the event was never
  reaching ANY of the widgets FIX 5 bound onto in the first place. The
  fix: bind a single handler at the Tk root (not per-widget), and
  inside it, resolve the target widget via
  winfo_containing(event.x_root, event.y_root) -- a live, direct OS
  coordinate query (real cursor position, independent of Tk's own
  stale internal motion cache) -- instead of trusting Tk's own
  dispatch decision for the event at all.

  NOTE: touchpad scrolling over the general page area remains an open,
  unresolved issue even with FIX 6 in place -- see
  docs/KNOWN_ISSUES.md for the current status, confirmed environment
  details, what has been ruled out so far, and the next diagnostic
  step.

  FIX 7 -- implemented in bind_text_widget_scroll_passthrough() below.
  A DIFFERENT, CONFIRMED-FIXED bug (affects mouse and touchpad
  equally, unrelated to the FIX 6 touchpad issue above): scrolling
  while hovering a tk.Text widget whose own content already fits fully
  on screen (e.g. the Settings page's near-empty "Update output" box,
  or a short Activity Log) did NOTHING AT ALL. Root cause: every
  tk.Text widget has a BUILT-IN, automatic class-level <MouseWheel>
  binding (not something this codebase wrote -- Tk provides it for
  every Text widget) that intercepts the wheel event and calls Tcl's
  "break" to stop it from propagating any further, REGARDLESS of
  whether the Text widget actually has anything to scroll. So hovering
  an already-fully-visible Text box and scrolling did nothing: Tk's
  own binding claimed the event, had no overflow to scroll to, and
  still blocked the event from ever reaching FIX 6's
  _on_global_mousewheel() handler, which would otherwise have scrolled
  the page underneath it. Fix: bind an INSTANCE-level handler directly
  on the Text widget itself. Instance bindings always run BEFORE a
  widget's class-level bindings in Tk's bindtag resolution order, so
  this handler gets first look at every wheel event over that specific
  widget -- if the Text widget's own content is already fully visible
  (yview() reports the whole document in view), it scrolls
  app._page_canvas (the outer page) instead and returns "break" so
  Tk's own do-nothing Text-class binding never runs on top of it; if
  the Text widget genuinely has overflow content, it does nothing
  (returns None) and steps out of the way, letting Tk's normal
  built-in Text scrolling behave exactly as it always has.

  Regardless of mechanism, the Text-widget check below is what lets
  the handler defer to a Text widget's own native scrolling (Activity
  Log, Update Output, Results analysis box, etc.) instead of competing
  with it -- unrelated to which "which widget received this event" bug
  is being worked around.

DYNAMIC TEXT WRAPPING, specifically:
Every Label built through page_shell()/add_card() used to use a FIXED
pixel wraplength (e.g. 950, 980) chosen to look right at the old
1220x780 default window size. Once the window is opened smaller (the
new 800x600 default) or resized down by the user, that fixed value
exceeds the actual available width, and Tk clips the label instead of
re-wrapping it -- wraplength is a static value that Tk never
recalculates on its own.
bind_dynamic_wraplength(label, container) fixes this: it binds
<Configure> on `container` (the label's parent) so that every time the
container's width changes, the label's wraplength is recomputed to
match it (minus a small margin) -- text now reflows correctly at any
window size instead of cutting off. Applied here to page_shell()'s
subtitle and add_card()'s body label, which together cover the large
majority of body text across every page.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from gui.theme import COLORS
from gui.widgets.card import Card

# Minimum sensible wraplength, in pixels, so a container that briefly
# reports a near-zero width during initial layout (before geometry
# management has settled) never collapses a label's wrapping down to
# an unreadably narrow column.
MIN_DYNAMIC_WRAPLENGTH = 220


def widget_is_or_contains_text(widget: tk.Misc | None) -> bool:
    """
    True if `widget` is a tk.Text widget, or is nested inside one (e.g.
    a scrollbar or internal component of a Text-based widget). Used so
    the page-level scroll handler defers to a Text widget's own native
    scrolling (Activity Log, Update Output, Results analysis box, etc.)
    instead of competing with it. Shared by both the legacy per-widget
    handler (FIX 5) and the current global handler (FIX 6, in
    main_window.py) -- see the module docstring for how they differ.
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
    scroll units, guaranteeing at least 1 unit of movement for ANY
    nonzero delta -- see the FIX 2 section of the module docstring.
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
    Keep `label`'s wraplength in sync with `container`'s current width,
    instead of a fixed pixel constant -- see the DYNAMIC TEXT WRAPPING
    section of the module docstring for why this matters. `margin` is
    subtracted from the measured width (e.g. to account for the
    container's own padding) so wrapped text never touches the very
    edge of its container.
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
    # bound on the same container (e.g. page_shell()'s own scrollregion
    # sync, or the canvas-width sync).
    container.bind("<Configure>", _update_wraplength, add="+")
    # The container may already have a real width by the time this
    # label is created (e.g. re-rendering an existing page) -- run once
    # immediately, after the current geometry pass settles, so the
    # label doesn't sit at its default/fixed wraplength until the next
    # resize event happens to fire.
    try:
        container.after_idle(_update_wraplength)
    except tk.TclError:
        pass


def bind_text_widget_scroll_passthrough(text_widget: tk.Text, app: tk.Misc) -> None:
    """
    Implements FIX 7 -- see the FIX 7 entry in this module's top
    docstring (MOUSEWHEEL SCROLLING section) for the full root-cause
    explanation and history. Kept brief here to avoid documenting the
    same fix twice in two different places in the file; the module
    docstring is the single source of truth for fix history, in
    chronological order.

    Must be called once, right after creating the given Text widget --
    see gui/pages/settings_page.py (update_box, log_box) and
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
    <Button-4>, and <Button-5> DIRECTLY on each one as an instance
    binding. Kept as a supplementary/defensive layer -- confirmed
    working for a real mouse wheel -- but the primary mechanism for the
    general page area is the global handler in main_window.py (FIX 6);
    see the module docstring for why this alone is not sufficient for
    touchpads, and docs/KNOWN_ISSUES.md for the current status of that
    open issue. Safe to call on a widget tree that is still being
    built or that gets partially destroyed mid-walk (each bind() call
    is individually guarded). add="+" throughout so this never
    clobbers any other binding a widget might already have.
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
        Build a scrollable page shell. `root` (the frame returned here)
        is the grid parent every page module builds its cards into via
        app.add_card(root, row, ...) -- it's just embedded inside a
        scrollable Canvas instead of gridded straight into self.main,
        so pages taller than the window remain fully reachable.

        The canvas is stashed on self._page_canvas so main_window.py's
        global mousewheel handler (FIX 6) always knows which canvas to
        scroll, regardless of which page is currently showing.
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
        # wraplength tracks this specific card's width -- correct even
        # in multi-column layouts (e.g. the Frameworks page's 2-column
        # grid) where a card is narrower than the full page width.
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
