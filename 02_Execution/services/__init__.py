"""
Application service layer.
Services contain operational logic that should not live inside app.py
or controllers.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import tkinter as tk


def timestamp() -> str:
    """Return a standard local timestamp for log/status messages."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


__all__ = ["timestamp", "set_analysis_text", "analyze_tfl", "fallback_csv_summary", "open_tfl_csv"]
