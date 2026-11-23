"""
File: gui/pages/dashboard_page.py

Purpose
-------
Render the Dashboard, the landing page: start TFL, analyze the latest
session, and jump to the other pages.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("Dashboard"); DEFAULT_PAGE in
  gui/navigation.py.
- Buttons call app.start_tfl(), app.analyze_tfl() (after switching to
  Results), app.open_tfl_folder(), and app.show_page().

Settings / parameters
---------------------
- Cards occupy grid rows 2 and 3.

Edge cases
----------
- Analyze Latest Session switches to Results first so the report has a
  box to appear in.

Known limitations
-----------------
- Holds no state; rebuilt on every visit.

Examples
--------
- app.show_page("Dashboard")
"""
from __future__ import annotations


def _analyze_latest(app) -> None:
    app.show_page("Results")
    app.analyze_tfl()


def render(app):
    root = app.page_shell("Dashboard", "Run the Temporal Feedback Loop and review its sessions.")
    app.add_card(
        root, 2, "Temporal Feedback Loop",
        "Start a TFL run, analyze the most recent session, or open the folder where every session is saved.",
        [
            ("Run TFL", app.start_tfl, True),
            ("Analyze Latest Session", lambda: _analyze_latest(app), False),
            ("Open TFL Folder", app.open_tfl_folder, False),
        ],
    )
    app.add_card(
        root, 3, "Archive",
        "Read local documentation, or change output and update settings.",
        [
            ("Open Archive", lambda: app.show_page("Archive"), False),
            ("Open Settings", lambda: app.show_page("Settings"), False),
        ],
    )
