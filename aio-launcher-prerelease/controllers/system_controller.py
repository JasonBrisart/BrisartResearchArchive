"""
File: controllers/system_controller.py

Purpose
-------
Coordinate every GUI action: launching TFL, analyzing sessions, opening
output, saving settings, update checks, the document viewer, and
shutdown. Every failure is reported in a dialog and the Activity Log and
never escapes into the Tk event loop.

Communication / relationships
-----------------------------
- Mixed into gui/main_window.BrisartSuiteApp; pages call these methods
  as app.<method>().
- Launches frameworks/TFL/gui_session.TFLGuiSession (imported lazily).
- Analysis: frameworks/TFL/analysis.py and frameworks/TFL/output.py.
- Settings and output paths: config/runtime.py.
- Updates: services/updater/gui_integration.check_updates().
- Documents: gui/components/document_viewer.py.

Settings / parameters
---------------------
- _collect_settings() builds a settings dictionary from the live Tk
  variables and window size; frameworks/TFL/gui_session.py uses it so a run writes
  to the output folder currently shown in Settings, even if unsaved.
- tfl_output_dir() is the folder TFL writes to:
  <output folder>/TFL, by default
  %APPDATA%/Brisart Research Archive/outputs/TFL.

Edge cases
----------
- Only one TFL window can be open; a second Run brings the existing
  window to the front.
- Closing the Archive during a run asks first; every answer given so far
  is already saved.
- A failed settings save does not close the application without
  confirmation.
- Opening a folder creates it first.

Known limitations
-----------------
- Opening folders and CSVs uses the operating system's default
  application (os.startfile, open, or xdg-open).
- Analysis runs on the UI thread; a 120-trial session takes well under a
  second.

Examples
--------
- app.start_tfl()
- app.analyze_tfl()
- app.open_tfl_folder()
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from config.runtime import get_output_folder, get_tfl_output_dir, normalize_settings, save_settings as persist_settings
from gui.components.document_viewer import open_local_doc as open_document_viewer
from services.updater.gui_integration import check_updates as run_gui_update_check


def open_with_system(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


class SystemController:
    # ---------------------------------------------------------- reporting
    def _fail(self, title: str, message: str) -> None:
        self.log(message)
        try:
            messagebox.showerror(title, message, parent=self)
        except tk.TclError:
            pass

    def _read(self, attribute: str, default):
        try:
            return getattr(self, attribute).get()
        except (AttributeError, tk.TclError):
            return default

    def _collect_settings(self) -> dict:
        settings = dict(getattr(self, "settings", {}) or {})
        for key in ("output_folder", "enable_update_checks", "notify_on_update", "auto_install_updates", "theme"):
            settings[key] = self._read(key, settings.get(key))
        for key, method in (("window_width", self.winfo_width), ("window_height", self.winfo_height)):
            try:
                size = int(method())
                if size > 1:
                    settings[key] = size
            except (TypeError, ValueError, tk.TclError):
                pass
        return normalize_settings(settings)

    def tfl_output_dir(self) -> Path:
        return get_tfl_output_dir(self._collect_settings())

    # ---------------------------------------------------------- TFL
    def tfl_running(self) -> bool:
        session = getattr(self, "tfl_session", None)
        return session is not None and session.window_exists()

    def start_tfl(self) -> None:
        if self.tfl_running():
            try:
                self.tfl_session.win.lift()
                self.tfl_session.win.focus_force()
            except tk.TclError:
                pass
            return
        try:
            from frameworks.TFL.gui_session import TFLGuiSession
            self.tfl_session = TFLGuiSession(self)
            self.tfl_session.start()
        except Exception as exc:
            self.tfl_session = None
            self._fail("TFL Launch Failed", f"TFL could not start: {type(exc).__name__}: {exc}")

    def set_analysis_text(self, report: str) -> None:
        box = getattr(self, "analysis_box", None)
        try:
            if box is None or not box.winfo_exists():
                return
            box.delete("1.0", "end")
            box.insert("end", str(report))
            box.see("1.0")
        except tk.TclError:
            pass

    def analyze_tfl(self, path: Path | str | None = None) -> None:
        try:
            from frameworks.TFL.analysis import analyze_output
            from frameworks.TFL.output import latest_session_file
            target = Path(path) if path else latest_session_file(self.tfl_output_dir())
            report = analyze_output(target) if target else (
                f"No TFL session files exist yet in:\n{self.tfl_output_dir()}\n\nRun TFL first."
            )
        except Exception as exc:
            self._fail("Analysis Failed", f"TFL analysis failed: {type(exc).__name__}: {exc}")
            return
        self.set_analysis_text(report)
        self.log(f"TFL analysis: {target.name if target else 'no sessions yet'}")

    def choose_tfl_session(self) -> None:
        try:
            selected = filedialog.askopenfilename(
                title="Choose a TFL session CSV", initialdir=str(self.tfl_output_dir()),
                filetypes=[("TFL session CSV", "*.csv")], parent=self,
            )
        except tk.TclError as exc:
            self._fail("Choose Session Failed", f"The file dialog could not open: {exc}")
            return
        if selected:
            self.analyze_tfl(selected)

    def open_latest_tfl_csv(self) -> None:
        from frameworks.TFL.output import latest_session_file
        path = latest_session_file(self.tfl_output_dir())
        if path is None:
            self._fail("No Sessions", f"No TFL session files exist yet in:\n{self.tfl_output_dir()}")
            return
        try:
            open_with_system(path)
        except Exception as exc:
            self._fail("Open CSV Failed", f"Could not open {path.name}: {type(exc).__name__}: {exc}")

    def open_tfl_folder(self) -> None:
        self._open_folder(self.tfl_output_dir())

    def open_output_folder(self) -> None:
        self._open_folder(get_output_folder(self._collect_settings()))

    def _open_folder(self, folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            open_with_system(folder)
            self.log(f"Opened folder: {folder}")
        except Exception as exc:
            self._fail("Open Folder Failed", f"Could not open {folder}: {type(exc).__name__}: {exc}")

    # ---------------------------------------------------------- settings
    def save_config(self, *, update_status: bool = False, show_error: bool = False) -> bool:
        try:
            normalized = self._collect_settings()
            saved = persist_settings(normalized)
        except Exception as exc:
            saved, normalized = False, None
            reason = f"{type(exc).__name__}: {exc}"
        else:
            reason = "the settings file could not be written"
        if not saved:
            message = f"Settings were not saved: {reason}."
            if show_error:
                self._fail("Settings Save Failed", message)
            else:
                self.log(message)
            return False
        self.settings = normalized
        if update_status:
            self.log("Settings saved.")
        return True

    def browse_output_folder(self) -> None:
        previous = self._read("output_folder", "")
        try:
            selected = filedialog.askdirectory(
                title="Select Output Directory", mustexist=True, parent=self,
                initialdir=str(get_output_folder(self._collect_settings())),
            )
        except tk.TclError as exc:
            self._fail("Browse Failed", f"The folder dialog could not open: {exc}")
            return
        if not selected:
            return
        self.output_folder.set(str(Path(selected).resolve()))
        if not self.save_config(show_error=True):
            self.output_folder.set(previous)
            return
        self.log(f"Output folder set: {selected}")

    def on_close(self) -> None:
        if self.tfl_running():
            try:
                if not messagebox.askyesno(
                    "TFL Run In Progress",
                    "A TFL run is still open. Every answer given so far is already saved.\n\nClose anyway?",
                    parent=self,
                ):
                    return
            except tk.TclError:
                pass
            self.tfl_session.end_run("Archive closed")
        if not self.save_config():
            try:
                if not messagebox.askyesno("Settings Not Saved", "Settings could not be saved. Close anyway?", parent=self):
                    return
            except tk.TclError:
                pass
        try:
            self.destroy()
        except tk.TclError:
            pass

    # ---------------------------------------------------------- other
    def check_updates(self) -> None:
        run_gui_update_check(self)

    def open_local_doc(self) -> None:
        try:
            open_document_viewer(self)
        except Exception as exc:
            self._fail("Document Viewer Failed", f"Could not open the document viewer: {type(exc).__name__}: {exc}")


__all__ = ["SystemController", "open_with_system"]
