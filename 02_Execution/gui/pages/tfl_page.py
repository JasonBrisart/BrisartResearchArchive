"""
File: gui/pages/tfl_page.py

Purpose
-------
Render the TFL page: what the framework does, where its sessions are
saved, how to use the keyboard, and the trial procedure. Replaces the
Frameworks page now that TFL is the only framework.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("TFL") through gui/navigation.py.
- Buttons call app.start_tfl(), app.show_page("Results"), and
  app.open_tfl_folder().
- Reads frameworks/TFL/settings.py for the identity text and
  app.tfl_output_dir() for the folder.

Settings / parameters
---------------------
- Cards occupy grid rows 2 to 5: Run, Saving, Keyboard, Procedure.

Edge cases
----------
- The save folder is recomputed on every visit from the live Output
  Directory setting.

Known limitations
-----------------
- Run options are chosen in the TFL window that Run opens, not on this
  page.
- The Run card describes the default run in fixed wording (3 blocks of 40
  trials, probes and delayed reentry on, perturbations off, 12-second
  timer) and the Keyboard card lists the keys by hand; edit them if a
  default or a key changes.

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
        "(Default TFL: 3 blocks of 40 trials, probes and delayed reentry on, perturbations off, 12-second response timer on).",
        [("Run TFL", app.start_tfl, True), ("Results", lambda: app.show_page("Results"), False)],
    )
    app.add_card(
        root, 3, "Saving",
        "Every answer is saved the moment it is given. Each run gets its own CSV named with the date and "
        f"time it started, so earlier sessions are never overwritten.\n\nSaved to:\n{app.tfl_output_dir()}",
        [("Open TFL Folder", app.open_tfl_folder, False)],
    )
    app.add_card(
        root, 4, "Keyboard",
        "Every answer can be given from the keyboard: A, B, and U answer the choice questions, Enter "
        "views the stimulus and submits the affect rating, Esc stops the run, and F11 switches to full "
        "screen. A key held down answers only once.",
    )
    app.add_card(
        root, 5, "Procedure",
        "Each trial: cue and prior instruction, the ambiguous stimulus, a prediction (A/B), an affect rating "
        "(0\u2013100), an optional perturbation step, a final behavioral choice (A/B), feedback, and on probe "
        "or delayed-reentry trials a content probe (A/B/U).",
    )


