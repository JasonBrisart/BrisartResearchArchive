"""
services/tfl_analysis.py
TFL-specific analysis wrappers that bridge the GUI
(controllers/system_controller.py) to the headless TFL analysis layer
(frameworks/TFL/analysis.py) without the controller importing the
framework directly.

Framework-specific by design: if another framework (SST, PFT, ...) later
needs the same GUI bridge, it should get its own <framework>_analysis.py
module rather than overloading this one. Split out of the old
services/__init__.py, which mixed this TFL-only logic into the generic
services package initializer -- so that (a) the name reflects that these
are TFL-only, and (b) the services package no longer needs an
__init__.py at all.
"""
from __future__ import annotations
from pathlib import Path
import tkinter as tk
def set_analysis_text(app, report: str) -> None:
    """Display an analysis report in the Results text box when present."""
    box = getattr(app, "analysis_box", None)
    if box is None:
        return
    try:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", str(report))
        box.see("1.0")
    except tk.TclError:
        pass
def analyze_tfl(app) -> None:
    """Run the TFL analysis pipeline and display the report."""
    from frameworks.TFL import analysis as tfl_analysis
    report = tfl_analysis.analyze_output()
    set_analysis_text(app, report)
def fallback_csv_summary(app) -> str:
    """Return a minimal summary when full analysis is unavailable."""
    from frameworks.TFL import analysis as tfl_analysis
    try:
        path = tfl_analysis.get_default_output_file()
    except Exception as exc:
        return f"No TFL output available: {type(exc).__name__}: {exc}"
    if not Path(path).exists():
        return f"No TFL output file found yet: {path}"
    try:
        rows = tfl_analysis.load_output(path)
    except Exception as exc:
        return f"Could not read TFL output: {type(exc).__name__}: {exc}"
    return f"TFL output: {len(rows)} rows at {path}"
def open_tfl_csv(app) -> None:
    """Open the latest TFL output CSV in the OS default application."""
    import os
    import subprocess
    import sys as platform_sys
    from frameworks.TFL import analysis as tfl_analysis
    path = tfl_analysis.get_default_output_file()
    if not Path(path).exists():
        raise FileNotFoundError(f"No TFL output file found yet: {path}")
    if platform_sys.platform.startswith("win"):
        os.startfile(str(path))  # noqa: S606
    elif platform_sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
__all__ = ["set_analysis_text", "analyze_tfl", "fallback_csv_summary", "open_tfl_csv"]
