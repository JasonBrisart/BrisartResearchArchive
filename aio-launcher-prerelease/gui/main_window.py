"""
File: gui/main_window.py

Purpose:
Create the Brisart Research Archive root window, initialize application
state and services, build the primary layout, manage page navigation,
and schedule the Archive's self-update check.

Communication / relationships:
- Mixes UIController, SystemController, and LogController into the root.
- Reads persistent configuration through config/runtime.py.
- Initializes framework discovery through config/registries.py.
- Builds navigation through gui/components/sidebar.py.
- Launches frameworks through services/framework_service.py.
- Schedules the Archive updater through services/updater/.
- Renders pages registered by config/registries.py.

Settings / parameters:
- The window opens at 800 by 600 pixels.
- The minimum window size is 800 by 600 pixels.
- STARTUP_UPDATE_CHECK_DELAY_MS controls the Archive update-check delay.
- DEFAULT_PAGE controls the initial page.

Edge cases:
- Page rendering failures produce a visible error and log entry.
- Missing page renderers produce a visible error.
- Mouse-wheel events over Text widgets remain owned by those widgets.
- Destroyed page canvases are checked before scrolling.

Known limitations:
- Touchpad scrolling over the general page area may remain platform
  dependent.
- The application always opens at 800 by 600 rather than restoring the
  previously saved window size.

Examples:
- python main.py
- BrisartSuiteApp().mainloop()
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.registries import (
    DEFAULT_PAGE,
    get_page_registry,
    initialize_framework_registry,
    normalize_page_name,
)
from config.runtime import load_settings
from config.state import AppState
from controllers.log_controller import LogController
from controllers.system_controller import SystemController
from gui.components.page_helpers import (
    UIController,
    mousewheel_units,
    widget_is_or_contains_text,
)
from gui.components.sidebar import build_sidebar
from gui.theme import APP_NAME, APP_VERSION, COLORS, apply_theme
from services.framework_service import FrameworkService
from services.updater.gui_integration import startup_check


EXECUTION_DIR = Path(__file__).resolve().parents[1]

if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))


STARTUP_UPDATE_CHECK_DELAY_MS = 1500
FORCED_STARTUP_WIDTH = 800
FORCED_STARTUP_HEIGHT = 600
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600


class BrisartSuiteApp(
    UIController,
    SystemController,
    LogController,
    tk.Tk,
):
    """Main Brisart Research Archive GUI application."""

    def __init__(self):
        super().__init__()

        self.execution_dir = EXECUTION_DIR
        self.app_name = APP_NAME
        self.app_version = APP_VERSION
        self.settings = load_settings()

        initialize_framework_registry()

        self.title(APP_NAME)
        self.geometry(
            f"{FORCED_STARTUP_WIDTH}x{FORCED_STARTUP_HEIGHT}"
        )
        self.minsize(
            MIN_WINDOW_WIDTH,
            MIN_WINDOW_HEIGHT,
        )
        self.configure(bg=COLORS["bg"])

        self.state = AppState(
            root=self,
            execution_dir=EXECUTION_DIR,
            settings=self.settings,
        )

        self.framework_service = FrameworkService(self)

        self.nav: dict[str, tk.Widget] = {}
        self.main: ttk.Frame | None = None
        self.sidebar: tk.Widget | None = None
        self._page_canvas: tk.Canvas | None = None
        self._current_page_name: str | None = None

        apply_theme(self)
        self._build_layout()

        self.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        self.bind_all(
            "<MouseWheel>",
            self._on_global_mousewheel,
        )
        self.bind_all(
            "<Button-4>",
            self._on_global_mousewheel,
        )
        self.bind_all(
            "<Button-5>",
            self._on_global_mousewheel,
        )

        self.show_page(DEFAULT_PAGE)

        self.after(
            STARTUP_UPDATE_CHECK_DELAY_MS,
            lambda: startup_check(self),
        )

    # ============================================================
    # Mouse-wheel scrolling
    # ============================================================

    def _on_global_mousewheel(self, event) -> None:
        try:
            target_widget = self.winfo_containing(
                event.x_root,
                event.y_root,
            )
        except (tk.TclError, AttributeError):
            target_widget = None

        if widget_is_or_contains_text(target_widget):
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
    # Application-state proxies
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

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        build_sidebar(self)

        self.main = ttk.Frame(
            self,
            style="Bg.TFrame",
        )
        self.main.grid(
            row=0,
            column=1,
            sticky="nsew",
        )
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

    # ============================================================
    # Page navigation
    # ============================================================

    def clear(self) -> None:
        if self.main is None:
            return

        for widget in self.main.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass

        self._page_canvas = None

    def show_page(self, name: str) -> None:
        page_name = normalize_page_name(name)
        self._current_page_name = page_name

        self.clear()
        self._update_nav_selection(page_name)

        render_function = get_page_registry().get(page_name)

        if render_function is None:
            messagebox.showerror(
                "Missing Page",
                f"No page renderer found for: {page_name}",
                parent=self,
            )
            return

        try:
            render_function(self)
        except Exception as exc:
            message = (
                f"The {page_name} page could not be fully displayed: "
                f"{type(exc).__name__}: {exc}"
            )

            try:
                messagebox.showerror(
                    "Page Load Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            try:
                self.log(message)
            except Exception:
                pass

    def _update_nav_selection(self, active_name: str) -> None:
        for navigation_name, button in self.nav.items():
            try:
                button.configure(
                    bg=(
                        COLORS["panel2"]
                        if navigation_name == active_name
                        else "#050812"
                    ),
                    fg=(
                        COLORS["text"]
                        if navigation_name == active_name
                        else COLORS["muted"]
                    ),
                )
            except tk.TclError:
                pass


def main() -> None:
    app = BrisartSuiteApp()
    app.mainloop()


if __name__ == "__main__":
    main()