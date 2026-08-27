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

NEWEST-ENTRY-ON-TOP DISPLAY ORDER, specifically (FIX 1):
The Activity Log box used to insert new lines at "end" (the bottom),
which meant a user had to scroll all the way down to see the most
recent action -- the natural expectation for an activity/event log is
the opposite: newest at the top, so the most recent thing that
happened is the first thing visible without any scrolling at all.

Fixed by inserting every new line at "1.0" (the very top of the
widget) instead of "end". This flips which end of the box is "newest"
vs. "oldest" for the CURRENT session's own entries, so
trim_text_widget_lines() (which caps the widget from growing forever)
had to flip too: it used to delete overflow from the top (since the
top was the oldest content, back when new lines were appended at the
bottom); now that new lines land at the top, the oldest content is at
the BOTTOM, so overflow is trimmed there instead. gui.see("1.0") (not
"end") is called after every insert, so the box stays scrolled to the
top -- where the newest entry now is -- every time something new is
logged.

gui/pages/settings_page.py's _populate_activity_log() was updated to
match: config.activity_log.load_activity_log() still returns persisted
history oldest-first/newest-last (that storage format is unchanged --
see that module's docstring), but the page now reverses that list
before inserting it, so the persisted history displays newest-first
too, consistent with how new entries get added during the live
session.
"""
from __future__ import annotations

import tkinter as tk

from config.activity_log import append_activity_log_entry
from services import timestamp

MAX_LOG_LINES = 3000


def trim_text_widget_lines(widget: tk.Text, max_lines: int = MAX_LOG_LINES) -> None:
    """
    Keep a Tk Text widget from growing forever. Tk line indexes are
    1-based.

    NEWEST-ON-TOP, specifically (see FIX 1 in the module docstring):
    new entries are now inserted at "1.0" (the top), so the OLDEST
    content is whatever has been pushed down to the BOTTOM of the
    widget over time -- the opposite of how this worked before. When
    the widget exceeds max_lines, this now deletes everything past
    line max_lines (i.e. the oldest tail at the bottom), keeping the
    most recent max_lines lines at the top intact.
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
            # Newest-on-top (FIX 1, see module docstring): inserted at
            # "1.0" instead of "end", so the most recent entry is
            # always the very first thing visible in the box.
            widget.insert("1.0", message)
            # trim_text_widget_lines() caps the visual Text widget's own
            # growth (MAX_LOG_LINES) -- separate and independent from
            # the 100-entry cap on the persisted activity_log.json file
            # appended below. The widget can show up to 3000 lines of
            # the CURRENT session; the persisted file remembers up to
            # 100 entries across ALL sessions.
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
        # what makes activity visible again on the NEXT launch, even
        # for actions logged while the Settings page wasn't open.
        # NOTE: append_activity_log_entry() still stores oldest-first/
        # newest-last on disk (see config/activity_log.py) -- only the
        # DISPLAY order was changed here and in settings_page.py's
        # _populate_activity_log(). The on-disk format itself did not
        # need to change.
        append_activity_log_entry(stamped.rstrip("\n"))
