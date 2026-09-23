"""
ui
--

Modular Tkinter presentation layer for ArchiveSnapshot.

The UI package delegates all archival operations to the engine package.
It is organized as one module per notebook tab, plus shared modules for
settings persistence and filesystem actions:

    app.py               - main application window and tab coordination
    app_settings.py       - GUI settings load/save
    path_actions.py        - shared folder picker and file/folder opening
    calendar_tab.py        - Calendar tab
    snapshot_tab.py        - Create Snapshot tab
    comparison_tab.py      - Compare tab
    verification_tab.py    - Verify tab
    settings_tab.py        - Settings tab
    about_tab.py           - About tab
"""

from .app import ArchiveSnapshotApp, run_gui


__all__ = [
    "ArchiveSnapshotApp",
    "run_gui",
]
