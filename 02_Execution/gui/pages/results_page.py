import tkinter as tk

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
