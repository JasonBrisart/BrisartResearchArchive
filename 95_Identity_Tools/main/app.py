"""
File: app.py

Purpose
-------
Tkinter desktop GUI for BrisartIdentityTools: Vault, Biometrics, and Packages
in one window.

Public interface:
- class App(tk.Tk)
- main()

Design notes:

This module is only the application shell -- the window, the three tabs'
assembly, and the menu bar. Everything else lives in folder-grouped submodules:

    gui/
      app.py              <- this file: shell + main() only
      core/
        constants.py      APP_TITLE, filetypes, and the repo-root bootstrap
        busy.py           BusyDialog + run_in_background (the threading core)
      widgets/
        dialogs.py        reusable modal dialogs
        path_panel.py     the shared file/folder/drive picker
      tabs/
        tab_vault.py      VaultTab
        tab_biometrics.py BiometricsTab
        tab_packages.py   PackagesTab

No cryptography, validation, or persistence logic lives anywhere in gui/ --
every button is wired directly to the same already-tested application layer the
three CLIs use.

Importing gui.core.constants first runs the repo-root sys.path bootstrap (it
walks up to version.py) before any tool package is imported by the tab modules,
so python -m gui.app, python cli.py gui, and opening a single submodule in an
editor all resolve the tool packages correctly.

Communication / relationships
-----------------------------
Depends on (project modules):
- gui.core.constants (gui/core/constants.py)
- gui.tabs.tab_vault (gui/tabs/tab_vault.py)
- gui.tabs.tab_biometrics (gui/tabs/tab_biometrics.py)
- gui.tabs.tab_packages (gui/tabs/tab_packages.py)
- version (version.py)
Standard library: tkinter.
Imported by: no other module in this tree imports it directly (it is an entry
point).
Covered by tests: no test file imports this module directly.

Settings / parameters
---------------------
No module-level constants, environment variables, or defaulted arguments:
behaviour is controlled entirely by the values callers pass in.

Edge cases
----------
Defines no error paths of its own: it raises nothing and catches nothing, so
any exception from the standard library or a dependency reaches the caller
unchanged.

Known limitations
-----------------
- Location mismatch: this file sits at the repository root, but cli.py's gui
  command runs ``from gui import app`` and the design notes describe it as
  gui/app.py. No gui/app.py exists in this tree, so ``python cli.py gui`` and
  ``python -m gui.app`` fail with ImportError until the file is moved to
  gui/app.py (or cli.py is pointed at the root module). Launch it directly with
  ``python app.py`` in the meantime.
- Standard-library only (tkinter ships with Python), consistent with the rest
  of this ecosystem's zero-third-party-dependency rule.
- No test module imports this file directly; as an entry point it is verified
  only by running it, so check changes manually.

Examples
--------
::

    python app.py
"""

import tkinter as tk
from tkinter import messagebox, ttk

# Import core.constants first: this runs the repo-root sys.path bootstrap before
# the tab modules below import vault/biometrics/packages.
from gui.core.constants import APP_TITLE
from gui.tabs.tab_vault import VaultTab
from gui.tabs.tab_biometrics import BiometricsTab
from gui.tabs.tab_packages import PackagesTab


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x640")
        self.minsize(760, 520)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        notebook.add(VaultTab(notebook), text="Vault")
        notebook.add(BiometricsTab(notebook), text="Biometrics")
        notebook.add(PackagesTab(notebook), text="Packages")
        menu_bar = tk.Menu(self)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Exit", command=self.destroy)
        menu_bar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu_bar)

    def _show_about(self):
        from version import __version__
        messagebox.showinfo(
            APP_TITLE,
            f"BrisartIdentityTools {__version__}\n\n"
            "Local identity tooling: a BSR2-encrypted vault (any file, folder, "
            "or drive, any size), local biometric verification with sealed "
            "templates and file attachments, and identity-bound packages.\n\n"
            "Standard library only. No cloud services, no third-party "
            "dependencies.",
        )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()




