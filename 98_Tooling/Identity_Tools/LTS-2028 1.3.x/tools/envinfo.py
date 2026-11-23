"""
File: tools/envinfo.py

Purpose
-------
One-shot environment snapshot for bug reports. Run this and paste its output
directly into the **Environment:** field of a KNOWN_ISSUES.md entry (see
docs/KNOWN_ISSUES.md for the standard bug report template).

Public interface:
- get_tk_version() -- Returns "Tcl X.Y / Tk X.Y", or a short explanation if
  Tkinter isn't available at all (e.g. a minimal Python build with no Tcl/Tk
  support) rather than letting an ImportError crash this script.
- build_environment_report()

Design notes:

Talks to: nothing else in the codebase. Standalone, dependency-free, safe to
run from anywhere -- it only reads OS/Python/Tk metadata.

What each line reports, and why it's in the standard bug template:
- OS / OS version / OS build : which OS and build is running. Relevant any time
  a bug might be OS- or driver-specific.
- Machine / Processor : CPU architecture as reported by the OS (e.g. AMD64,
  ARM64, x86_64). Matters on any machine where the installed Python build's own
  architecture might not match the OS/CPU's native architecture -- see the
  "Python" line below.
- Python version / build : exact interpreter version and architecture bit-ness
  of the PYTHON PROCESS ITSELF, which is not always the same as the OS/CPU
  architecture above. On any platform that supports running one CPU
  architecture's binaries under emulation on another (e.g. x64 binaries on an
  ARM64 OS, or vice versa), a mismatch between this line and the
  Machine/Processor line above is exactly the kind of detail that can explain
  platform-specific bugs.
- Tcl/Tk version : the GUI toolkit version bundled with this Python install.
  Every gui/* file in this project depends on Tkinter directly, so this version
  is directly relevant to any GUI bug report.

Communication / relationships
-----------------------------
Standard library: __future__, platform, tkinter.
Imported by: no other module in this tree imports it directly (it is an entry
point).
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
- Broad ``except Exception`` boundary in get_tk_version, module: failures are
  reported to the user/caller rather than crashing.

Known limitations
-----------------
- Never modifies anything and never sends data anywhere.
- Behaviour branches on the host operating system (sys.platform / os.name
  checks in the code); verify changes on Windows, macOS, and Linux.
- No test module imports this file directly; as an entry point it is verified
  only by running it, so check changes manually.

Examples
--------
::

    python -m tools.envinfo
    from tools.envinfo import get_tk_version, build_environment_report
    get_tk_version()
    build_environment_report()
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




