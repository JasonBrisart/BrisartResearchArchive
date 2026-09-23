"""
services/updater/gui_integration.py
Tkinter-facing entry points. This is the only file most of the app
actually talks to -- controllers/system_controller.py imports from
here, and gui/main_window.py calls startup_check() once at launch.

Settings read from the app object (all tk.BooleanVar, all optional --
missing/None defaults to the safe/expected value):

  - enable_update_checks : master switch. If False, NOTHING in this
                            file ever contacts the registry -- not the
                            manual "Check Updates" button, not the
                            automatic startup check.

  - auto_install_updates : if True, both the automatic startup check
                            AND the manual "Check Updates" button
                            install a verified update immediately, with
                            no prompt -- the checkbox itself is the
                            user's standing confirmation.

  - notify_on_update      : if True (and auto_install_updates is
                            False), the user is asked with a Yes/No
                            dialog, BEFORE anything is downloaded,
                            whether to download and install an
                            available update. Answering "No" simply
                            means it will be offered again next time --
                            nothing is remembered or suppressed. If
                            True (and auto_install_updates is also
                            True), an "Update Installed" popup with a
                            changelog is shown right after an automatic
                            install completes. If False, install
                            outcomes are never announced either way.

  AUTOMATIC STARTUP CHECK, specifically:
  With auto_install_updates OFF and notify_on_update OFF, the user has
  explicitly asked for zero automatic activity -- no background
  checking, no silent downloading, nothing. In that combination,
  startup_check() is a complete no-op: it does not contact the
  registry at all. The ONLY way an update check happens is the user
  manually pressing "Check Updates", which always works as long as
  enable_update_checks is on -- that's an explicit action, not
  something happening on their behalf.
"""
from __future__ import annotations

import threading
import tkinter as tk
from typing import Any

from services.updater.notify import maybe_notify_result, notify_on_update_enabled
from services.updater.orchestration import check_and_maybe_install
from services.updater.tk_helpers import app_is_alive, ask_yes_no_on_ui_thread, schedule_on_ui_thread, widget_is_alive

_update_lock = threading.Lock()


def update_checks_enabled(app: Any) -> bool:
    variable = getattr(app, "enable_update_checks", None)
    if variable is None:
        return True
    try:
        return bool(variable.get())
    except (AttributeError, tk.TclError):
        return False


def auto_install_enabled(app: Any) -> bool:
    variable = getattr(app, "auto_install_updates", None)
    if variable is None:
        return True
    try:
        return bool(variable.get())
    except (AttributeError, tk.TclError):
        return False


def set_status_text(app: Any, message: str) -> None:
    status_variable = getattr(app, "status_text", None)
    if status_variable is None:
        return
    try:
        status_variable.set(str(message))
    except (AttributeError, tk.TclError):
        pass


def find_update_box(app: Any) -> Any | None:
    update_box = getattr(app, "update_box", None)
    if widget_is_alive(update_box):
        return update_box
    show_page = getattr(app, "show_page", None)
    if not callable(show_page):
        return None
    try:
        show_page("Settings")
    except (AttributeError, tk.TclError):
        return None
    update_box = getattr(app, "update_box", None)
    if widget_is_alive(update_box):
        return update_box
    return None


def set_update_text(app: Any, report: str) -> None:
    if not app_is_alive(app):
        return
    update_box = find_update_box(app)
    if update_box is None:
        return
    try:
        update_box.delete("1.0", "end")
        update_box.insert("end", str(report))
        update_box.see("1.0")
    except tk.TclError:
        return
    set_status_text(app, "Update check complete")


def format_update_result(result: Any, captured_output: str) -> str:
    output = str(captured_output).strip()
    if output:
        return output
    if isinstance(result, dict):
        lines: list[str] = []
        for key, label in (
            ("status", "Status"), ("local_version", "Local version"),
            ("remote_version", "Remote version"), ("downloaded_file", "Downloaded file"),
        ):
            value = str(result.get(key, "")).strip()
            if value:
                lines.append(f"{label}: {value}")
        message = str(result.get("message", "")).strip()
        if message:
            if lines:
                lines.append("")
            lines.append(message)
        changelog = str(result.get("changelog", "")).strip()
        if changelog:
            lines.append("")
            lines.append("What's new:")
            lines.append(changelog)
        if lines:
            return "\n".join(lines)
    return "Update check completed."


def _run_with_capture(operation, *args, **kwargs) -> tuple[dict, str]:
    collected_lines: list[str] = []

    def _collect_and_print(line: str) -> None:
        collected_lines.append(line)
        print(line)

    result = operation(_collect_and_print, *args, **kwargs)
    captured_output = "\n".join(collected_lines).strip()
    return result, captured_output


def build_confirm_install(app: Any):
    """
    Returns a confirm_install(remote_version) callback wired to a Yes/No
    dialog, or None if no prompt should ever be shown for this check:

      - auto_install is on: the checkbox already is the confirmation,
        no prompt needed.
      - "Notify me about updates" is off: the user has explicitly asked
        not to be interrupted; checks still happen silently.

    The returned callback is safe to call from a background thread --
    see tk_helpers.ask_yes_no_on_ui_thread.
    """
    if auto_install_enabled(app):
        return None
    if not notify_on_update_enabled(app):
        return None

    def _confirm(remote_version: str) -> bool:
        return ask_yes_no_on_ui_thread(
            app,
            "Update Available",
            f"A new update (version {remote_version}) is available.\n\n"
            "Would you like to download and install it now?",
        )

    return _confirm


def _run_check(app: Any, *, silent_when_nothing_new: bool) -> None:
    """
    Shared worker body for both the manual "Check Updates" button and
    the automatic startup check. Always checks the registry; whether it
    installs, prompts, or stays silent depends entirely on the current
    auto_install_updates / notify_on_update settings (see module
    docstring). Callers are responsible for deciding WHETHER to call
    this at all -- see should_run_automatic_startup_check() for the
    startup-specific gate.
    """
    if not app_is_alive(app):
        return
    if not update_checks_enabled(app):
        if not silent_when_nothing_new:
            set_update_text(
                app,
                "Update checks are disabled.\n\nNo remote request was made.\n"
                "The Archive will remain on the current local version.",
            )
        return
    if not _update_lock.acquire(blocking=False):
        if not silent_when_nothing_new:
            set_update_text(app, "An update check is already running.\n\nThe existing request will continue.")
        return

    auto_install = auto_install_enabled(app)
    confirm_install = build_confirm_install(app)
    if not silent_when_nothing_new:
        set_status_text(app, "Checking for updates..." if not auto_install else "Checking for updates (auto-install enabled)...")

    def worker() -> None:
        try:
            result, captured_output = _run_with_capture(
                lambda emit: check_and_maybe_install(emit, auto_install=auto_install, confirm_install=confirm_install)
            )
            report = format_update_result(result=result, captured_output=captured_output)
        except Exception as exc:
            result = {"status": "unexpected_error", "message": str(exc)}
            report = f"Update check failed unexpectedly.\n\n{type(exc).__name__}: {exc}"
        finally:
            _update_lock.release()

        status = result.get("status")
        if silent_when_nothing_new and status in {"current", "local_newer"}:
            return  # nothing to report on an unattended startup check
        schedule_on_ui_thread(app, lambda: set_update_text(app, report))
        context = "install" if status in {"installed", "exe_swap_pending"} else "check"
        maybe_notify_result(app, result, context=context)

    try:
        thread = threading.Thread(target=worker, name="BrisartUpdateCheck", daemon=True)
        thread.start()
    except Exception:
        _update_lock.release()
        raise


def check_updates(app: Any) -> None:
    """Wired to the 'Check Updates' button. Always runs an explicit,
    user-requested check -- the only gate is enable_update_checks
    itself. This is the one path that works even when both
    auto_install_updates and notify_on_update are off."""
    _run_check(app, silent_when_nothing_new=False)


def run_update_check(app: Any) -> None:
    check_updates(app)


def should_run_automatic_startup_check(app: Any) -> bool:
    """
    The automatic startup check is only allowed to make ANY contact
    with the registry if at least one of auto_install_updates or
    notify_on_update is on. With both off, the user has explicitly
    asked for zero unattended activity -- no silent background
    checking, no silent downloading -- so startup_check() must be a
    complete no-op in that case. The manual "Check Updates" button
    remains the only way to trigger a check when both are off.
    """
    if not update_checks_enabled(app):
        return False
    return auto_install_enabled(app) or notify_on_update_enabled(app)


def startup_check(app: Any) -> None:
    """
    Called once, automatically, shortly after the application window is
    built (see gui/main_window.py). Does nothing at all unless
    should_run_automatic_startup_check() allows it -- see that
    function's docstring for the exact gating rule. When it does run,
    it behaves exactly like check_updates() -- checks, downloads+
    verifies, prompts or installs per the current settings -- but stays
    completely silent if the local version is already current, since
    the user didn't explicitly ask.
    """
    if not should_run_automatic_startup_check(app):
        return
    _run_check(app, silent_when_nothing_new=True)


def update_check_is_running() -> bool:
    acquired = _update_lock.acquire(blocking=False)
    if not acquired:
        return True
    _update_lock.release()
    return False
