"""
services/updater/notify.py
User-facing notifications for update check/install outcomes.

Two categories of popup, with very different rules:

  - SECURITY events (a failed signature/hash verification) ALWAYS show,
    regardless of any user setting. If something tried to tamper with
    the update source, the user must be told -- no toggle silences
    this, ever.

  - INSTALL-OUTCOME events (an install actually completed, or an exe
    swap was staged) are gated by "Notify me about updates"
    (notify_on_update_enabled). This applies whether the install was
    manual (user said "Yes" to the Yes/No prompt) or fully automatic
    (auto_install_updates is on):
      * notify ON  -> a popup summarizing the install, with changelog.
      * notify OFF -> completely silent. No popup, no changelog. The
        only sign anything happened is the version number itself
        changing the next time the app is opened -- by design, for
        users who want background updating with zero interruption.

  - The "would you like to download and install this now?" prompt
    (manual/non-auto-install path only) is NOT handled here -- it's a
    synchronous Yes/No dialog raised directly from the background
    worker via services.updater.gui_integration's confirm_install
    callback, shown BEFORE anything is downloaded. That prompt is only
    ever offered when auto_install_updates is off in the first place,
    so it doesn't overlap with the auto-install notify gating above.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Any

from services.updater.tk_helpers import app_is_alive, schedule_on_ui_thread


def notify_on_update_enabled(app: Any) -> bool:
    variable = getattr(app, "notify_on_update", None)
    if variable is None:
        return True
    try:
        return bool(variable.get())
    except (AttributeError, tk.TclError):
        return False


def show_notification(app: Any, title: str, message: str, kind: str = "info") -> None:
    """Schedules a messagebox popup onto the Tkinter UI thread. Safe to
    call from a background worker thread. `kind` is one of
    'info' | 'warning' | 'error'."""

    def _show() -> None:
        if not app_is_alive(app):
            return
        try:
            if kind == "error":
                messagebox.showerror(title, message, parent=app)
            elif kind == "warning":
                messagebox.showwarning(title, message, parent=app)
            else:
                messagebox.showinfo(title, message, parent=app)
        except tk.TclError:
            pass

    schedule_on_ui_thread(app, _show)


def _format_changelog_section(changelog: str) -> str:
    changelog = str(changelog).strip()
    if not changelog:
        return ""
    return f"\n\nWhat's new:\n{changelog}"


def maybe_notify_result(app: Any, result: dict[str, Any], *, context: str) -> None:
    """
    Inspects a check_and_maybe_install()/startup_update_check() result
    dict and shows an appropriate notification, if any is warranted.

    context is "check" (a check-only pass that did not install
    anything) or "install" (an install, or exe-swap staging, actually
    happened). Currently unused for branching here, but kept for
    callers/logging that want to distinguish the two.
    """
    status = str(result.get("status", ""))
    remote_version = str(result.get("remote_version", ""))
    message = str(result.get("message", ""))
    changelog_section = _format_changelog_section(result.get("changelog", ""))

    # SECURITY event: always shown, never gated behind any toggle.
    # A user must never be able to accidentally silence a warning that
    # an update failed cryptographic verification.
    if status == "verification_failed":
        show_notification(
            app, "Update Rejected",
            "A downloaded release failed cryptographic verification and was "
            "NOT installed. This can indicate a compromised update source.\n\n"
            f"{message}",
            kind="warning",
        )
        return

    # INSTALL-OUTCOME events: gated by "Notify me about updates", for
    # BOTH the manual (Yes/No-confirmed) install path and the fully
    # automatic (auto_install_updates) path. With notify off, this is
    # intentionally silent -- no popup, no changelog -- so background
    # updating stays fully unattended. The user will simply see a new
    # version number the next time they open Settings.
    if status in {"installed", "exe_swap_pending"}:
        if not notify_on_update_enabled(app):
            return
        if status == "installed":
            show_notification(
                app, "Update Installed",
                f"Version {remote_version} was installed automatically.{changelog_section}\n\n"
                f"Restart the application to run the new version.",
                kind="info",
            )
        else:
            show_notification(
                app, "Update Ready",
                f"Version {remote_version} has been verified and staged.{changelog_section}\n\n"
                f"The application will now close and relaunch automatically.",
                kind="info",
            )
        return

    # "declined": the user already answered "No" on the Yes/No dialog
    # raised by confirm_install -- nothing further to show. The same
    # update will simply be offered again on the next check.
    # "downloaded" (no confirm_install was offered, e.g. notifications
    # are off): intentionally silent -- this is the background
    # download+verify path, not meant to interrupt anyone.
