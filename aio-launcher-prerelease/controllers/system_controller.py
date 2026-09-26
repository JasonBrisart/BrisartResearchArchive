"""
File: controllers/system_controller.py

Purpose:
Coordinate application-level actions including framework execution,
framework-registry refreshes, settings persistence, output-directory
management, TFL analysis, Archive update checks, document viewing, and
application shutdown.

Communication / relationships:
- Uses config/runtime.py for settings and output-directory resolution.
- Delegates framework execution to services/framework_service.py.
- Delegates TFL analysis to services/tfl_analysis.py.
- Delegates Archive updates to services/updater/gui_integration.py.
- Opens local documents through gui/components/document_viewer.py.
- Is mixed into gui/main_window.BrisartSuiteApp.

Settings / parameters:
- save_config() controls whether status and error dialogs are shown.
- _collect_settings() reads current Tk variables and window dimensions.
- Output directories may be absolute or relative to the application
  data directory.

Edge cases:
- Missing services and Tk variables produce visible or logged failures.
- Settings-save failures do not automatically close the application.
- Output directories are created before opening when necessary.
- Framework and analysis exceptions are isolated from the GUI loop.

Known limitations:
- TFL analysis remains framework-specific.
- Opening folders and CSV files depends on the operating system's
  default file-management commands.

Examples:
- app.start_framework("TFL")
- app.check_updates()
- app.open_output_folder()
"""

from __future__ import annotations

import os
import subprocess
import sys as platform_sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

from config.runtime import (
    get_output_folder,
    normalize_settings,
    save_settings as persist_settings,
)
from gui.components.document_viewer import (
    open_local_doc as open_document_viewer,
)
from services.tfl_analysis import (
    analyze_tfl as run_tfl_analysis,
    fallback_csv_summary as build_fallback_csv_summary,
    open_tfl_csv as open_tfl_result_csv,
    set_analysis_text as display_analysis_text,
)
from services.updater.gui_integration import (
    check_updates as run_gui_update_check,
    set_update_text as display_update_text,
    update_check_is_running as gui_update_check_is_running,
)


class SystemController:
    """Coordinate application-level Brisart Research Archive actions."""

    # ============================================================
    # Core helpers
    # ============================================================

    def _set_status(self, message: str) -> None:
        status_variable = getattr(self, "status_text", None)

        if status_variable is None:
            return

        try:
            status_variable.set(str(message))
        except (AttributeError, tk.TclError):
            pass

    def _log_message(self, message: str) -> None:
        logger = getattr(self, "log", None)

        if not callable(logger):
            return

        try:
            logger(str(message))
        except (AttributeError, RuntimeError, tk.TclError):
            pass

    def _read_tk_value(
        self,
        attribute_name: str,
        default: Any = None,
    ) -> Any:
        value = getattr(self, attribute_name, default)
        getter = getattr(value, "get", None)

        if callable(getter):
            try:
                return getter()
            except tk.TclError:
                return default

        return value

    def _window_dimension(
        self,
        method_name: str,
        fallback: int,
    ) -> int:
        method = getattr(self, method_name, None)

        if not callable(method):
            return int(fallback)

        try:
            value = int(method())
        except (TypeError, ValueError, tk.TclError):
            return int(fallback)

        if value <= 1:
            return int(fallback)

        return value

    def _collect_settings(self) -> dict:
        existing_settings = getattr(self, "settings", {})

        settings = (
            dict(existing_settings)
            if isinstance(existing_settings, dict)
            else {}
        )

        settings["default_framework"] = self._read_tk_value(
            "selected_framework",
            settings.get("default_framework", "TFL"),
        )
        settings["output_folder"] = self._read_tk_value(
            "output_folder",
            settings.get("output_folder", "outputs"),
        )
        settings["enable_update_checks"] = self._read_tk_value(
            "enable_update_checks",
            settings.get("enable_update_checks", True),
        )
        settings["notify_on_update"] = self._read_tk_value(
            "notify_on_update",
            settings.get("notify_on_update", True),
        )
        settings["auto_install_updates"] = self._read_tk_value(
            "auto_install_updates",
            settings.get("auto_install_updates", True),
        )
        settings["theme"] = self._read_tk_value(
            "theme",
            settings.get("theme", "dark"),
        )
        settings["window_width"] = self._window_dimension(
            "winfo_width",
            settings.get("window_width", 800),
        )
        settings["window_height"] = self._window_dimension(
            "winfo_height",
            settings.get("window_height", 600),
        )

        return normalize_settings(settings)

    # ============================================================
    # Framework selection and execution
    # ============================================================

    def select_framework(self, framework_id: str) -> None:
        normalized_id = str(framework_id).strip()

        if not normalized_id:
            self._set_status(
                "Framework selection failed: no framework ID was supplied."
            )
            return

        selected_variable = getattr(
            self,
            "selected_framework",
            None,
        )

        if selected_variable is None:
            self._set_status(
                "Framework selection failed: selection state is unavailable."
            )
            return

        try:
            selected_variable.set(normalized_id)
        except (AttributeError, tk.TclError) as exc:
            message = (
                "Framework selection failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)
            return

        saved = self.save_config(update_status=False)

        if saved:
            message = f"Selected framework: {normalized_id}"
        else:
            message = (
                f"Selected framework for this session: {normalized_id}. "
                "The selection could not be saved."
            )

        self._set_status(message)
        self._log_message(message)

    def start_selected_framework(self) -> None:
        framework_service = getattr(
            self,
            "framework_service",
            None,
        )
        start_method = getattr(
            framework_service,
            "start_selected_framework",
            None,
        )

        if not callable(start_method):
            message = (
                "Framework launch failed: "
                "the framework service is unavailable."
            )
            self._set_status(message)
            self._log_message(message)
            return

        try:
            start_method()
        except Exception as exc:
            message = (
                "Framework launch failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Framework Launch Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

    def start_framework(self, framework_id: str) -> None:
        normalized_id = str(framework_id).strip()

        if not normalized_id:
            self._set_status(
                "Framework launch failed: no framework ID was supplied."
            )
            return

        framework_service = getattr(
            self,
            "framework_service",
            None,
        )
        start_method = getattr(
            framework_service,
            "start_framework",
            None,
        )

        if not callable(start_method):
            message = (
                "Framework launch failed: "
                "the framework service is unavailable."
            )
            self._set_status(message)
            self._log_message(message)
            return

        try:
            start_method(normalized_id)
        except Exception as exc:
            message = (
                f"Could not launch {normalized_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Framework Launch Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

    def refresh_framework_registry(self) -> None:
        try:
            from config.registries import (
                get_available_frameworks,
                get_reserved_frameworks,
                refresh_framework_registry,
            )

            registry = list(refresh_framework_registry())
            available_frameworks = list(get_available_frameworks())
            reserved_frameworks = list(get_reserved_frameworks())

            valid_ids = {
                str(item.get("id", "")).casefold()
                for item in registry
                if isinstance(item, dict) and item.get("id")
            }

            current_selection = str(
                self._read_tk_value(
                    "selected_framework",
                    "",
                )
                or ""
            ).strip()

            if (
                not current_selection
                or current_selection.casefold() not in valid_ids
            ):
                replacement_id = ""

                for item in available_frameworks:
                    if not isinstance(item, dict):
                        continue

                    candidate = str(item.get("id", "")).strip()

                    if candidate:
                        replacement_id = candidate
                        break

                if not replacement_id:
                    for item in registry:
                        if not isinstance(item, dict):
                            continue

                        candidate = str(item.get("id", "")).strip()

                        if candidate:
                            replacement_id = candidate
                            break

                selected_variable = getattr(
                    self,
                    "selected_framework",
                    None,
                )

                if replacement_id and selected_variable is not None:
                    selected_variable.set(replacement_id)

            message = (
                "Framework registry refreshed. "
                f"Total: {len(registry)} | "
                f"Available: {len(available_frameworks)} | "
                f"Reserved: {len(reserved_frameworks)}"
            )

            self._set_status(message)
            self._log_message(message)
            self.save_config(update_status=False)

            show_page = getattr(self, "show_page", None)

            if callable(show_page):
                show_page("Frameworks")

        except Exception as exc:
            message = (
                "Framework registry refresh failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Registry Refresh Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

    # ============================================================
    # Settings persistence and shutdown
    # ============================================================

    def save_config(
        self,
        *,
        update_status: bool = False,
        show_error: bool = False,
    ) -> bool:
        if not hasattr(self, "settings"):
            message = (
                "Settings could not be saved because application "
                "settings are unavailable."
            )

            if update_status:
                self._set_status(message)

            self._log_message(message)
            return False

        try:
            normalized = self._collect_settings()
            saved = persist_settings(normalized)
        except Exception as exc:
            message = (
                "Settings save failed: "
                f"{type(exc).__name__}: {exc}"
            )

            if update_status:
                self._set_status(message)

            self._log_message(message)

            if show_error:
                try:
                    messagebox.showerror(
                        "Settings Save Failed",
                        message,
                        parent=self,
                    )
                except tk.TclError:
                    pass

            return False

        if not saved:
            message = (
                "Settings could not be written to disk. "
                "The current session remains active."
            )

            if update_status:
                self._set_status(message)

            self._log_message(message)

            if show_error:
                try:
                    messagebox.showerror(
                        "Settings Save Failed",
                        message,
                        parent=self,
                    )
                except tk.TclError:
                    pass

            return False

        self.settings.clear()
        self.settings.update(normalized)

        if update_status:
            self._set_status("Settings saved.")

        self._log_message("Application settings saved.")
        return True

    def save_settings(self) -> bool:
        return self.save_config(
            update_status=True,
            show_error=True,
        )

    def on_close(self) -> None:
        saved = self.save_config(
            update_status=False,
            show_error=False,
        )

        if not saved:
            try:
                should_close = messagebox.askyesno(
                    "Settings Were Not Saved",
                    (
                        "The application could not save the current "
                        "settings.\n\n"
                        "Close the Brisart Research Archive anyway?"
                    ),
                    parent=self,
                )
            except tk.TclError:
                should_close = True

            if not should_close:
                self._set_status(
                    "Close cancelled. Settings have not been saved."
                )
                return

        destroy_method = getattr(self, "destroy", None)

        if callable(destroy_method):
            try:
                destroy_method()
            except tk.TclError:
                pass

    # ============================================================
    # Output-directory management
    # ============================================================

    def browse_output_folder(self) -> None:
        current_value = str(
            self._read_tk_value("output_folder", "") or ""
        ).strip()

        initial_directory: str | None = None

        if current_value:
            candidate = Path(current_value).expanduser()

            if candidate.is_dir():
                initial_directory = str(candidate)

        if initial_directory is None:
            try:
                initial_directory = str(
                    get_output_folder(
                        getattr(self, "settings", None)
                    )
                )
            except (OSError, TypeError, ValueError):
                initial_directory = None

        dialog_options = {
            "title": "Select Output Directory",
            "mustexist": True,
            "parent": self,
        }

        if initial_directory:
            dialog_options["initialdir"] = initial_directory

        try:
            selected_folder = filedialog.askdirectory(
                **dialog_options
            )
        except tk.TclError as exc:
            message = f"Output-folder selection failed: {exc}"
            self._set_status(message)
            self._log_message(message)
            return

        if not selected_folder:
            return

        selected_path = Path(selected_folder).expanduser()

        try:
            selected_path = selected_path.resolve(strict=True)
        except OSError as exc:
            message = (
                "The selected output folder is unavailable: "
                f"{exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Invalid Output Folder",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            return

        if not selected_path.is_dir():
            message = "The selected output path is not a directory."
            self._set_status(message)

            try:
                messagebox.showerror(
                    "Invalid Output Folder",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            return

        output_variable = getattr(
            self,
            "output_folder",
            None,
        )

        if output_variable is None:
            self._set_status(
                "Output folder could not be changed because the "
                "output-folder setting is unavailable."
            )
            return

        try:
            output_variable.set(str(selected_path))
        except (AttributeError, tk.TclError) as exc:
            message = (
                "Output folder could not be changed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)
            return

        saved = self.save_config(update_status=False)

        if not saved:
            try:
                output_variable.set(current_value)
            except (AttributeError, tk.TclError):
                pass

            message = (
                "The output-folder change was not saved. "
                "The previous value was restored."
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Output Folder Not Saved",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            return

        message = f"Output folder set: {selected_path}"
        self._set_status(message)
        self._log_message(message)

    def open_output_folder(self) -> None:
        current_value = str(
            self._read_tk_value("output_folder", "") or ""
        ).strip()

        try:
            folder_path = (
                Path(current_value).expanduser()
                if current_value
                else get_output_folder(
                    getattr(self, "settings", None)
                )
            )
        except (OSError, TypeError, ValueError):
            folder_path = get_output_folder(
                getattr(self, "settings", None)
            )

        try:
            folder_path.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            message = (
                "Could not create the output folder: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Open Folder Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            return

        try:
            if platform_sys.platform.startswith("win"):
                os.startfile(str(folder_path))
            elif platform_sys.platform == "darwin":
                subprocess.run(
                    ["open", str(folder_path)],
                    check=False,
                )
            else:
                subprocess.run(
                    ["xdg-open", str(folder_path)],
                    check=False,
                )
        except Exception as exc:
            message = (
                "Could not open the output folder: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Open Folder Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

            return

        message = f"Opened output folder: {folder_path}"
        self._set_status(message)
        self._log_message(message)

    # ============================================================
    # TFL analysis
    # ============================================================

    def analyze_tfl(self) -> None:
        try:
            run_tfl_analysis(self)
        except Exception as exc:
            message = (
                "TFL analysis failed: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Analysis Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

    def set_analysis_text(self, report: str) -> None:
        display_analysis_text(self, str(report))

    def fallback_csv_summary(self) -> str:
        return build_fallback_csv_summary(self)

    def open_tfl_csv(self) -> None:
        try:
            open_tfl_result_csv(self)
        except Exception as exc:
            message = (
                "Could not open the TFL CSV: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Open CSV Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass

    # ============================================================
    # Archive updates
    # ============================================================

    def check_updates(self) -> None:
        run_gui_update_check(self)

    def run_update_check(self) -> None:
        self.check_updates()

    def update_check_is_running(self) -> bool:
        return gui_update_check_is_running()

    def set_update_text(self, report: Any) -> None:
        display_update_text(self, str(report))

    # ============================================================
    # Local documents
    # ============================================================

    def open_local_doc(self) -> None:
        try:
            open_document_viewer(self)
        except Exception as exc:
            message = (
                "Could not open the document viewer: "
                f"{type(exc).__name__}: {exc}"
            )
            self._set_status(message)
            self._log_message(message)

            try:
                messagebox.showerror(
                    "Document Viewer Failed",
                    message,
                    parent=self,
                )
            except tk.TclError:
                pass


__all__ = ["SystemController"]