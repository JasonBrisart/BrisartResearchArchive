"""
Central Tk-backed application state.

main_window.py referenced this as config.state.AppState but it was not
present in the last export - recreated here so the shell has a single,
explicit place for the Tk variables that controllers and pages read from
via BrisartSuiteApp's proxy properties (selected_framework, status_text,
output_folder, enable_update_checks, theme).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any


class AppState:
    """
    Owns the Tk variables backing persisted settings.
    Created once by the main window during startup, after settings have
    been loaded from disk.
    """

    def __init__(self, root: tk.Misc, execution_dir: Path, settings: dict[str, Any]):
        self.root = root
        self.execution_dir = execution_dir

        self.selected_framework = tk.StringVar(
            master=root, value=str(settings.get("default_framework", "TFL"))
        )
        self.status_text = tk.StringVar(master=root, value="Ready.")
        self.output_folder = tk.StringVar(
            master=root, value=str(settings.get("output_folder", "outputs"))
        )
        self.enable_update_checks = tk.BooleanVar(
            master=root, value=bool(settings.get("enable_update_checks", True))
        )
        self.theme = tk.StringVar(master=root, value=str(settings.get("theme", "dark")))


__all__ = ["AppState"]
