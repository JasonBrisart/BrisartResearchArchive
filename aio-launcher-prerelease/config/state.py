"""
File: config/state.py

Purpose
-------
Own the Tk variables that back persisted settings for the live GUI
session.

Communication / relationships
-----------------------------
- Created once by gui/main_window.py after load_settings().
- Exposed through BrisartSuiteApp proxy properties: status_text,
  output_folder, enable_update_checks, notify_on_update,
  auto_install_updates, and theme.
- Read by controllers/system_controller.py, gui/pages/settings_page.py,
  and services/updater/.

Settings / parameters
---------------------
- AppState(root, execution_dir, settings).
- status_text starts as "Ready.".

Edge cases
----------
- Missing keys fall back to config/runtime.DEFAULT_SETTINGS.
- Values are only coerced here; full validation happens in
  config/runtime.normalize_settings() when saving.

Known limitations
-----------------
- Requires a Tk root, so it is GUI-only.
- Changes reach disk only when SystemController.save_config() runs.

Examples
--------
- state = AppState(root=app, execution_dir=EXECUTION_DIR, settings=load_settings())
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any

from config.runtime import DEFAULT_SETTINGS


class AppState:
    def __init__(self, root: tk.Misc, execution_dir: Path, settings: dict[str, Any]):
        def value(key):
            return settings.get(key, DEFAULT_SETTINGS[key])

        self.root = root
        self.execution_dir = execution_dir
        self.status_text = tk.StringVar(master=root, value="Ready.")
        self.output_folder = tk.StringVar(master=root, value=str(value("output_folder")))
        self.enable_update_checks = tk.BooleanVar(master=root, value=bool(value("enable_update_checks")))
        self.notify_on_update = tk.BooleanVar(master=root, value=bool(value("notify_on_update")))
        self.auto_install_updates = tk.BooleanVar(master=root, value=bool(value("auto_install_updates")))
        self.theme = tk.StringVar(master=root, value=str(value("theme")))


__all__ = ["AppState"]
