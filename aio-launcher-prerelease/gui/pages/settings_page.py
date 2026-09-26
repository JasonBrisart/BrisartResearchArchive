"""
File: gui/pages/settings_page.py

Purpose:
Render the Settings page: application info, output directory, update
preferences, update output, and the persistent Activity Log.

Communication / relationships:
- Registered as "Settings" in config/registries.get_page_registry().
- Binds directly to AppState variables through the app proxy
  properties, so values survive page rebuilds.
- Buttons call app.browse_output_folder(), app.open_output_folder(), and
  app.check_updates().
- Reads config/activity_log.load_activity_log().
- services/updater/gui_integration.set_update_text() writes into
  app.update_box, navigating here first if needed.

Settings / parameters:
- Dependency rule: "Automatically download and install updates" and
  "Notify me about updates" only matter while "Enable update checks" is
  on.
- The Activity Log shows up to 100 persisted entries, newest first.

Edge cases:
- Unchecking "Enable update checks" force-unchecks and disables both
  dependent options. Re-enabling it does not restore their previous
  values; the user must opt back in.
- The dependency state is re-applied on every render, so the page is
  always correct even after settings load from disk.
- An empty history shows "Activity log ready.".
- Both Text boxes use the scroll passthrough (Fix 7 in
  gui/components/page_helpers.py).

Known limitations:
- There is no Save button; changes are written when the app closes or
  when another action calls save_config().
- Output-folder text typed into the entry is validated only when saved;
  unsafe values fall back to "outputs".

Examples:
- app.show_page("Settings")
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from config.activity_log import load_activity_log
from gui.components.page_helpers import bind_text_widget_scroll_passthrough
from gui.theme import COLORS, FONT_MONO
from gui.widgets.card import Card


def _apply_update_checks_enabled_state(app) -> None:
    """
    Enforces the dependency rule described in the module docstring.
    Safe to call at any time, including when the Settings page is not
    currently on screen (widget references are checked for liveness
    before being touched, since pages are destroyed/rebuilt on every
    navigation).
    """
    try:
        checks_enabled = bool(app.enable_update_checks.get())
    except tk.TclError:
        return

    dependent_vars_and_widgets = (
        (app.auto_install_updates, getattr(app, "auto_install_checkbox", None)),
        (app.notify_on_update, getattr(app, "notify_checkbox", None)),
    )
    for variable, widget in dependent_vars_and_widgets:
        if not checks_enabled:
            try:
                if bool(variable.get()):
                    variable.set(False)
            except tk.TclError:
                pass
        if widget is None:
            continue
        try:
            if widget.winfo_exists():
                widget.configure(state=("normal" if checks_enabled else "disabled"))
        except tk.TclError:
            pass


def _populate_activity_log(log_box: tk.Text) -> None:
    """
    Fill the Activity Log Text box with persisted history from
    previous sessions, NEWEST FIRST -- load_activity_log() itself
    returns oldest-first/newest-last, so that list is reversed here
    before insertion, falling back to a single placeholder line if no
    history exists yet.
    """
    try:
        history = load_activity_log()
    except Exception:
        history = []
    if history:
        newest_first = list(reversed(history))
        log_box.insert("end", "\n".join(newest_first) + "\n")
    else:
        log_box.insert("end", "Activity log ready.\n")


def render(app):
    root = app.page_shell(
        "Settings",
        "Application configuration, update management, and activity log.",
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
        text="Default location for future archive-wide outputs, reports, and exports.",
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

    # ------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------
    updates_card = Card(root)
    updates_card.grid(row=5, column=0, sticky="ew", padx=26, pady=9)
    updates_card.grid_columnconfigure(0, weight=1)
    ttk.Label(updates_card, text="Updates", style="CardTitle.TLabel").grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        updates_card,
        text=(
            "Stay on the latest version of the Archive. You're always in control -- "
            "nothing is downloaded or installed without your permission unless you "
            "choose to turn on automatic installs below."
        ),
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=1, column=0, sticky="w", pady=(7, 14))

    ttk.Checkbutton(
        updates_card, text="Enable update checks", variable=app.enable_update_checks,
        command=lambda: _apply_update_checks_enabled_state(app),
    ).grid(row=2, column=0, sticky="w", pady=(0, 2))
    ttk.Label(
        updates_card,
        text=(
            "Turn this off and the Archive will never check for updates -- this also "
            "disables the two settings below, since neither does anything without it."
        ),
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=3, column=0, sticky="w", pady=(0, 12))

    auto_install_checkbox = ttk.Checkbutton(
        updates_card, text="Automatically download and install updates", variable=app.auto_install_updates,
    )
    auto_install_checkbox.grid(row=4, column=0, sticky="w", pady=(0, 2))
    app.auto_install_checkbox = auto_install_checkbox
    ttk.Label(
        updates_card,
        text="New updates are installed right away, and you'll see what's new afterward.",
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=5, column=0, sticky="w", pady=(0, 12))

    notify_checkbox = ttk.Checkbutton(
        updates_card, text="Notify me about updates", variable=app.notify_on_update,
    )
    notify_checkbox.grid(row=6, column=0, sticky="w", pady=(0, 2))
    app.notify_checkbox = notify_checkbox
    ttk.Label(
        updates_card,
        text=(
            "Applies either way: with automatic installs off, you'll be asked before an "
            "update is downloaded -- say not now and you'll simply be asked again next "
            "time. With automatic installs on, you'll instead see what's new right after "
            "an update installs itself."
        ),
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=7, column=0, sticky="w", pady=(0, 4))
    ttk.Label(
        updates_card,
        text=(
            "Turn this off along with automatic installs, and the Archive will not check "
            "for updates on its own at all -- opening the program stays completely "
            "untouched. Updates are only ever checked when you press Check Updates below."
        ),
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=8, column=0, sticky="w", pady=(0, 4))
    ttk.Label(
        updates_card,
        text="Note: if an update ever fails a security check, you'll always be told right away.",
        style="CardMuted.TLabel", wraplength=950,
    ).grid(row=9, column=0, sticky="w", pady=(0, 14))

    ttk.Button(
        updates_card, text="Check Updates", command=app.check_updates, style="Accent.TButton",
    ).grid(row=10, column=0, sticky="w")

    # Sync greyed/ungreyed + checked state immediately on every render,
    # so navigating to this page always reflects the true current state
    # of "Enable update checks" -- not just after a click on it.
    _apply_update_checks_enabled_state(app)

    app.update_box = tk.Text(
        root, height=12, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.update_box.grid(row=6, column=0, sticky="ew", padx=26, pady=10)
    app.update_box.insert("end", "Update output will appear here.\n")
    bind_text_widget_scroll_passthrough(app.update_box, app)

    app.add_card(
        root, 7, "Activity Log",
        "Recent application activity: framework launches, autosaves, registry refreshes, and errors. "
        "Kept across sessions -- the most recent 100 actions are shown, newest first.",
    )
    app.log_box = tk.Text(
        root, height=10, bg=COLORS["panel"], fg=COLORS["text"],
        insertbackground=COLORS["accent"], relief="flat", font=FONT_MONO, wrap="word",
    )
    app.log_box.grid(row=8, column=0, sticky="ew", padx=26, pady=(0, 10))
    _populate_activity_log(app.log_box)
    app.log_box.see("1.0")
    bind_text_widget_scroll_passthrough(app.log_box, app)
