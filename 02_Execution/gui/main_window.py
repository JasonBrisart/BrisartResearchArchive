"""
gui/main_window.py
BrisartSuiteApp -- the Tk root window and application shell. Owns
window lifecycle, app-wide state init, framework service init, the
sidebar/main two-column layout, and page navigation (show_page()).
Mixes in UIController (page_shell/add_card), SystemController (all
the app-level actions), and LogController (status/logging) so every
page module can just call app.<method>() directly without importing
any of those modules itself.

WINDOW SIZE, specifically:
Defaults to 800x600 (see config/runtime.DEFAULT_SETTINGS) rather than
the old 1220x780, so the app opens at a reasonable, non-bloated size on
a typical display -- the user can always resize larger afterward, and
that new size is what gets persisted (see SystemController.save_config
in controllers/system_controller.py). self.minsize(800, 600) below is
a SEPARATE hard floor enforced directly by Tk, independent of whatever
is in settings -- it must be kept in sync with
config.runtime.MIN_WINDOW_WIDTH/MIN_WINDOW_HEIGHT, since either one
alone silently overriding the other back up would defeat the point of
a smaller default (Tk's minsize() always wins over a smaller
geometry() request, and normalize_int() in config/runtime.py always
wins over a smaller saved setting).

MOUSEWHEEL SCROLLING, specifically -- FIX 6, the current mechanism for
the general page area:
Every page is wrapped in a scrollable Canvas by
gui.components.page_helpers.UIController.page_shell(). Earlier fixes
(see page_helpers.py's module docstring for the full history)
correctly got a physical mouse wheel working over the entire page, but
a touchpad two-finger scroll gesture still did nothing at all, no
matter which widget was hovered.

Root cause hypothesis: Tk keeps an internal cache of "which widget is
currently under the pointer," used to decide which widget receives a
<MouseWheel> event. That cache is only ever updated by real <Motion>
events -- the cursor physically moving. A mouse wheel almost always
has tiny hand jitter right before/during scrolling, which keeps the
cache correct. A touchpad two-finger scroll gesture moves the cursor
ZERO pixels by design (the OS deliberately separates "finger scroll"
from "pointer position"), so if the cursor was already resting
somewhere before the gesture started, Tk's cached "current widget" for
dispatch purposes is stale -- and the event goes to whatever that
stale cache says, not the widget actually visually under the
touchpad-controlled cursor. Binding directly on every widget (as the
previous fix did) doesn't help, because the event may never reach any
of those widgets in the first place.

The fix: bind ONE handler here, at the Tk root, instead of per-widget.
Inside _on_global_mousewheel(), the target widget is resolved via
self.winfo_containing(event.x_root, event.y_root) -- a live, direct
query of the real OS cursor position -- instead of trusting whatever
widget Tk's own (stale) internal dispatch decided on for this event.
This sidesteps the stale-cache problem entirely: it does not matter
what Tk thinks the "current widget" is, only where the cursor is
actually, physically sitting right now.

NOTE: touchpad scrolling over the general page area remains an open,
unresolved issue even with this fix in place -- see
docs/KNOWN_ISSUES.md for the current status, confirmed environment
details, what has been ruled out so far, and the next diagnostic step.

Bound once, here, at app startup -- NOT per-page and NOT via
bind_scrolling_recursively() (which remains in page_helpers.py as a
defensive secondary layer for real mouse wheels, but is not what
touchpad scrolling depends on). self._page_canvas (kept in sync by
page_helpers.UIController.page_shell() on every page render) is always
what actually gets scrolled, regardless of which specific widget the
cursor's real screen coordinates resolve to.
"""
from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.registries import DEFAULT_PAGE, get_page_registry, initialize_framework_registry, normalize_page_name
from config.runtime import load_settings
from config.state import AppState
from controllers import LogController, SystemController
from gui.components.page_helpers import UIController, mousewheel_units, widget_is_or_contains_text
from gui.components.sidebar import build_sidebar
from gui.theme import APP_NAME, APP_VERSION, COLORS, apply_theme
from services.framework_service import FrameworkService
from services.updater.gui_integration import startup_check

EXECUTION_DIR = Path(__file__).resolve().parents[1]
if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))

# Delay before the automatic startup update check fires, in milliseconds.
# Gives the window time to finish building and become visible first, so
# the check never competes with initial layout for the UI thread.
STARTUP_UPDATE_CHECK_DELAY_MS = 1500

# Hard floor enforced directly by Tk via self.minsize() below. Must stay
# equal to config.runtime.MIN_WINDOW_WIDTH/MIN_WINDOW_HEIGHT -- see the
# WINDOW SIZE section of this module's docstring for why both need to
# move together.
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600


class BrisartSuiteApp(UIController, SystemController, LogController, tk.Tk):
    """
    Main GUI application shell.

    Owns: root Tk window lifecycle, app-wide state initialization,
    framework service initialization, sidebar/main layout,
    and page navigation.

    Controllers own: system actions, logging, framework launch
    wrappers, update wrappers, settings persistence.
    """

    def __init__(self):
        super().__init__()
        self.execution_dir = EXECUTION_DIR
        self.app_name = APP_NAME
        self.app_version = APP_VERSION
        self.settings = load_settings()

        # Populate the framework registry before any page renders.
        initialize_framework_registry()

        self.title(APP_NAME)
        self.geometry(f"{self.settings['window_width']}x{self.settings['window_height']}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.configure(bg=COLORS["bg"])

        self.state = AppState(root=self, execution_dir=EXECUTION_DIR, settings=self.settings)
        self.framework_service = FrameworkService(self)

        self.nav: dict[str, tk.Widget] = {}
        self.main: ttk.Frame | None = None
        self.sidebar: tk.Widget | None = None
        # Set by page_helpers.UIController.page_shell() on every page
        # render; this is what _on_global_mousewheel() below actually
        # scrolls, regardless of which specific widget the real cursor
        # position resolves to.
        self._page_canvas: tk.Canvas | None = None

        apply_theme(self)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Bound ONCE, at the root, for the lifetime of the app -- see
        # the MOUSEWHEEL SCROLLING (FIX 6) section of this module's
        # docstring, and docs/KNOWN_ISSUES.md for the current status of
        # touchpad scrolling on the general page area.
        self.bind_all("<MouseWheel>", self._on_global_mousewheel)
        self.bind_all("<Button-4>", self._on_global_mousewheel)
        self.bind_all("<Button-5>", self._on_global_mousewheel)

        self.show_page(DEFAULT_PAGE)

        # Automatic update check, once, shortly after launch. Respects
        # "Enable update checks" (does nothing at all if disabled) and
        # "Automatically download and install updates" (installs a
        # verified release immediately if enabled; otherwise just
        # downloads + verifies and leaves installation to the user).
        # Runs on a background thread; never blocks window startup.
        self.after(STARTUP_UPDATE_CHECK_DELAY_MS, lambda: startup_check(self))

    # ============================================================
    # Mousewheel scrolling (FIX 6) -- see module docstring
    # ============================================================
    def _on_global_mousewheel(self, event) -> None:
        """
        Single root-level handler for every <MouseWheel>/<Button-4>/
        <Button-5> event in the entire app, for both a real mouse wheel
        and a touchpad two-finger scroll gesture. Resolves the actual
        widget under the cursor via a live screen-coordinate query
        (winfo_containing) rather than trusting Tk's own internal
        dispatch decision for this event -- see the module docstring
        for why that distinction matters, and docs/KNOWN_ISSUES.md for
        the current status of touchpad scrolling on the general page
        area.
        """
        try:
            target_widget = self.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, AttributeError):
            target_widget = None

        if widget_is_or_contains_text(target_widget):
            # Let the Text widget's own native scrolling handle it --
            # e.g. the Activity Log or Update Output boxes -- instead
            # of also scrolling the page underneath them.
            return

        canvas = self._page_canvas
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
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

    # ============================================================
    # App State Proxies
    # ============================================================
    @property
    def selected_framework(self):
        return self.state.selected_framework

    @property
    def status_text(self):
        return self.state.status_text

    @property
    def output_folder(self):
        return self.state.output_folder

    @property
    def enable_update_checks(self):
        return self.state.enable_update_checks

    @property
    def notify_on_update(self):
        return self.state.notify_on_update

    @property
    def auto_install_updates(self):
        return self.state.auto_install_updates

    @property
    def theme(self):
        return self.state.theme

    # ============================================================
    # Layout
    # ============================================================
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        build_sidebar(self)
        self.main = ttk.Frame(self, style="Bg.TFrame")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

    # ============================================================
    # Page Navigation
    # ============================================================
    def clear(self) -> None:
        if self.main is None:
            return
        for widget in self.main.winfo_children():
            widget.destroy()
        self._page_canvas = None

    def show_page(self, name: str) -> None:
        page_name = normalize_page_name(name)
        self.clear()
        self._update_nav_selection(page_name)
        render_func = get_page_registry().get(page_name)
        if render_func is None:
            messagebox.showerror("Missing Page", f"No page renderer found for: {page_name}", parent=self)
            return
        try:
            render_func(self)
        except Exception as exc:
            # Previously unguarded: every other action in this app
            # (framework launch, settings save, update check, document
            # viewer) wraps its work in try/except with a visible error
            # dialog and a log entry. Page rendering was the one
            # exception - a broken page would silently leave the user
            # looking at a half-built blank screen with no indication
            # anything went wrong.
            message = f"The {page_name} page could not be fully displayed: {type(exc).__name__}: {exc}"
            try:
                messagebox.showerror("Page Load Failed", message, parent=self)
            except tk.TclError:
                pass
            if hasattr(self, "log"):
                try:
                    self.log(message)
                except Exception:
                    pass

    def _update_nav_selection(self, active_name: str) -> None:
        for nav_name, button in self.nav.items():
            try:
                button.configure(
                    bg=COLORS["panel2"] if nav_name == active_name else "#050812",
                    fg=COLORS["text"] if nav_name == active_name else COLORS["muted"],
                )
            except tk.TclError:
                pass


def main():
    app = BrisartSuiteApp()
    app.mainloop()


if __name__ == "__main__":
    main()
