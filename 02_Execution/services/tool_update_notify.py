"""
services/tool_update_notify.py
Popup notification for Tooling update checks -- shown once per check
that finds at least one installed program with a newer version
published on the registry. Mirrors services/updater/notify.py's
show_notification() pattern (schedule onto the Tk UI thread, safe to
call from a background thread) but is kept as its own small module
rather than folded into notify.py, since this notification is about
OTHER installed programs (Tooling), not about the Archive's own
self-update -- conflating the two would make notify.py responsible for
two independent subsystems' popups.

Talks to:
  - controllers/system_controller.py's check_tool_updates() calls
    show_tool_update_popup() once, after a background update check
    completes, only if the check found at least one upgrade candidate.
  - services/updater/tk_helpers.py's schedule_on_ui_thread() /
    app_is_alive() are reused UNCHANGED, for the same thread-safety
    reason they exist there: this is called from a background worker
    thread (see SystemController.check_tool_updates()), and any Tk
    widget access must happen on the main thread.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

from services.updater.tk_helpers import app_is_alive, schedule_on_ui_thread


def build_tool_update_message(upgrades: list[dict]) -> str:
    """
    Builds the popup body text for a list of upgrade-candidate dicts
    (as returned by services.tooling_manager.check_all_tool_updates()).
    Split out from show_tool_update_popup() so the message text itself
    can be unit-tested without any Tk dependency at all.
    """
    lines = ["Updates are available for the following installed programs:", ""]
    for upgrade in upgrades:
        lines.append(f"- {upgrade['name']}: v{upgrade['installed_version']} -> v{upgrade['available_version']}")
        changelog = str(upgrade.get("changelog", "")).strip()
        if changelog:
            lines.append(f"    {changelog}")
    lines.append("")
    lines.append("Open the Tooling page to update any of them.")
    return "\n".join(lines)


def show_tool_update_popup(app: Any, upgrades: list[dict]) -> None:
    """
    Shows a single popup summarizing every installed Tooling program
    that has a newer version available. Does nothing if `upgrades` is
    empty (callers should already check this before calling, but this
    function is defensive regardless, so it's always safe to call
    directly with whatever check_all_tool_updates() returned).
    """
    if not upgrades:
        return
    message = build_tool_update_message(upgrades)

    def _show() -> None:
        if not app_is_alive(app):
            return
        try:
            messagebox.showinfo("Tooling Updates Available", message, parent=app)
        except tk.TclError:
            pass

    schedule_on_ui_thread(app, _show)


__all__ = ["build_tool_update_message", "show_tool_update_popup"]
