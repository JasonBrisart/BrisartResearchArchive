"""
File: frameworks/TFL/options_screen.py

Purpose
-------
Render the pre-session TFL screen: the reference default-settings list,
the run options (the four reference toggles plus the optional response
timer), a live Current Settings summary, and the Restore Default
Settings / Cancel / Start Experiment actions.

Communication / relationships
-----------------------------
- render_options(session) is called by frameworks/TFL/session_gui.py.
- Writes option values into session.config; Start Experiment calls
  session.begin_session(); Cancel calls session.cancel().
- Uses config.apply_default_options(), describe_current_options(), and
  normalize_timer_seconds().
- Uses gui/theme.py and gui/widgets/card.py, with local fallbacks.

Settings / parameters
---------------------
- TOGGLE_DEFINITIONS: (config key, title, description).
- Timer seconds: Spinbox from RESPONSE_TIMER_MIN_SEC to
  RESPONSE_TIMER_MAX_SEC, enabled only while the timer is checked.

Edge cases
----------
- Every toggle change refreshes the summary and the Default/Modified
  label immediately.
- Unreadable timer text is normalized to TRIAL_DURATION_SEC when the
  experiment starts.
- Returns silently if the session window no longer exists.

Known limitations
-----------------
- Structural values (blocks, intervals, seed) are edited in
  frameworks/TFL/settings.py, as in the reference.

Examples
--------
- render_options(session)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from . import settings
from .config import apply_default_options, describe_current_options, normalize_timer_seconds, update_run_mode

try:
    from gui.widgets.card import Card
except ImportError:
    class Card(ttk.Frame):
        def __init__(self, parent, *args, **kwargs):
            kwargs.setdefault("style", "Card.TFrame")
            kwargs.setdefault("padding", (16, 14))
            super().__init__(parent, *args, **kwargs)

TOGGLE_DEFINITIONS = [
    ("enable_extra_stimuli", "Extra Stimuli",
     "Use the full 60-item stimulus library instead of the first 20."),
    ("enable_perturbations", "Perturbations",
     "Every 5th trial adds a brief physical perturbation and a post-perturbation probe."),
    ("enable_probes", "Probes",
     "Every 4th trial asks which interpretation is most active after feedback."),
    ("enable_delayed_reentry", "Delayed Reentry",
     "Every 6th trial in a block re-presents the stimulus from six trials earlier."),
    ("enable_response_timer", "Response Timer",
     "Limit prediction and behavioral choice to a fixed number of seconds. "
     "Off in the reference protocol; turning it on marks the run Modified TFL."),
]


def _read_controls(session) -> None:
    for key, variable in session.option_vars.items():
        try:
            session.config[key] = bool(variable.get())
        except tk.TclError:
            pass
    try:
        session.config["trial_duration_sec"] = normalize_timer_seconds(session.timer_seconds_var.get())
    except (tk.TclError, AttributeError):
        session.config["trial_duration_sec"] = settings.TRIAL_DURATION_SEC
    update_run_mode(session.config)


def _refresh(session) -> None:
    _read_controls(session)
    try:
        session.summary_var.set("\n".join(describe_current_options(session.config)))
        state = "normal" if session.config.get("enable_response_timer") else "disabled"
        session.timer_spinbox.configure(state=state)
    except (tk.TclError, AttributeError):
        pass


def _restore_defaults(session) -> None:
    session.config = apply_default_options(session.config)
    render_options(session)


def _start(session) -> None:
    _read_controls(session)
    session.begin_session()


def render_options(session: Any) -> None:
    if session.win is None:
        return
    try:
        if not session.win.winfo_exists():
            return
    except tk.TclError:
        return
    session.clear()
    session.option_vars = {}

    root = ttk.Frame(session.win, style="Bg.TFrame", padding=22)
    root.pack(fill="both", expand=True)
    ttk.Label(root, text=settings.VERSION_LABEL, style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        root,
        text="Default settings: " + " \u00b7 ".join(settings.DEFAULT_MODE_DESCRIPTION),
        style="Muted.TLabel", wraplength=900, justify="left",
    ).pack(anchor="w", pady=(4, 14))

    body = ttk.Frame(root, style="Bg.TFrame")
    body.pack(fill="both", expand=True)
    body.grid_columnconfigure(0, weight=3)
    body.grid_columnconfigure(1, weight=2)

    options = Card(body)
    options.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    ttk.Label(options, text="Run Options", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
    row = 1
    for key, title, description in TOGGLE_DEFINITIONS:
        variable = tk.BooleanVar(master=session.win, value=bool(session.config.get(key, False)))
        session.option_vars[key] = variable
        ttk.Checkbutton(options, text=title, variable=variable,
                        command=lambda: _refresh(session)).grid(row=row, column=0, sticky="w", pady=(10, 0))
        ttk.Label(options, text=description, style="CardMuted.TLabel",
                  wraplength=480, justify="left").grid(row=row + 1, column=0, sticky="w")
        row += 2

    timer_row = ttk.Frame(options, style="Card.TFrame")
    timer_row.grid(row=row, column=0, sticky="w", pady=(6, 0))
    ttk.Label(timer_row, text="Seconds per timed response:", style="Card.TLabel").pack(side="left")
    session.timer_seconds_var = tk.StringVar(
        master=session.win,
        value=str(normalize_timer_seconds(session.config.get("trial_duration_sec", settings.TRIAL_DURATION_SEC))),
    )
    session.timer_spinbox = ttk.Spinbox(
        timer_row, from_=settings.RESPONSE_TIMER_MIN_SEC, to=settings.RESPONSE_TIMER_MAX_SEC,
        textvariable=session.timer_seconds_var, width=5, command=lambda: _refresh(session),
    )
    session.timer_spinbox.pack(side="left", padx=(8, 0))
    session.timer_spinbox.bind("<FocusOut>", lambda _event: _refresh(session), add="+")

    summary = Card(body)
    summary.grid(row=0, column=1, sticky="nsew")
    ttk.Label(summary, text="Current Settings", style="CardTitle.TLabel").pack(anchor="w")
    session.summary_var = tk.StringVar(master=session.win)
    ttk.Label(summary, textvariable=session.summary_var, style="CardMuted.TLabel",
              justify="left").pack(anchor="w", pady=(8, 0))

    actions = ttk.Frame(root, style="Bg.TFrame")
    actions.pack(fill="x", pady=(16, 0))
    ttk.Button(actions, text="Restore Default Settings",
               command=lambda: _restore_defaults(session)).pack(side="left")
    ttk.Button(actions, text="Cancel", command=session.cancel).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Start Experiment", style="Accent.TButton",
               command=lambda: _start(session)).pack(side="right")
    _refresh(session)


__all__ = ["render_options", "TOGGLE_DEFINITIONS"]
