"""
gui/main_window.py
BrisartSuiteApp -- the Tk root window and application shell. Owns window
lifecycle, app-wide state init, framework service init, the sidebar/main
two-column layout, and page navigation (show_page()). Mixes in
UIController (page_shell/add_card), SystemController (all app-level
actions), and LogController (status/logging) so every page module can
call app.<method>() directly without importing those modules itself.

WINDOW SIZE
The window always opens at exactly 800x600 on launch, via the literal
FORCED_STARTUP_WIDTH/HEIGHT constants -- NOT self.settings['window_width']
/['window_height']. This is intentionally unconditional rather than a
one-time default: a plain default stops applying once the user resizes
and closes the app (which saves the new size), so the app would reopen
at the last saved size instead. Resizing still works during the session
and the new size is still written to user_settings.json on close; that
persisted value is simply never read to set the startup geometry.
self.minsize(800, 600) is a SEPARATE hard floor on resizing, enforced
directly by Tk, and must stay in sync with
config.runtime.MIN_WINDOW_WIDTH/MIN_WINDOW_HEIGHT.

MOUSEWHEEL SCROLLING
Every page is wrapped in a scrollable Canvas by page_helpers.page_shell().
A single handler is bound once here at the Tk root, for the lifetime of
the app, rather than per-widget. Inside _on_global_mousewheel(), the
target widget is resolved via self.winfo_containing(event.x_root,
event.y_root) -- a live query of the real cursor position -- instead of
trusting Tk's internal pointer cache, which a touchpad two-finger scroll
(cursor moves zero pixels) can leave stale. self._page_canvas (kept in
sync by page_shell() on every render) is always what gets scrolled.
Touchpad scrolling over the general page area remains an open issue even
with this handler; see docs/KNOWN_ISSUES.md.

TOOLING UPDATE CHECK
self.tool_update_availability is a plain dict (never persisted; reflects
only the current session's most recent check), keyed by tool_id,
populated by SystemController.check_tool_updates() when a check finds an
installed program with a newer published version. gui/pages/tooling_page.py
reads it to decide which programs show an "Update to vX.Y.Z" button. It
falls back to {} until the first check completes, so no update buttons
show on first render. The automatic Tooling check is chained to run
STARTUP_TOOLING_CHECK_DELAY_MS after the Archive's own self-update check
so the two don't compete for the network/UI thread at launch.
self._current_page_name tracks the most recently shown page (post-alias)
so SystemController's Tooling wrappers can skip re-rendering the Tooling
page if the user has navigated elsewhere.
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
# Delay before the automatic Tooling update check fires, staggered 1
# second after the Archive's own self-update check above.
STARTUP_TOOLING_CHECK_DELAY_MS = STARTUP_UPDATE_CHECK_DELAY_MS + 1000
# The window always opens at exactly this size on every launch, never
# read from self.settings -- see the WINDOW SIZE section of the module
# docstring for why this is unconditional rather than a one-time default.
FORCED_STARTUP_WIDTH = 800
FORCED_STARTUP_HEIGHT = 600
# Hard floor enforced directly by Tk via self.minsize() below. Must stay
# equal to config.runtime.MIN_WINDOW_WIDTH/MIN_WINDOW_HEIGHT, and is a
# separate concept from FORCED_STARTUP_WIDTH/HEIGHT (a resize floor, not
# a startup value) even though both use the same 800x600 numbers.
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
class BrisartSuiteApp(UIController, SystemController, LogController, tk.Tk):
    """
    Main GUI application shell.

    Owns: root Tk window lifecycle, app-wide state initialization,
    framework service initialization, sidebar/main layout, and page
    navigation. Controllers own: system actions, logging, framework
    launch wrappers, update wrappers, Tooling-page actions, settings
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
        # Hardcoded 800x600 (not self.settings) so the window always opens
        # at that size -- see the WINDOW SIZE section of the docstring.
        self.geometry(f"{FORCED_STARTUP_WIDTH}x{FORCED_STARTUP_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.configure(bg=COLORS["bg"])
        self.state = AppState(root=self, execution_dir=EXECUTION_DIR, settings=self.settings)
        self.framework_service = FrameworkService(self)
        self.nav: dict[str, tk.Widget] = {}
        self.main: ttk.Frame | None = None
        self.sidebar: tk.Widget | None = None
        # Set by page_helpers.page_shell() on every page render; this is
        # what _on_global_mousewheel() scrolls.
        self._page_canvas: tk.Canvas | None = None
        # Most recently shown page name (post-alias) -- read by
        # SystemController to decide whether to re-render the Tooling page.
        self._current_page_name: str | None = None
        # Populated by SystemController.check_tool_updates().
        self.tool_update_availability: dict = {}
        apply_theme(self)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # Bound once, at the root, for the lifetime of the app -- see the
        # MOUSEWHEEL SCROLLING section of the docstring, and
        # docs/KNOWN_ISSUES.md for the open touchpad issue.
        self.bind_all("<MouseWheel>", self._on_global_mousewheel)
        self.bind_all("<Button-4>", self._on_global_mousewheel)
        self.bind_all("<Button-5>", self._on_global_mousewheel)
        self.show_page(DEFAULT_PAGE)
        # Automatic update check, once, shortly after launch. Respects
        # "Enable update checks" and "Automatically download and install
        # updates". Runs on a background thread; never blocks startup.
        self.after(STARTUP_UPDATE_CHECK_DELAY_MS, lambda: startup_check(self))
        # Automatic Tooling update check, staggered after the Archive's
        # own self-update check. Silent if nothing needs updating.
        self.after(STARTUP_TOOLING_CHECK_DELAY_MS, self.check_tool_updates)
    # ============================================================
    # Mousewheel scrolling -- see module docstring
    # ============================================================
    def _on_global_mousewheel(self, event) -> None:
        """
        Single root-level handler for every <MouseWheel>/<Button-4>/
        <Button-5> event in the app. Resolves the widget under the cursor
        via a live screen-coordinate query (winfo_containing) rather than
        Tk's internal dispatch, so a touchpad gesture that moves the
        cursor zero pixels still scrolls the right region. See the module
        docstring and docs/KNOWN_ISSUES.md.
        """
        try:
            target_widget = self.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, AttributeError):
            target_widget = None
        if widget_is_or_contains_text(target_widget):
            # Let the Text widget's own native scrolling handle it (e.g.
            # the Activity Log or Update Output boxes) instead of also
            # scrolling the page underneath them.
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
            # Page rendering is guarded like every other app action: a
            # broken page shows a visible error dialog and a log entry
            # rather than leaving the user at a half-built blank screen.
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
