"""
File: controllers/log_controller.py

Purpose:
Provide app.log(text), the single logging entry point for the whole
application. Every call updates the status text, writes a timestamped
line into any live Activity Log widget, and persists the same line to
disk.

Communication / relationships:
- Mixed into gui/main_window.BrisartSuiteApp.
- Called by controllers/system_controller.py,
  services/framework_service.py, frameworks/TFL/session_gui.py, and
  page-render failures in gui/main_window.py.
- Persists through config/activity_log.append_activity_log_entry().
- Timestamps come from services/timestamps.py.
- Writes into log_box (gui/pages/settings_page.py) and home_log_box
  (reserved for a future Dashboard log).

Settings / parameters:
- MAX_LOG_LINES (3000): caps the on-screen widget, independent of the
  100-entry cap on the persisted file.
- New lines are inserted at "1.0", so the newest entry is always at the
  top; trimming removes the oldest lines from the bottom.

Edge cases:
- Widget references are checked for liveness before every write, since
  pages are destroyed and rebuilt on navigation. Dead references are
  deleted, never written to.
- TclError during a write is swallowed.
- Lines are persisted to disk even when no widget currently exists.

Known limitations:
- No current page creates home_log_box.
- The on-screen log resets on every page rebuild; the Settings page
  repopulates it from the persisted history.

Examples:
- app.log("TFL session started: 20260926-101500-a1b2c3d4")
- append_log_line(text_widget, "Manual note")
"""
from __future__ import annotations
import tkinter as tk
from config.activity_log import append_activity_log_entry
from services.timestamps import timestamp
MAX_LOG_LINES = 3000
def trim_text_widget_lines(widget: tk.Text, max_lines: int = MAX_LOG_LINES) -> None:
    """
    Keep a Tk Text widget from growing forever. Tk line indexes are
    1-based. New entries are inserted at the top, so the oldest content
    is whatever has been pushed to the BOTTOM over time; when the widget
    exceeds max_lines, everything past line max_lines (the oldest tail)
    is deleted, keeping the most recent max_lines lines at the top.
    """
    try:
        line_count = int(widget.index("end-1c").split(".", 1)[0])
    except (tk.TclError, ValueError, AttributeError):
        return
    if line_count <= max_lines:
        return
    try:
        widget.delete(f"{max_lines + 1}.0", "end")
    except tk.TclError:
        pass
def append_log_line(widget: tk.Text, text: str) -> None:
    """Standalone helper mirroring LogController._write_log_widget()'s
    newest-on-top insert behavior, for any caller that holds a Text
    widget reference directly rather than going through LogController."""
    try:
        widget.insert("1.0", f"[{timestamp()}] {text}\n")
        trim_text_widget_lines(widget)
        widget.see("1.0")
    except tk.TclError:
        pass
class LogController:
    """
    Central logging helper for the status bar and page log boxes. Page
    widgets are recreated during navigation, so logging verifies that a
    stored widget reference still identifies a live Tk widget before
    writing to it.
    """
    @staticmethod
    def _widget_is_alive(widget) -> bool:
        if widget is None:
            return False
        try:
            return bool(widget.winfo_exists())
        except (AttributeError, tk.TclError):
            return False
    def _write_log_widget(self, attribute_name: str, message: str) -> None:
        widget = getattr(self, attribute_name, None)
        if not self._widget_is_alive(widget):
            if hasattr(self, attribute_name):
                try:
                    delattr(self, attribute_name)
                except AttributeError:
                    pass
            return
        try:
            # Newest-on-top: inserted at "1.0" so the most recent entry
            # is always the first thing visible in the box.
            widget.insert("1.0", message)
            # trim_text_widget_lines() caps the visual widget's own
            # growth (MAX_LOG_LINES), independent of the 100-entry cap on
            # the persisted activity_log.json file appended below.
            trim_text_widget_lines(widget)
            widget.see("1.0")
        except tk.TclError:
            try:
                delattr(self, attribute_name)
            except AttributeError:
                pass
    def log(self, text: str) -> None:
        message_text = str(text)
        try:
            self.status_text.set(message_text)
        except (AttributeError, tk.TclError):
            pass
        stamped = f"[{timestamp()}] {message_text}\n"
        self._write_log_widget("log_box", stamped)
        self._write_log_widget("home_log_box", stamped)
        # Persist every logged message to disk, independent of whether
        # any Text widget currently exists to show it live -- this is
        # what makes activity visible again on the next launch. The
        # on-disk store keeps oldest-first order; only the DISPLAY order
        # is newest-first (here and in settings_page).
        append_activity_log_entry(stamped.rstrip("\n"))