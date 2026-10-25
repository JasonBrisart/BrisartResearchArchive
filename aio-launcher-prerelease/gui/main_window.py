"""
File: gui/main_window.py

Purpose
-------
Create the Brisart Research Archive window: load settings, build the
layout, handle page navigation and mouse-wheel scrolling, and schedule
the startup update check.

Communication / relationships
-----------------------------
- Mixes UIController, SystemController, and LogController into the Tk
  root.
- Loads settings through config/runtime.py into config/state.AppState.
- Builds the sidebar with gui/components/sidebar.py and resolves pages
  with gui/navigation.py.
- Schedules services/updater/gui_integration.startup_check().

Settings / parameters
---------------------
- Opens at 800x600; minimum size 800x600 (must match
  config/runtime.MIN_WINDOW_WIDTH/HEIGHT).
- STARTUP_UPDATE_CHECK_DELAY_MS: 1500.
- DEFAULT_PAGE comes from gui/navigation.py.

Edge cases
----------
- A page that fails to render shows an error dialog and is logged; the
  window stays usable.
- The wheel is left to Text widgets under the cursor; destroyed page
  canvases are checked before scrolling.

Known limitations
-----------------
- Always opens at 800x600 instead of the saved size.
- Touchpad two-finger scrolling over the general page area does not work
  (a physical mouse wheel does). To diagnose, log every <MouseWheel>,
  <Button-4>, <Button-5>, and <Shift-MouseWheel> event while scrolling
  with the touchpad; if Tk receives none, the fix is outside the Archive.

Examples
--------
- python main.py
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.runtime import load_settings
from config.state import AppState
from controllers.log_controller import LogController
from controllers.system_controller import SystemController
from gui.components.page_helpers import UIController, mousewheel_units, widget_is_or_contains_text
from gui.components.sidebar import build_sidebar
from gui.navigation import DEFAULT_PAGE, get_page_renderer, normalize_page_name
from gui.theme import APP_NAME, APP_VERSION, COLORS, apply_theme
from services.updater.gui_integration import startup_check

EXECUTION_DIR = Path(__file__).resolve().parents[1]
STARTUP_UPDATE_CHECK_DELAY_MS = 1500
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600


class BrisartSuiteApp(UIController, SystemController, LogController, tk.Tk):
    def __init__(self):
        super().__init__()
        self.execution_dir = EXECUTION_DIR
        self.app_name = APP_NAME
        self.app_version = APP_VERSION
        self.settings = load_settings()
        self.title(APP_NAME)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.configure(bg=COLORS["bg"])
        self.app_state = AppState(root=self, execution_dir=EXECUTION_DIR, settings=self.settings)
        self.nav: dict[str, tk.Widget] = {}
        self.main: ttk.Frame | None = None
        self._page_canvas: tk.Canvas | None = None
        self.tfl_session = None
        apply_theme(self)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, self._on_global_mousewheel)
        self.show_page(DEFAULT_PAGE)
        self.after(STARTUP_UPDATE_CHECK_DELAY_MS, lambda: startup_check(self))

    # ---------------------------------------------------------- state proxies
    @property
    def status_text(self):
        return self.app_state.status_text

    @property
    def output_folder(self):
        return self.app_state.output_folder

    @property
    def enable_update_checks(self):
        return self.app_state.enable_update_checks

    @property
    def notify_on_update(self):
        return self.app_state.notify_on_update

    @property
    def auto_install_updates(self):
        return self.app_state.auto_install_updates

    @property
    def theme(self):
        return self.app_state.theme

    # ---------------------------------------------------------- layout
    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        build_sidebar(self)
        self.main = ttk.Frame(self, style="Bg.TFrame")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

    def _on_global_mousewheel(self, event) -> None:
        try:
            target = self.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, AttributeError):
            target = None
        canvas = self._page_canvas
        if widget_is_or_contains_text(target) or canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
            number = getattr(event, "num", None)
            units = -1 if number == 4 else 1 if number == 5 else mousewheel_units(event)
            if units:
                canvas.yview_scroll(units, "units")
        except tk.TclError:
            pass

    # ---------------------------------------------------------- navigation
    def clear(self) -> None:
        for widget in self.main.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self._page_canvas = None

    def show_page(self, name: str) -> None:
        page_name = normalize_page_name(name)
        self.clear()
        for nav_name, button in self.nav.items():
            active = nav_name == page_name
            try:
                button.configure(bg=COLORS["panel2"] if active else "#050812",
                                 fg=COLORS["text"] if active else COLORS["muted"])
            except tk.TclError:
                pass
        render = get_page_renderer(page_name)
        if render is None:
            messagebox.showerror("Missing Page", f"No page named {page_name}.", parent=self)
            return
        try:
            render(self)
        except Exception as exc:
            message = f"The {page_name} page could not be displayed: {type(exc).__name__}: {exc}"
            self.log(message)
            try:
                messagebox.showerror("Page Load Failed", message, parent=self)
            except tk.TclError:
                pass


def main() -> None:
    BrisartSuiteApp().mainloop()


if __name__ == "__main__":
    main()
