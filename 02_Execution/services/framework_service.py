from __future__ import annotations

import importlib
import traceback
from tkinter import messagebox
from typing import Any

from config.registries import get_framework


class FrameworkService:
    """
    Dynamically launch GUI framework runners. Framework identity and
    runner information come from the framework registry. Import and
    startup failures are isolated so a broken framework does not
    terminate the Archive GUI.
    """

    def __init__(self, app):
        self.app = app

    # ============================================================
    # Public Launch Methods
    # ============================================================

    def start_selected_framework(self) -> None:
        try:
            framework_id = self.app.selected_framework.get()
        except Exception as exc:
            self._show_error(
                title="Framework Selection Failed",
                message="The selected framework could not be read.",
                exc=exc,
            )
            return
        self.start_framework(framework_id)

    def start_framework(self, framework_id: str) -> None:
        framework_id = str(framework_id).strip()
        if not framework_id:
            messagebox.showerror(
                "Framework Not Selected", "Select a framework before starting.", parent=self._message_parent()
            )
            return

        framework = get_framework(framework_id)
        if framework is None:
            messagebox.showerror(
                "Framework Not Found", f"No framework is registered with ID: {framework_id}",
                parent=self._message_parent(),
            )
            self._log(f"Framework not found: {framework_id}")
            return

        status = str(framework.get("status", "")).strip()
        if status.casefold() != "available":
            messagebox.showinfo(
                "Coming Soon", f"{framework_id} is reserved but not wired yet.", parent=self._message_parent()
            )
            return

        runner_module = str(framework.get("runner_module", "")).strip()
        runner_class = str(framework.get("runner_class", "")).strip()
        if not runner_module or not runner_class:
            messagebox.showerror(
                "Runner Missing", f"No GUI runner is configured for {framework_id}.", parent=self._message_parent()
            )
            self._log(f"{framework_id} runner metadata is incomplete.")
            return

        module = self._load_runner_module(framework_id=framework_id, runner_module=runner_module)
        if module is None:
            return
        runner_type = self._load_runner_type(framework_id=framework_id, module=module, runner_class=runner_class)
        if runner_type is None:
            return
        runner = self._create_runner(framework_id=framework_id, runner_type=runner_type)
        if runner is None:
            return

        start_method = getattr(runner, "start", None)
        if not callable(start_method):
            messagebox.showerror(
                f"{framework_id} Runner Invalid",
                f"{runner_class} does not expose a callable start() method.",
                parent=self._message_parent(),
            )
            self._log(f"{framework_id} runner has no callable start() method.")
            return

        try:
            start_method()
        except Exception as exc:
            self._show_error(
                title=f"{framework_id} Start Failed",
                message="The framework runner was created, but its start operation failed.",
                exc=exc,
            )

    # ============================================================
    # Runner Resolution
    # ============================================================

    def _load_runner_module(self, framework_id: str, runner_module: str):
        try:
            importlib.invalidate_caches()
            return importlib.import_module(runner_module)
        except Exception as exc:
            self._show_error(
                title=f"{framework_id} Import Failed",
                message="The configured framework runner module could not be imported.",
                exc=exc,
            )
            return None

    def _load_runner_type(self, framework_id: str, module, runner_class: str):
        try:
            runner_type = getattr(module, runner_class)
        except Exception as exc:
            self._show_error(
                title=f"{framework_id} Runner Missing",
                message=f"The configured runner class {runner_class!r} could not be resolved.",
                exc=exc,
            )
            return None
        if not callable(runner_type):
            messagebox.showerror(
                f"{framework_id} Runner Invalid",
                f"{runner_class!r} exists in {module.__name__!r}, but it is not callable.",
                parent=self._message_parent(),
            )
            self._log(f"{framework_id} runner class {runner_class!r} is not callable.")
            return None
        return runner_type

    def _create_runner(self, framework_id: str, runner_type):
        try:
            return runner_type(self.app)
        except Exception as exc:
            self._show_error(
                title=f"{framework_id} Initialization Failed",
                message="The framework runner could not be initialized.",
                exc=exc,
            )
            return None

    # ============================================================
    # Error Reporting
    # ============================================================

    def _message_parent(self):
        if self.app is None:
            return None
        try:
            if self.app.winfo_exists():
                return self.app
        except Exception:
            pass
        return None

    def _show_error(self, *, title: str, message: str, exc: BaseException) -> None:
        exception_text = f"{type(exc).__name__}: {exc}"
        messagebox.showerror(title, f"{message}\n\n{exception_text}", parent=self._message_parent())
        self._log(f"{title}: {exception_text}")
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _log(self, text: Any) -> None:
        message = str(text)
        if self.app is not None and hasattr(self.app, "log"):
            try:
                self.app.log(message)
                return
            except Exception:
                pass
        print(message)
