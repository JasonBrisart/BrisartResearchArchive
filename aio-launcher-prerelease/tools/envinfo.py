"""
File: tools/envinfo.py

Purpose:
Print a one-shot environment snapshot for bug reports. Paste the output
into the Environment field of a docs/KNOWN_ISSUES.md entry.

Communication / relationships:
- Standalone; talks to nothing else in the codebase. Reads only OS,
  Python, and Tk metadata, never modifies anything, and never sends
  data anywhere.

Settings / parameters:
- Reports OS name, release, and build; machine and processor
  architecture; Python version, bitness, and implementation; and the
  Tcl/Tk version.

Edge cases:
- If Tkinter is unavailable, the Tk line explains why instead of
  crashing.
- The GUI popup is skipped silently when no display is available; the
  console output is enough.

Known limitations:
- A mismatch between the Python bitness and the machine architecture
  (for example x64 Python on an ARM64 OS) is reported but not
  interpreted.

Examples:
- python tools/envinfo.py
"""
from __future__ import annotations

import platform


def get_tk_version() -> str:
    """
    Returns "Tcl X.Y / Tk X.Y", or a short explanation if Tkinter isn't
    available at all (e.g. a minimal Python build with no Tcl/Tk
    support) rather than letting an ImportError crash this script.
    """
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        tcl_version = root.tk.call("info", "patchlevel")
        tk_version = str(tkinter.TkVersion)
        root.destroy()
        return f"Tcl {tcl_version} / Tk {tk_version}"
    except Exception as exc:
        return f"unavailable ({type(exc).__name__}: {exc})"


def build_environment_report() -> str:
    return "\n".join([
        f"OS: {platform.system()} {platform.release()} (build {platform.version()})",
        f"Machine / Processor: {platform.machine()} / {platform.processor() or 'unknown'}",
        f"Python: {platform.python_version()} ({platform.architecture()[0]}, {platform.python_implementation()})",
        f"Tkinter: {get_tk_version()}",
    ])


if __name__ == "__main__":
    report = build_environment_report()
    print(report)
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showinfo(
            "Environment Snapshot",
            report + "\n\n(Also printed to the console -- copy from either place.)",
        )
        root.destroy()
    except Exception:
        pass  # console output above is enough if a GUI popup isn't available
