"""
controllers/log_controller.py
LogController — the mixin every part of the app calls through for
status/logging: app.log(text) is the single entry point used by
system_controller.py, framework_service.py, the updater, and every
page action that reports success/failure back to the user.

Every call to log() does three things:
  1. Updates the status bar text (self.status_text), if present.
  2. Writes a timestamped line into whichever on-screen Text widgets
     currently exist (log_box on the Settings page, home_log_box on
     the Dashboard if one is ever added) -- this is purely visual and
     resets to empty every time those pages are destroyed/rebuilt on
     navigation, since Tk widgets don't survive that.
  3. Appends the same timestamped line to the PERSISTENT activity log
     on disk (config/activity_log.py), which is what makes activity
     visible again after the app is closed and reopened -- see that
     module's docstring for the on-disk format and the 100-entry
     rolling-window cap. This is what gui/pages/settings_page.py reads
     from to pre-populate the Activity Log box with history from
     previous sessions before this session's own entries are added on
     top.

Widget references (log_box, etc.) are checked for liveness before
every write, since page modules destroy/rebuild their widgets on every
navigation -- a stale reference from a page the user has since
navigated away from must never raise or silently attach itself to a
dead widget.
"""
from __future__ import annotations

import tkinter as tk

from config.activity_log import append_activity_log_entry
from services import timestamp

MAX_LOG_LINES = 3000


def trim_text_widget_lines(widget: tk.Text, max_lines: int = MAX_LOG_LINES) -> None:
    """Keep a Tk Text widget from growing forever. Tk line indexes are 1-based."""
    try:
        line_count = int(widget.index("end-1c").split(".", 1)[0])
    except (tk.TclError, ValueError, AttributeError):
        return
    overflow = line_count - max_lines
    if overflow <= 0:
        return
    try:
        widget.delete("1.0", f"{overflow + 1}.0")
    except tk.TclError:
        pass


def append_log_line(widget: tk.Text, text: str) -> None:
    try:
        widget.insert("end", f"[{timestamp()}] {text}\n")
        trim_text_widget_lines(widget)
        widget.see("end")
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
            widget.insert("end", message)
            # trim_text_widget_lines() caps the visual Text widget's own
            # growth (MAX_LOG_LINES) -- separate and independent from
            # the 100-entry cap on the persisted activity_log.json file
            # appended below. The widget can show up to 3000 lines of
            # the CURRENT session; the persisted file remembers up to
            # 100 entries across ALL sessions.
            trim_text_widget_lines(widget)
            widget.see("end")
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
        # what makes activity visible again on the NEXT launch, even
        # for actions logged while the Settings page wasn't open.
        append_activity_log_entry(stamped.rstrip("\n"))
