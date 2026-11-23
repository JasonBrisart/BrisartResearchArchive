"""
File: controllers/log_controller.py

Purpose
-------
Provide app.log(text), the single logging entry point for the GUI. Every
call timestamps the message, adds it to the top of the Settings page
Activity Log when that page is showing, and persists it to disk.

Communication / relationships
-----------------------------
- Mixed into gui/main_window.BrisartSuiteApp.
- Called by controllers/system_controller.py, frameworks/TFL/gui_session.py,
  and by gui/main_window.py when a page fails to render.
- Persists through config/activity_log.append_activity_log_entry().
- Writes into app.log_box, which gui/pages/settings_page.py creates.

Settings / parameters
---------------------
- MAX_LOG_LINES (3000): cap on the on-screen box, independent of the
  100-entry cap on the persisted file.
- Timestamps use local time, format YYYY-MM-DD HH:MM:SS.
- trim_text_widget_lines() removes the oldest lines, which are at the
  bottom because new lines are inserted at the top.

Edge cases
----------
- The log box is rebuilt on every navigation; a missing or destroyed box
  is skipped, and the line is still persisted.
- A TclError or AttributeError while writing to the box is swallowed, so
  logging can never crash the action it logs.
- Lines logged while another page is showing reach the Settings page only
  through the persisted file, the next time that page is built.

Known limitations
-----------------
- Local time with no timezone offset.
- The on-screen box holds up to 3000 lines in one session, but the file
  keeps only 100, so a rebuilt Settings page shows fewer than the session
  has logged.

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
        stamped = f"[{timestamp()}] {text}"
        self._write_log_box(stamped + "\n")
        append_activity_log_entry(stamped)


__all__ = ["LogController", "timestamp", "trim_text_widget_lines", "MAX_LOG_LINES"]

