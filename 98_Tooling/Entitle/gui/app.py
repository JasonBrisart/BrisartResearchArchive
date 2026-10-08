"""
Entitle GUI — Core Engine

A minimal Tkinter front end for the core Entitle workflows: issue, verify, deploy,
revoke/reinstate/check, and audit report.

Architecture:
    This module is intentionally thin. It builds the main window, a shared output
    pane, and a notebook of tabs -- but it does not know *how* any individual tab
    works. Each tab is a small, self-contained plug-in module under gui/tabs/, and
    is registered explicitly in TAB_MODULES below.

    To add a new tab:
        1. Create gui/tabs/my_new_tab.py with:
             - a ``TAB_TITLE`` string
             - a ``build(parent, app) -> tkinter widget`` function
        2. Import it and add it to TAB_MODULES below.

    No other file needs to change.

    Every tab calls directly into the same ``entitle.*`` functions used by the CLI
    in main.py, so the CLI and the GUI can never drift out of sync with each other.

Requires only the Python standard library (tkinter ships with the standard CPython
installer on Windows, macOS, and most Linux distributions).

Launch with:
    python main.py gui
or directly:
    python gui/app.py
"""
import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from entitle.bootstrap import ensure_bsr_on_path
ensure_bsr_on_path()

from gui.tabs import (
    deploy_tab,
    fork_provenance_tab,
    issue_tab,
    report_tab,
    revoke_tab,
    verify_tab,
)

# Explicit plug-in registry. Order here is the order tabs appear in the UI.
TAB_MODULES = (
    issue_tab,
    verify_tab,
    deploy_tab,
    fork_provenance_tab,
    revoke_tab,
    report_tab,
)


class EntitleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Entitle — Software Rights Management")
        self.geometry("880x640")
        self.minsize(760, 560)
        # Exposed so tab plug-ins can build sensible default paths without needing
        # to know how the app was launched or where it lives.
        self.repo_root = _REPO_ROOT

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.output = ScrolledText(self, height=10, wrap="word", state="disabled")
        self.output.pack(fill="both", expand=False, padx=8, pady=(0, 8))

        for module in TAB_MODULES:
            frame = module.build(notebook, self)
            notebook.add(frame, text=module.TAB_TITLE)

    # ---- shared output API used by every tab plug-in --------------------------
    def show_text(self, text):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.configure(state="disabled")

    def show_json(self, data):
        self.show_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    def show_error(self, exc):
        self.show_text(f"ERROR: {type(exc).__name__}: {exc}")
        messagebox.showerror("Entitle", f"{type(exc).__name__}: {exc}")


def launch():
    app = EntitleApp()
    app.mainloop()


if __name__ == "__main__":
    launch()
