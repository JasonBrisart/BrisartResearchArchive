"""
gui/pages/results_page.py
The Results page: run/refresh TFL analysis, open the generated CSV,
and display the analysis report in a scrollable Text box
(analysis_box). Registered as the "Results" page in
config.registries.get_page_registry(). services.set_analysis_text()
(see services/__init__.py) writes new report text directly into
analysis_box on every "Run TFL Analysis" click; this module only ever
sets its initial placeholder content.

MOUSE WHEEL OVER analysis_box, specifically:
Calls bind_text_widget_scroll_passthrough() right after creating
analysis_box, for the same reason as gui/pages/settings_page.py's
update_box/log_box: Tk's built-in, automatic Text-widget scroll
binding intercepts and swallows the wheel event even when the box's
own content is already fully visible (nothing to scroll internally),
which otherwise blocks the event from ever reaching the page-level
scroll handler in gui/main_window.py. See
gui.components.page_helpers.bind_text_widget_scroll_passthrough()'s
docstring (FIX 7) for the full mechanism.
"""
import tkinter as tk

from gui.components.page_helpers import bind_text_widget_scroll_passthrough
from gui.theme import COLORS, FONT_MONO


def render(app):
    root = app.page_shell(
        "Results",
        "Run analysis tools, inspect generated output, and open result files.",
    )
    app.add_card(
        root, 2, "Results Actions",
        (
            "Run the current analysis pipeline, open the generated CSV output, "
            "or run the selected framework before analyzing results."
        ),
        [
            ("Run TFL Analysis", app.analyze_tfl, True),
            ("Open CSV", app.open_tfl_csv, False),
            ("Run Selected Framework", app.start_selected_framework, False),
        ],
    )
    app.add_card(
        root, 3, "Results Summary",
        (
            "Analysis output appears below. "
            "If no CSV exists yet, run the TFL assay first. "
            "Future versions can display visual metrics, charts, export summaries, "
            "and archive-ready reports here."
        ),
    )
    app.analysis_box = tk.Text(
        root, height=30, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.analysis_box.grid(row=4, column=0, sticky="ew", padx=26, pady=10)
    app.analysis_box.insert(
        "end",
        "No analysis run yet.\n\n"
        "Recommended flow:\n"
        "1. Run selected framework.\n"
        "2. Generate CSV output.\n"
        "3. Run analysis.\n"
        "4. Inspect or export results.\n",
    )
    bind_text_widget_scroll_passthrough(app.analysis_box, app)
