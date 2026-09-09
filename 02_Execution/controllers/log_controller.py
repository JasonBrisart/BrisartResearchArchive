"""
controllers/log_controller.py
LogController -- the mixin every part of the app calls through for
status/logging: app.log(text) is the single entry point used by
system_controller.py, framework_service.py, the updater, and every page
action that reports success/failure back to the user.

Every call to log() does three things:
  1. Updates the status bar text (self.status_text), if present.
  2. Writes a timestamped line into whichever on-screen Text widgets
     currently exist (log_box on the Settings page, home_log_box on the
     Dashboard if one is ever added). This is purely visual and resets
     to empty every time those pages are destroyed/rebuilt on
     navigation, since Tk widgets don't survive that.
  3. Appends the same timestamped line to the PERSISTENT activity log on
     disk (config/activity_log.py), which is what makes activity visible
     again after the app is closed and reopened -- see that module's
     docstring for the on-disk format and the 100-entry rolling-window
     cap. gui/pages/settings_page.py reads that same file to
     pre-populate the Activity Log box with history from previous
     sessions.

Widget references (log_box, etc.) are checked for liveness before every
write, since page modules destroy/rebuild their widgets on every
navigation -- a stale reference from a page the user has since navigated
away from must never raise or silently attach itself to a dead widget.

Display order: the Activity Log shows the newest entry at the TOP. New
lines are inserted at "1.0" (not "end"), so trim_text_widget_lines()
caps growth by deleting the oldest content from the BOTTOM, and
gui.see("1.0") keeps the view pinned to the newest entry. The on-disk
store (config/activity_log.py) keeps its own oldest-first order and is
reversed for display by settings_page._populate_activity_log().
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