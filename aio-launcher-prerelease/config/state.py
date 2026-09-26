"""
File: config/state.py

Purpose:
Own the Tk variables that back persisted settings for the live GUI
session.

Communication / relationships:
- Created once by gui/main_window.py, after load_settings().
- Exposed through BrisartSuiteApp proxy properties: selected_framework,
  status_text, output_folder, enable_update_checks, notify_on_update,
  auto_install_updates, and theme.
- Read by controllers/system_controller.py, gui/pages/settings_page.py,
  and services/updater/.

Settings / parameters:
- AppState(root, execution_dir, settings).
- status_text starts as "Ready.".

Edge cases:
- Missing keys fall back to values matching config/runtime.DEFAULT_SETTINGS.
- Values are only coerced with str() or bool(); full normalization
  happens in config/runtime.py.

Known limitations:
- Requires a Tk root, so it is excluded from the headless dependency
  audit in tests/test_merged.py.
- Changes are not written to disk until SystemController.save_config()
  runs.

Examples:
- state = AppState(root=app, execution_dir=EXECUTION_DIR, settings=load_settings())
- state.selected_framework.get()
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
