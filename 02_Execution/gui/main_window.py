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
The window ALWAYS opens at exactly 800x600 on launch, every single
time, regardless of whatever window_width/window_height value is
currently saved in user_settings.json.

This is deliberately DIFFERENT from a normal "default" value: a
default only applies the first time, before any settings file exists
-- once the user resizes the window and closes the app (which saves
the new size via SystemController.save_config()), a plain default
would silently stop applying, and the app would keep reopening at
whatever size was last saved instead. That was the previous behavior,
and it's why simply setting DEFAULT_SETTINGS to 800x600 in
config/runtime.py was not suffient on its own to guarantee an 800x600
launch for anyone who had already resized and saved a different size.

The fix here is unconditional: self.geometry() below is called with
the literal FORCED_STARTUP_WIDTH/FORCED_STARTUP_HEIGHT constants, NOT
self.settings['window_width']/['window_height'] -- the saved values
are never read for this purpose anymore. Resizing still works exactly
as before during the session, and the new size is still written to
user_settings.json when the app closes (SystemController.save_config()
is unchanged) -- that persisted value is just never used to set the
STARTUP geometry anymore. If some other feature is ever added that
legitimately wants to know "what size was the window last closed at,"
that data is still there in settings; it's only the launch-time
self.geometry() call that ignores it now.

self.minsize(800, 600) below is a SEPARATE hard floor enforced
directly by Tk, independent of the startup geometry -- it stops the
user from ever resizing the window smaller than 800x600 during the
session. It happens to use the same 800x600 numbers as
FORCED_STARTUP_WIDTH/HEIGHT, but conceptually serves a different
purpose (a floor on resizing, not a startup value) and remains here as
its own constant pairing with config.runtime.MIN_WINDOW_WIDTH/
MIN_WINDOW_HEIGHT for that reason.

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

TOOLING UPDATE CHECK, specifically:
self.tool_update_availability is a plain dict (never persisted -- it
only ever reflects the current session's most recent check), keyed by
tool_id, populated by SystemController.check_tool_updates() whenever a
check finds at least one installed Tooling-page program with a newer
version published. gui/pages/tooling_page.py reads this dict directly
to decide which programs show an "Update to vX.Y.Z" button, alongside
their existing Run/Open Folder buttons. This dict simply does not
exist as a populated attribute (falls back to {} via getattr with a
default) until the first check of the current session has completed,
so the Tooling page shows no update buttons at all on first render,
before that first check finishes.

The automatic Tooling update check is chained to run 1 second AFTER
the Archive's own self-update startup check (see
STARTUP_TOOLING_CHECK_DELAY_MS below), rather than at the same moment,
so the two background checks don't compete for the network or the UI
thread's attention during the first seconds after launch.

self._current_page_name tracks whichever page name was most recently
passed to show_page(), after alias normalization. This is read by
SystemController's Tooling wrappers (download_tool/check_tool_updates)
to decide whether to bother re-rendering the Tooling page after a
background operation finishes -- there is no reason to force a Tooling
page render if the user has already navigated to a different page in
the meantime.
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

# Delay before the automatic Tooling update check fires, staggered
# 1 second after the Archive's own self-update check above -- see the
# TOOLING UPDATE CHECK section of this module's docstring for why.
STARTUP_TOOLING_CHECK_DELAY_MS = STARTUP_UPDATE_CHECK_DELAY_MS + 1000

# The window ALWAYS opens at exactly this size on every launch, no
# matter what -- never read from self.settings['window_width']/
# ['window_height']. See the WINDOW SIZE section of this module's
# docstring for why this is deliberately unconditional rather than a
# one-time-only default.
FORCED_STARTUP_WIDTH = 800
FORCED_STARTUP_HEIGHT = 600

# Hard floor enforced directly by Tk via self.minsize() below. Must stay
# equal to config.runtime.MIN_WINDOW_WIDTH/MIN_WINDOW_HEIGHT -- see the
# WINDOW SIZE section of this module's docstring for why this is a
# separate concept from FORCED_STARTUP_WIDTH/HEIGHT above, even though
# both currently use the same 800x600 numbers.
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600


class BrisartSuiteApp(UIController, SystemController, LogController, tk.Tk):
    """
    Main GUI application shell.

    Owns: root Tk window lifecycle, app-wide state initialization,
    framework service initialization, sidebar/main layout,
    and page navigation.

    Controllers own: system actions, logging, framework launch
    wrappers, update wrappers, Tooling-page actions, settings
    persistence.
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
        # Deliberately hardcoded -- NOT self.settings['window_width']/
        # ['window_height'] -- so the window always opens at exactly
        # 800x600, every launch, regardless of whatever size was saved
        # from a previous session. See the WINDOW SIZE section of this
        # module's docstring for the full rationale.
        self.geometry(f"{FORCED_STARTUP_WIDTH}x{FORCED_STARTUP_HEIGHT}")
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
        # Tracks the most recently shown page name (post-alias-
        # normalization) -- see the TOOLING UPDATE CHECK section of
        # this module's docstring for why SystemController reads this.
        self._current_page_name: str | None = None
        # Populated by SystemController.check_tool_updates() -- see the
        # TOOLING UPDATE CHECK section of this module's docstring.
        self.tool_update_availability: dict = {}

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

        # Automatic Tooling update check, staggered 1 second after the
        # Archive's own self-update check above -- see the TOOLING
        # UPDATE CHECK section of this module's docstring for why.
        # Silent if nothing needs updating; shows a summary popup and
        # updates gui/pages/tooling_page.py's buttons otherwise.
        self.after(STARTUP_TOOLING_CHECK_DELAY_MS, self.check_tool_updates)

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
        self._current_page_name = page_name
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
