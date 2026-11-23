"""
File: gui/main_window.py

Purpose
-------
Create the Brisart Research Archive window: load settings, build the
layout, and handle page navigation and mouse-wheel scrolling.

Communication / relationships
-----------------------------
- Mixes UIController, SystemController, and LogController into the Tk root.
- Loads settings through config/runtime.py and owns the one live Tk
  variable the pages bind to: output_folder.
- Builds the sidebar with gui/components/sidebar.py and resolves pages
  with gui/navigation.py; applies gui/theme.apply_theme().
- run.py calls main() for the GUI.

Settings / parameters
---------------------
- WINDOW_WIDTH x WINDOW_HEIGHT: opens at, and cannot shrink below, 800x600.
- EXECUTION_DIR: the folder holding run.py; the Settings page shows it and
  the document viewer's file dialog starts there.
- DEFAULT_PAGE comes from gui/navigation.py.

Edge cases
----------
- A page that fails to render shows an error dialog and is logged; the
  window stays usable.
- An unknown page name shows a "Missing Page" dialog.
- The global wheel handler leaves the wheel to Text and Listbox widgets
  under the cursor and checks that the page canvas still exists before
  scrolling it.
- Each page visit destroys and rebuilds the page, so in-page state (a
  report, a selection) is not kept when you navigate away.

Known limitations
-----------------
- Window size and position are not remembered between launches.
- Touchpad two-finger scrolling over the general page area does not work (a
  physical mouse wheel does). To diagnose, log every <MouseWheel>,
  <Button-4>, <Button-5>, and <Shift-MouseWheel> event while scrolling with
  the touchpad; if Tk receives none, the fix is outside the Archive.

Examples
--------
- python run.py
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from config.runtime import load_settings
from controllers.log_controller import LogController
from controllers.system_controller import SystemController
from gui.components.page_helpers import UIController, mousewheel_units, widget_scrolls_itself
from gui.components.sidebar import build_sidebar
from gui.navigation import DEFAULT_PAGE, get_page_renderer, normalize_page_name
from gui.theme import APP_NAME, APP_VERSION, COLORS, apply_theme

EXECUTION_DIR = Path(__file__).resolve().parents[1]
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
        self.output_folder = tk.StringVar(master=self, value=self.settings["output_folder"])
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
        ancestor = target
        while ancestor is not None and ancestor is not canvas:
            ancestor = getattr(ancestor, "master", None)
        if ancestor is None or widget_scrolls_itself(target) or canvas is None:
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
                button.configure(bg=COLORS["panel2"] if active else COLORS["sidebar"],
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

