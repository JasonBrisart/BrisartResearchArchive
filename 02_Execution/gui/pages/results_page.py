"""
File: gui/pages/results_page.py

Purpose
-------
Render the Results page: analyze the latest TFL session or a chosen
one, open the latest CSV, and show the analysis report.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("Results") through
  gui/navigation.py.
- Buttons call app.analyze_tfl(), app.choose_tfl_session(),
  app.open_latest_tfl_csv(), and app.open_tfl_folder().
- SystemController.set_analysis_text() writes reports into
  app.analysis_box; frameworks/TFL/gui_session.py shows this page and analyzes the
  finished session after a run.

Settings / parameters
---------------------
- app.analysis_box: a 30-line Text widget at grid row 3.

Edge cases
----------
- The wheel scrolls the page when the report fits in the box (see
  bind_text_widget_scroll_passthrough()).
- A short instruction is shown until an analysis runs.

Known limitations
-----------------
- Plain-text report; no charts.

Examples
--------
- app.show_page("Results"); app.analyze_tfl()
"""
import tkinter as tk

from gui.components.page_helpers import bind_text_widget_scroll_passthrough
from gui.theme import COLORS, FONT_MONO


def render(app):
    root = app.page_shell("Results", "Analyze TFL sessions and open their CSV files.")
    app.add_card(
        root, 2, "TFL Sessions",
        f"Sessions are saved in:\n{app.tfl_output_dir()}",
        [
            ("Analyze Latest Session", app.analyze_tfl, True),
            ("Choose Session...", app.choose_tfl_session, False),
            ("Open Latest CSV", app.open_latest_tfl_csv, False),
            ("Open TFL Folder", app.open_tfl_folder, False),
        ],
    )
    app.analysis_box = tk.Text(
        root, height=30, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.analysis_box.grid(row=3, column=0, sticky="ew", padx=26, pady=10)
    app.analysis_box.insert("end", "No analysis yet. Choose Analyze Latest Session, or run TFL first.\n")
    bind_text_widget_scroll_passthrough(app.analysis_box, app)
