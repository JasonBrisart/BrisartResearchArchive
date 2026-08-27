"""
Brisart Research Archive — System Controller.

Coordinates application-level actions that do not belong to a specific
GUI page: framework selection/launch, registry refresh, settings
persistence, output-folder selection, shutdown, analysis wrappers,
update wrappers, Tooling-page actions, and document viewing. Real
behavior for analysis, updates, framework execution, Tooling
downloads/installs, and document rendering remains delegated to their
respective services.
"""
from __future__ import annotations

import os
import subprocess
import sys as platform_sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

from config.runtime import get_output_folder, normalize_settings, save_settings as persist_settings
from gui.components.document_viewer import open_local_doc as open_document_viewer
from services import (
    analyze_tfl as run_tfl_analysis,
    fallback_csv_summary as build_fallback_csv_summary,
    open_tfl_csv as open_tfl_result_csv,
    set_analysis_text as display_analysis_text,
)
from services.tool_update_notify import show_tool_update_popup
from services.tooling_manager import (
    check_all_tool_updates,
    download_and_install_tool,
    open_tool_install_folder,
    run_tool as run_tooling_program,
)
from services.updater.gui_integration import (
    check_updates as run_gui_update_check,
    set_update_text as display_update_text,
    update_check_is_running as gui_update_check_is_running,
)


class SystemController:
    """Coordinate application-level Archive actions."""

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

    def _read_tk_value(self, attribute_name: str, default: Any = None) -> Any:
        value = getattr(self, attribute_name, default)
        getter = getattr(value, "get", None)
        if callable(getter):
            try:
                return getter()
            except tk.TclError:
                return default
        return value

    def _window_dimension(self, method_name: str, fallback: int) -> int:
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
        settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}
        settings["default_framework"] = self._read_tk_value(
            "selected_framework", settings.get("default_framework", "TFL")
        )
        settings["output_folder"] = self._read_tk_value(
            "output_folder", settings.get("output_folder", "outputs")
        )
        settings["enable_update_checks"] = self._read_tk_value(
            "enable_update_checks", settings.get("enable_update_checks", True)
        )
        settings["notify_on_update"] = self._read_tk_value(
            "notify_on_update", settings.get("notify_on_update", True)
        )
        settings["auto_install_updates"] = self._read_tk_value(
            "auto_install_updates", settings.get("auto_install_updates", True)
        )
        settings["theme"] = self._read_tk_value("theme", settings.get("theme", "dark"))
        settings["window_width"] = self._window_dimension("winfo_width", settings.get("window_width", 1220))
        settings["window_height"] = self._window_dimension("winfo_height", settings.get("window_height", 780))
        return normalize_settings(settings)

    # ============================================================
    # Framework selection / launch / refresh
    # ============================================================
    def select_framework(self, framework_id: str) -> None:
        normalized_id = str(framework_id).strip()
        if not normalized_id:
            self._set_status("Framework selection failed: no framework ID was supplied.")
            return
        selected_variable = getattr(self, "selected_framework", None)
        if selected_variable is None:
            self._set_status("Framework selection failed: selection state is unavailable.")
            return
        try:
            selected_variable.set(normalized_id)
        except (AttributeError, tk.TclError) as exc:
            message = f"Framework selection failed: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            return
        saved = self.save_config(update_status=False)
        message = (
            f"Selected framework: {normalized_id}" if saved
            else f"Selected framework for this session: {normalized_id}. The selection could not be saved."
        )
        self._set_status(message)
        self._log_message(message)

    def start_selected_framework(self) -> None:
        framework_service = getattr(self, "framework_service", None)
        start_method = getattr(framework_service, "start_selected_framework", None)
        if not callable(start_method):
            message = "Framework launch failed: the framework service is unavailable."
            self._set_status(message)
            self._log_message(message)
            return
        try:
            start_method()
        except Exception as exc:
            message = f"Framework launch failed: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Framework Launch Failed", message, parent=self)
            except tk.TclError:
                pass

    def start_framework(self, framework_id: str) -> None:
        normalized_id = str(framework_id).strip()
        if not normalized_id:
            self._set_status("Framework launch failed: no framework ID was supplied.")
            return
        framework_service = getattr(self, "framework_service", None)
        start_method = getattr(framework_service, "start_framework", None)
        if not callable(start_method):
            message = "Framework launch failed: the framework service is unavailable."
            self._set_status(message)
            self._log_message(message)
            return
        try:
            start_method(normalized_id)
        except Exception as exc:
            message = f"Could not launch {normalized_id}: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Framework Launch Failed", message, parent=self)
            except tk.TclError:
                pass

    def refresh_framework_registry(self) -> None:
        try:
            from config.registries import get_available_frameworks, get_reserved_frameworks, refresh_framework_registry
            registry = list(refresh_framework_registry())
            available_frameworks = list(get_available_frameworks())
            reserved_frameworks = list(get_reserved_frameworks())
            valid_ids = {
                str(item.get("id", "")).casefold() for item in registry
                if isinstance(item, dict) and item.get("id")
            }
            current_selection = str(self._read_tk_value("selected_framework", "") or "").strip()
            if not current_selection or current_selection.casefold() not in valid_ids:
                replacement_id = ""
                for item in available_frameworks:
                    if isinstance(item, dict):
                        candidate = str(item.get("id", "")).strip()
                        if candidate:
                            replacement_id = candidate
                            break
                if not replacement_id:
                    for item in registry:
                        if isinstance(item, dict):
                            candidate = str(item.get("id", "")).strip()
                            if candidate:
                                replacement_id = candidate
                                break
                selected_variable = getattr(self, "selected_framework", None)
                if replacement_id and selected_variable is not None:
                    selected_variable.set(replacement_id)
            message = (
                f"Framework registry refreshed. Total: {len(registry)} | "
                f"Available: {len(available_frameworks)} | Reserved: {len(reserved_frameworks)}"
            )
            self._set_status(message)
            self._log_message(message)
            self.save_config(update_status=False)
            show_page = getattr(self, "show_page", None)
            if callable(show_page):
                show_page("Frameworks")
        except Exception as exc:
            message = f"Framework registry refresh failed: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Registry Refresh Failed", message, parent=self)
            except tk.TclError:
                pass

    # ============================================================
    # Settings persistence / shutdown / output folder
    # ============================================================
    def save_config(self, *, update_status: bool = False, show_error: bool = False) -> bool:
        if not hasattr(self, "settings"):
            message = "Settings could not be saved because application settings are unavailable."
            if update_status:
                self._set_status(message)
            self._log_message(message)
            return False
        try:
            normalized = self._collect_settings()
            saved = persist_settings(normalized)
        except Exception as exc:
            message = f"Settings save failed: {type(exc).__name__}: {exc}"
            if update_status:
                self._set_status(message)
            self._log_message(message)
            if show_error:
                try:
                    messagebox.showerror("Settings Save Failed", message, parent=self)
                except tk.TclError:
                    pass
            return False
        if not saved:
            message = "Settings could not be written to disk. The current session remains active."
            if update_status:
                self._set_status(message)
            self._log_message(message)
            if show_error:
                try:
                    messagebox.showerror("Settings Save Failed", message, parent=self)
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
        return self.save_config(update_status=True, show_error=True)

    def on_close(self) -> None:
        saved = self.save_config(update_status=False, show_error=False)
        if not saved:
            try:
                should_close = messagebox.askyesno(
                    "Settings Were Not Saved",
                    "The application could not save the current settings.\n\nClose the Brisart Research Archive anyway?",
                    parent=self,
                )
            except tk.TclError:
                should_close = True
            if not should_close:
                self._set_status("Close cancelled. Settings have not been saved.")
                return
        destroy_method = getattr(self, "destroy", None)
        if callable(destroy_method):
            try:
                destroy_method()
            except tk.TclError:
                pass

    def browse_output_folder(self) -> None:
        current_value = str(self._read_tk_value("output_folder", "") or "").strip()
        initial_directory: str | None = None
        if current_value:
            candidate = Path(current_value).expanduser()
            if candidate.is_dir():
                initial_directory = str(candidate)
        if initial_directory is None:
            try:
                initial_directory = str(get_output_folder(getattr(self, "settings", None)))
            except (OSError, TypeError, ValueError):
                initial_directory = None
        dialog_options = {"title": "Select Output Directory", "mustexist": True, "parent": self}
        if initial_directory:
            dialog_options["initialdir"] = initial_directory
        try:
            selected_folder = filedialog.askdirectory(**dialog_options)
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
            message = f"The selected output folder is unavailable: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Invalid Output Folder", message, parent=self)
            except tk.TclError:
                pass
            return
        if not selected_path.is_dir():
            message = "The selected output path is not a directory."
            self._set_status(message)
            try:
                messagebox.showerror("Invalid Output Folder", message, parent=self)
            except tk.TclError:
                pass
            return
        output_variable = getattr(self, "output_folder", None)
        if output_variable is None:
            self._set_status("Output folder could not be changed because the output-folder setting is unavailable.")
            return
        try:
            output_variable.set(str(selected_path))
        except (AttributeError, tk.TclError) as exc:
            message = f"Output folder could not be changed: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            return
        saved = self.save_config(update_status=False)
        if not saved:
            try:
                output_variable.set(current_value)
            except (AttributeError, tk.TclError):
                pass
            message = "The output-folder change was not saved. The previous value was restored."
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Output Folder Not Saved", message, parent=self)
            except tk.TclError:
                pass
            return
        message = f"Output folder set: {selected_path}"
        self._set_status(message)
        self._log_message(message)

    def open_output_folder(self) -> None:
        """
        Open the current output folder in the OS file explorer. Falls
        back to the default output folder if the configured value is
        blank or unreadable, and creates the folder first if it does
        not exist yet so this never silently fails on a fresh install.
        """
        current_value = str(self._read_tk_value("output_folder", "") or "").strip()
        folder_path: Path
        try:
            folder_path = Path(current_value).expanduser() if current_value else get_output_folder(getattr(self, "settings", None))
        except (OSError, TypeError, ValueError):
            folder_path = get_output_folder(getattr(self, "settings", None))
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            message = f"Could not create the output folder: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Open Folder Failed", message, parent=self)
            except tk.TclError:
                pass
            return
        try:
            if platform_sys.platform.startswith("win"):
                os.startfile(str(folder_path))  # noqa: S606
            elif platform_sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder_path)], check=False)
        except Exception as exc:
            message = f"Could not open the output folder: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Open Folder Failed", message, parent=self)
            except tk.TclError:
                pass
            return
        message = f"Opened output folder: {folder_path}"
        self._set_status(message)
        self._log_message(message)

    # ============================================================
    # Analysis wrappers
    # ============================================================
    def analyze_tfl(self) -> None:
        try:
            run_tfl_analysis(self)
        except Exception as exc:
            message = f"TFL analysis failed: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Analysis Failed", message, parent=self)
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
            message = f"Could not open the TFL CSV: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Open CSV Failed", message, parent=self)
            except tk.TclError:
                pass

    # ============================================================
    # Update wrappers
    #
    # There is no manual "Install Update" action anymore. Every check --
    # whether from this button or the automatic startup check -- goes
    # through the same path in services.updater.gui_integration:
    #   - auto_install_updates ON: installs immediately, no prompt.
    #   - auto_install_updates OFF, notify_on_update ON: asks with a
    #     Yes/No dialog before downloading anything. Declining just
    #     means it will ask again next time.
    #   - auto_install_updates OFF, notify_on_update OFF: checks and
    #     downloads+verifies silently; never installs, never prompts.
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
    # Tooling wrappers (real download/run/open-folder/update-check)
    #
    # Each of these delegates the actual work to
    # services/tooling_manager.py (download+verify+install/run/open-
    # folder/check-updates), which reuses the SAME registry-fetch and
    # signed-download-and-verify machinery as the Archive's own
    # self-updater -- see that module's docstring for the full trust
    # model. This controller layer only ever handles: running the work
    # off the UI thread where needed, translating a result dict into a
    # status/log message, and re-rendering the Tooling page afterward
    # so its Download/Run/Open Folder buttons reflect the new state.
    # ============================================================
    def _refresh_tooling_page_if_visible(self) -> None:
        show_page = getattr(self, "show_page", None)
        if not callable(show_page):
            return
        if getattr(self, "_current_page_name", None) != "Tooling":
            return
        try:
            self.after(0, lambda: show_page("Tooling"))
        except (AttributeError, tk.TclError):
            pass

    def download_tool(self, tool_id: str) -> None:
        """
        Downloads (or updates) one Tooling-page program in the
        background, then re-renders the Tooling page so its buttons
        reflect the new install state. Safe to call for a fresh install
        or an update -- services.tooling_manager.download_and_install_tool()
        handles both identically.
        """
        normalized_id = str(tool_id).strip()
        if not normalized_id:
            self._set_status("Tooling download failed: no program was specified.")
            return
        self._set_status(f"Downloading {normalized_id}...")

        def worker() -> None:
            result = download_and_install_tool(normalized_id, self._log_message)
            status = result.get("status")
            message = str(result.get("message", ""))
            if status == "installed":
                self._set_status(message)
            else:
                self._set_status(f"Tooling download failed: {message}")
                try:
                    self.after(0, lambda: messagebox.showerror("Download Failed", message, parent=self))
                except (AttributeError, tk.TclError):
                    pass
            self._refresh_tooling_page_if_visible()

        threading.Thread(target=worker, name=f"ToolingDownload-{normalized_id}", daemon=True).start()

    def run_tool(self, tool_id: str) -> None:
        """Launches an installed Tooling-page program. Never blocks --
        the underlying subprocess.Popen call returns immediately."""
        normalized_id = str(tool_id).strip()
        if not normalized_id:
            self._set_status("Could not run program: no program was specified.")
            return
        result = run_tooling_program(normalized_id)
        status = result.get("status")
        message = str(result.get("message", ""))
        self._set_status(message)
        self._log_message(message)
        if status not in {"launched"}:
            try:
                messagebox.showerror("Run Failed", message, parent=self)
            except tk.TclError:
                pass

    def open_tool_folder(self, tool_id: str) -> None:
        """Opens an installed Tooling-page program's install folder in
        the OS file explorer."""
        normalized_id = str(tool_id).strip()
        if not normalized_id:
            self._set_status("Could not open folder: no program was specified.")
            return
        result = open_tool_install_folder(normalized_id)
        status = result.get("status")
        message = str(result.get("message", ""))
        self._set_status(message)
        self._log_message(message)
        if status not in {"opened"}:
            try:
                messagebox.showerror("Open Folder Failed", message, parent=self)
            except tk.TclError:
                pass

    def check_tool_updates(self) -> None:
        """
        Checks every currently-installed Tooling-page program against
        its registry entry, in the background. Called automatically by
        gui/main_window.py shortly after launch -- there is no manual
        "Check for Updates" control on the Tooling page itself anymore;
        this is now the ONLY way this check ever runs.

        GATED BY "Enable update checks": since this method is no longer
        reachable via any button a user could click while that master
        switch is off, it must gate itself here.
        """
        enable_update_checks = getattr(self, "enable_update_checks", None)
        try:
            checks_enabled = bool(enable_update_checks.get()) if enable_update_checks is not None else True
        except (AttributeError, tk.TclError):
            checks_enabled = True
        if not checks_enabled:
            return

        def worker() -> None:
            upgrades = check_all_tool_updates(self._log_message)
            self.tool_update_availability = {upgrade["tool_id"]: upgrade for upgrade in upgrades}
            if upgrades:
                names = ", ".join(sorted(upgrade["name"] for upgrade in upgrades))
                self._set_status(f"Tooling updates available: {names}")
                show_tool_update_popup(self, upgrades)
            self._refresh_tooling_page_if_visible()

        threading.Thread(target=worker, name="ToolingUpdateCheck", daemon=True).start()

    # ============================================================
    # Documents
    # ============================================================
    def open_local_doc(self) -> None:
        try:
            open_document_viewer(self)
        except Exception as exc:
            message = f"Could not open the document viewer: {type(exc).__name__}: {exc}"
            self._set_status(message)
            self._log_message(message)
            try:
                messagebox.showerror("Document Viewer Failed", message, parent=self)
            except tk.TclError:
                pass


__all__ = ["SystemController"]
