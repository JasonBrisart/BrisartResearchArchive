from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.registries import DEFAULT_PAGE, get_page_registry, initialize_framework_registry, normalize_page_name
from config.runtime import load_settings
from config.state import AppState
from controllers import LogController, SystemController
from gui.components.page_helpers import UIController
from gui.components.sidebar import build_sidebar
from gui.theme import APP_NAME, APP_VERSION, COLORS, apply_theme
from services.framework_service import FrameworkService

EXECUTION_DIR = Path(__file__).resolve().parents[1]
if str(EXECUTION_DIR) not in sys.path:
    sys.path.insert(0, str(EXECUTION_DIR))


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
        self.minsize(1060, 700)
        self.configure(bg=COLORS["bg"])

        self.state = AppState(root=self, execution_dir=EXECUTION_DIR, settings=self.settings)
        self.framework_service = FrameworkService(self)

        self.nav: dict[str, tk.Widget] = {}
        self.main: ttk.Frame | None = None
        self.sidebar: tk.Widget | None = None

        apply_theme(self)
        self._build_layout()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_page(DEFAULT_PAGE)

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