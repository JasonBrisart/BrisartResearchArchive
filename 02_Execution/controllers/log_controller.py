"""
File: controllers/log_controller.py

Purpose
-------
Provide app.log(text), the single logging entry point for the GUI.
Every call updates the status text, inserts a timestamped line at the
top of the Settings page Activity Log when it is showing, and persists
the same line to disk.

Communication / relationships
-----------------------------
- Mixed into gui/main_window.BrisartSuiteApp.
- Called by controllers/system_controller.py, frameworks/TFL/gui_session.py, and
  page-render failures in gui/main_window.py.
- Persists through config/activity_log.append_activity_log_entry().
- Writes into app.log_box, created by gui/pages/settings_page.py.

Settings / parameters
---------------------
- MAX_LOG_LINES (3000) caps the on-screen box, independently of the
  100-entry cap on the persisted file.
- Timestamps use local time, format YYYY-MM-DD HH:MM:SS.

Edge cases
----------
- The log box is rebuilt on every navigation; a destroyed box is
  detected and skipped, and the line is still persisted.
- TclError during a write is swallowed so logging can never crash the
  action being logged.

Known limitations
-----------------
- Local time with no timezone offset.

Examples
--------
- app.log("TFL session started")
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime

from config.activity_log import append_activity_log_entry

MAX_LOG_LINES = 3000


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def trim_text_widget_lines(widget: tk.Text, max_lines: int = MAX_LOG_LINES) -> None:
    """New lines are inserted at the top, so the oldest lines are at the bottom."""
    try:
        line_count = int(widget.index("end-1c").split(".", 1)[0])
        if line_count > max_lines:
            widget.delete(f"{max_lines + 1}.0", "end")
    except (tk.TclError, ValueError, AttributeError):
        pass


class LogController:
    def _write_log_box(self, line: str) -> None:
        widget = getattr(self, "log_box", None)
        try:
            if widget is None or not widget.winfo_exists():
                return
            widget.insert("1.0", line)
            trim_text_widget_lines(widget)
            widget.see("1.0")
        except (AttributeError, tk.TclError):
            pass

    def log(self, text: str) -> None:
        message = str(text)
        try:
            self.status_text.set(message)
        except (AttributeError, tk.TclError):
            pass
        stamped = f"[{timestamp()}] {message}"
        self._write_log_box(stamped + "\n")
        append_activity_log_entry(stamped)


__all__ = ["LogController", "timestamp", "trim_text_widget_lines", "MAX_LOG_LINES"]
