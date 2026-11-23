"""
File: gui/pages/settings_page.py

Purpose
-------
Render the Settings page: application identity, output location, and the
persistent Activity Log. Update installation is intentionally outside this
application; releases are obtained manually from the project distribution.

Communication / relationships
-----------------------------
- Rendered by gui/main_window.show_page("Settings") through gui/navigation.py.
- Binds to AppState output_folder through the app proxy property.
- Buttons call app.browse_output_folder(), app.open_output_folder(), and
  app.open_tfl_folder().
- Reads config/activity_log.load_activity_log().

Settings / parameters
---------------------
- Output Directory is stored in config/runtime.py and defaults to the
  Archive AppData folder.
- The Activity Log shows up to 100 persisted entries, newest first.

Edge cases
----------
- The TFL folder line is recomputed on every render from the live output
  folder value.
- An empty activity history shows a single ready message.

Known limitations
-----------------
- There is no Save button; settings are written when the app closes or
  when Browse saves a new folder.
- Output-folder text typed by hand is validated when saved; unsafe values
  fall back to "outputs".

Examples
--------
- app.show_page("Settings")
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config.activity_log import load_activity_log
from gui.components.card import Card
from gui.components.page_helpers import bind_text_widget_scroll_passthrough
from gui.theme import COLORS, FONT_MONO


def _populate_activity_log(log_box: tk.Text) -> None:
    try:
        history = load_activity_log()
    except Exception:
        history = []
    if history:
        log_box.insert("end", "\n".join(reversed(history)) + "\n")
    else:
        log_box.insert("end", "Activity log ready.\n")


def render(app):
    root = app.page_shell(
        "Settings",
        "Application configuration and activity log.",
    )
    app.add_card(
        root, 2, "General",
        (
            f"Application: {app.app_name}\n"
            f"Version: {app.app_version}\n"
            f"Execution Folder:\n{app.execution_dir}"
        ),
    )

    output_card = Card(root)
    output_card.grid(row=3, column=0, sticky="ew", padx=26, pady=9)
    output_card.grid_columnconfigure(1, weight=1)
    ttk.Label(output_card, text="Output Directory", style="CardTitle.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w"
    )
    ttk.Label(
        output_card,
        text=(
            "Relative folders are kept inside the Archive's AppData folder. "
            f"TFL sessions are currently saved to:\n{app.tfl_output_dir()}"
        ),
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(7, 10))
    ttk.Entry(output_card, textvariable=app.output_folder).grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(0, 4)
    )
    ttk.Button(output_card, text="Browse", command=app.browse_output_folder).grid(
        row=2, column=2, padx=(8, 0), pady=(0, 4)
    )
    ttk.Button(output_card, text="Open Folder", command=app.open_output_folder).grid(
        row=3, column=2, padx=(8, 0), pady=(0, 8)
    )
    ttk.Button(output_card, text="Open TFL Folder", command=app.open_tfl_folder).grid(
        row=4, column=2, padx=(8, 0), pady=(0, 8)
    )

    app.add_card(
        root, 4, "Updates",
        "Updates are installed manually from the project's official GitHub distribution. "
        "This application does not check for, download, or install updates.",
    )

    app.add_card(
        root, 5, "Activity Log",
        "Recent application activity: TFL runs, saves, analyses, and errors. "
        "Kept across sessions; the most recent 100 actions are shown, newest first.",
    )
    app.log_box = tk.Text(
        root, height=10, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.log_box.grid(row=6, column=0, sticky="ew", padx=26, pady=(0, 10))
    _populate_activity_log(app.log_box)
    app.log_box.see("1.0")
    bind_text_widget_scroll_passthrough(app.log_box, app)
