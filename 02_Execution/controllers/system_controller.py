"""
File: controllers/system_controller.py

Purpose
-------
Coordinate every GUI action: launching TFL, analyzing one or several
sessions, opening session files and folders, saving settings, the
document viewer, and shutdown. Every failure is reported in a dialog and
in the Activity Log and never escapes into the Tk event loop.

Communication / relationships
-----------------------------
- Mixed into gui/main_window.BrisartSuiteApp; pages call these methods as
  app.<method>().
- Launches frameworks/TFL/gui_session.TFLGuiSession (imported lazily) and
  calls its end_run() when the Archive closes mid-run.
- Analysis: frameworks/TFL/analysis.analyze_outputs() and
  frameworks/TFL/output.latest_session_file().
- The Results page owns the session list and its selection; it hands the
  chosen files to analyze_tfl() and open_tfl_csvs().
- Settings and output paths: config/runtime.py. Documents:
  gui/components/document_viewer.py.

Settings / parameters
---------------------
- analyze_tfl(paths=None): None analyzes the newest session; one path or a
  list of paths analyzes exactly those (two or more are pooled); an empty
  list shows guidance instead.
- choose_tfl_sessions(): a multi-select file dialog that starts in the TFL
  folder and analyzes what is chosen.
- open_tfl_csvs(paths), MAX_CSVS_AT_ONCE (5): opens each file with the
  operating system's default application.
- _collect_settings() builds the settings dictionary from the live
  output-folder variable, so a run writes to the folder currently shown in
  Settings even if it has not been saved yet.
- tfl_output_dir() is <Output Directory>/TFL, by default
  %APPDATA%/Brisart Research Archive/outputs/TFL.

Edge cases
----------
- Only one TFL window can be open; a second Run brings it to the front.
- Closing the Archive during a run asks first; every answer given so far
  is already saved. A failed settings save asks before closing anyway.
- Browse saves the new folder immediately and restores the previous value
  if that save fails.
- More than MAX_CSVS_AT_ONCE selected files, or none, is refused with a
  message instead of opening anything.
- The file dialog can return a single string on some platforms; the
  result is split with tk.splitlist() before use.
- A report is written only if the Results page is showing; otherwise the
  action is still logged.
- Opening a folder creates it first.

Known limitations
-----------------
- Opening folders and CSVs uses the operating system default (os.startfile,
  open, or xdg-open); it is not tested end to end.
- Analysis runs on the UI thread; a pooled analysis of a few dozen
  120-trial sessions stays well under a second.

Examples
--------
- app.start_tfl()
- app.analyze_tfl()
- app.analyze_tfl([first_csv, second_csv])
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


MAX_CSVS_AT_ONCE = 5


def as_path_list(paths) -> list[Path]:
    """A single path or any iterable of paths, as a list of Paths."""
    if isinstance(paths, (str, Path)):
        return [Path(paths)]
    return [Path(item) for item in paths]


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
        settings["output_folder"] = self._read("output_folder", settings.get("output_folder"))
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

    def analyze_tfl(self, paths=None) -> None:
        try:
            from frameworks.TFL.analysis import analyze_outputs
            from frameworks.TFL.output import latest_session_file
            if paths is None:
                latest = latest_session_file(self.tfl_output_dir())
                if latest is None:
                    self.set_analysis_text(
                        f"No TFL session files exist yet in:\n{self.tfl_output_dir()}\n\nRun TFL first.")
                    self.log("TFL analysis: no sessions yet")
                    return
                targets = [latest]
            else:
                targets = as_path_list(paths)
            if not targets:
                self.set_analysis_text("Select one or more sessions in the list, then choose Analyze Selected.")
                return
            report = analyze_outputs(targets)
        except Exception as exc:
            self._fail("Analysis Failed", f"TFL analysis failed: {type(exc).__name__}: {exc}")
            return
        self.set_analysis_text(report)
        self.log(f"TFL analysis: {targets[0].name}" if len(targets) == 1
                 else f"TFL analysis: {len(targets)} sessions pooled")

    def choose_tfl_sessions(self) -> None:
        try:
            selected = filedialog.askopenfilenames(
                title="Choose one or more TFL session CSVs", initialdir=str(self.tfl_output_dir()),
                filetypes=[("TFL session CSV", "*.csv")], parent=self,
            )
            chosen = list(self.tk.splitlist(selected)) if selected else []
        except tk.TclError as exc:
            self._fail("Choose Sessions Failed", f"The file dialog could not open: {exc}")
            return
        if chosen:
            self.analyze_tfl(chosen)

    def open_tfl_csvs(self, paths) -> None:
        targets = as_path_list(paths)
        if not targets:
            self._fail("Nothing Selected", "Select one or more sessions in the list first.")
            return
        if len(targets) > MAX_CSVS_AT_ONCE:
            self._fail("Too Many Files",
                       f"{len(targets)} sessions are selected. Select at most {MAX_CSVS_AT_ONCE} to open "
                       "at once, or use Open TFL Folder.")
            return
        for path in targets:
            try:
                open_with_system(path)
            except Exception as exc:
                self._fail("Open CSV Failed", f"Could not open {path.name}: {type(exc).__name__}: {exc}")
                return

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
    def open_local_doc(self) -> None:
        try:
            open_document_viewer(self)
        except Exception as exc:
            self._fail("Document Viewer Failed", f"Could not open the document viewer: {type(exc).__name__}: {exc}")


__all__ = ["SystemController", "open_with_system"]

