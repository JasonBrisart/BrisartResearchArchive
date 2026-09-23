"""
Central Tk-backed application state.

Owns the Tk variables backing persisted settings, read by controllers
and pages via BrisartSuiteApp's proxy properties.
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
        self.notify_on_update = tk.BooleanVar(
            master=root, value=bool(settings.get("notify_on_update", True))
        )
        self.auto_install_updates = tk.BooleanVar(
            master=root, value=bool(settings.get("auto_install_updates", True))
        )
        self.theme = tk.StringVar(master=root, value=str(settings.get("theme", "dark")))


__all__ = ["AppState"]
