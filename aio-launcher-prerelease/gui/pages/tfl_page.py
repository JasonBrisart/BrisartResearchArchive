"""
File: gui/pages/tfl_page.py

Purpose
-------
Render the TFL page: what the framework does, where its sessions are
saved, and how to run it. Replaces the Frameworks page now that TFL is
the only framework.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("TFL") through
  gui/navigation.py.
- Buttons call app.start_tfl(), app.show_page("Results"), and
  app.open_tfl_folder().
- Reads frameworks/TFL/settings.py for the identity text and app.tfl_output_dir()
  for the folder.

Settings / parameters
---------------------
- Cards occupy grid rows 2 to 4.

Edge cases
----------
- The save folder is recomputed on every visit from the live output
  folder setting.

Known limitations
-----------------
- Run options are chosen in the TFL window that Run opens, not on this
  page.

Examples
--------
- app.show_page("TFL")
"""
from __future__ import annotations

from frameworks.TFL import settings


def render(app):
    root = app.page_shell(settings.FRAMEWORK_NAME, settings.VERSION_LABEL)
    app.add_card(
        root, 2, "Run",
        "Opens the TFL window. Choose run options there, or start straight away with the reference defaults "
        "(Default TFL: 3 blocks of 40 trials, probes and delayed reentry on, perturbations and timer off).",
        [("Run TFL", app.start_tfl, True), ("Results", lambda: app.show_page("Results"), False)],
    )
    app.add_card(
        root, 3, "Saving",
        "Every answer is saved the moment it is given. Each run gets its own CSV named with the date and "
        f"time it started, so earlier sessions are never overwritten.\n\nSaved to:\n{app.tfl_output_dir()}",
        [("Open TFL Folder", app.open_tfl_folder, False)],
    )
    app.add_card(
        root, 4, "Procedure",
        "Each trial: cue and prior instruction, the ambiguous stimulus, a prediction (A/B), an affect rating "
        "(0\u2013100), an optional perturbation step, a final behavioral choice (A/B), feedback, and on probe "
        "or delayed-reentry trials a content probe (A/B/U).",
    )
