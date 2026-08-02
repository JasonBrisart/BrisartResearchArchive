from __future__ import annotations

import tkinter as tk

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
            # Previously missing: trim_text_widget_lines() existed
            # specifically to cap a Text widget's growth, but nothing on
            # this path ever called it, so long-running sessions (TFL
            # autosave logs every 5 trials, framework launches, update
            # checks, etc.) grew these widgets without bound.
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
