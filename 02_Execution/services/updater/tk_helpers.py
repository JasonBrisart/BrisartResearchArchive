"""
services/updater/tk_helpers.py
Small, dependency-free Tkinter liveness/threading helpers, kept in their
own file specifically so both notify.py and gui_integration.py can
import from here without creating a circular import between them.
"""
from __future__ import annotations

import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox
from typing import Any


def app_is_alive(app: Any) -> bool:
    try:
        return bool(app.winfo_exists())
    except (AttributeError, tk.TclError):
        return False


def widget_is_alive(widget: Any) -> bool:
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except (AttributeError, tk.TclError):
        return False


def schedule_on_ui_thread(app: Any, callback: Callable[[], None]) -> bool:
    if not app_is_alive(app):
        return False
    try:
        app.after(0, callback)
    except (AttributeError, tk.TclError):
        return False
    return True


def ask_yes_no_on_ui_thread(app: Any, title: str, message: str) -> bool:
    """
    Blocks the CALLING thread (expected to be a background worker, never
    the Tkinter UI thread itself) until the user answers a Yes/No
    dialog shown on the UI thread.

    This is what lets a background update-check thread pause mid-flight
    to ask "install this now?" without freezing the window: the actual
    messagebox call happens inside a callback scheduled via
    schedule_on_ui_thread() (i.e. app.after(0, ...)), so Tkinter itself
    stays fully responsive and single-threaded. The worker thread just
    waits on a threading.Event that the UI-thread callback sets once the
    dialog closes.

    Returns False (does not install) if the app is not alive, or if the
    callback could not be scheduled at all.
    """
    if not app_is_alive(app):
        return False

    result_holder = {"value": False}
    done = threading.Event()

    def _ask() -> None:
        try:
            if app_is_alive(app):
                result_holder["value"] = bool(messagebox.askyesno(title, message, parent=app))
        except tk.TclError:
            result_holder["value"] = False
        finally:
            done.set()

    if not schedule_on_ui_thread(app, _ask):
        return False

    done.wait()
    return result_holder["value"]
