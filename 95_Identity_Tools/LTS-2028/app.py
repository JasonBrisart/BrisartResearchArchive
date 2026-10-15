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
assembly, and the menu bar. It sits at the repository root; everything else
lives in folder-grouped submodules under gui/:

    app.py                <- this file: shell + main() only
    gui/
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
walks up to version.py) before any tool package is imported by the tab modules.

Supported launch commands, both run from the repository root:
- ``python app.py`` -- runs this file directly.
- ``python cli.py gui`` -- the dispatcher imports this module and calls main().

Communication / relationships
-----------------------------
Depends on (project modules):
- gui.core.constants (gui/core/constants.py)
- gui.tabs.tab_vault (gui/tabs/tab_vault.py)
- gui.tabs.tab_biometrics (gui/tabs/tab_biometrics.py)
- gui.tabs.tab_packages (gui/tabs/tab_packages.py)
- version (version.py)
Standard library: tkinter.
Imported by:
- cli.py (only inside the gui command's handler)
Covered by tests: tests/test_cli_dispatcher.py imports it to confirm the gui
command resolves to this module, with main() replaced so no window opens.

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
- There is no gui/app.py, so ``python -m gui.app`` is not a launch command.
- Standard-library only (tkinter ships with Python), consistent with the rest
  of this ecosystem's zero-third-party-dependency rule.
- Tests confirm only that the gui command reaches this module's main(); the
  window itself is not exercised, so check visual changes by running it.

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




