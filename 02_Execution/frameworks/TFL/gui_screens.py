"""
File: frameworks/TFL/gui_screens.py

Purpose
-------
Render the TFL trial screens. Pure presentation: show the engine's
current stage, forward input to engine methods, and never write files or
decide protocol behavior.

Communication / relationships
-----------------------------
- render_trial(session) is called by frameworks/TFL/gui_session.TFLGuiSession.render().
- Reads session.engine; after each input calls session.after_input(),
  which handles completion and redraws.
- Shows session.save_status() in the footer of every trial screen.
- Uses gui/components/card.py.

Settings / parameters
---------------------
- Screens: cue (previous feedback, cue, prior, View Stimulus),
  prediction, affect (typed 0-100 entry), perturbation, post-perturbation
  probe, behavioral choice, content probe (with this trial's feedback),
  completion (final feedback, save location, any save problems).
- The countdown label refreshes every 250 ms while the response timer
  is on.

Edge cases
----------
- Invalid affect text shows the reference message and stays on the
  stage.
- The countdown stops as soon as its label is destroyed.
- Enter activates View Stimulus, affect Continue, and perturbation
  Completed.

Known limitations
-----------------
- The screen is rebuilt on every stage change.
- Requires Tk; the CLI and tests never import this module.

Examples
--------
- render_trial(session)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from . import settings
from .config import format_run_mode

from gui.components.card import Card

WRAP = 860


def info_block(parent, title: str, body: Any) -> Card:
    card = Card(parent)
    card.pack(fill="x", pady=5)
    ttk.Label(card, text=str(title), style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(card, text=str(body), style="CardMuted.TLabel", wraplength=WRAP,
              justify="left").pack(anchor="w", pady=(6, 0))
    return card


def _submit(session, method, value=None) -> None:
    accepted = method() if value is None else method(value)
    if accepted or session.engine.active_stage() != getattr(session, "rendered_stage", None):
        session.after_input()


def _bind_enter(session, callback) -> None:
    session.win.unbind("<Return>")
    if callback is not None:
        session.win.bind("<Return>", lambda _event: callback())


def _choice_row(session, parent, title, method, choices) -> None:
    form = Card(parent)
    form.pack(fill="x", pady=10)
    ttk.Label(form, text=title, style="CardTitle.TLabel").pack(anchor="w")
    if session.engine.seconds_remaining() is not None:
        countdown = tk.StringVar(master=session.win)
        label = ttk.Label(form, textvariable=countdown, style="CardMuted.TLabel")
        label.pack(anchor="w")
        _tick(session, countdown, label)
    row = ttk.Frame(form, style="Card.TFrame")
    row.pack(anchor="w", pady=(10, 2))
    for choice in choices:
        ttk.Button(row, text=choice, width=6,
                   command=lambda value=choice: _submit(session, method, value)).pack(side="left", padx=(0, 8))


def _tick(session, variable, label) -> None:
    try:
        if not label.winfo_exists():
            return
        remaining = session.engine.seconds_remaining()
        if remaining is None:
            return
        variable.set(f"Time remaining: {remaining} seconds")
        if remaining > 0:
            session.win.after(250, lambda: _tick(session, variable, label))
    except tk.TclError:
        return


def _affect_form(session, parent) -> None:
    form = Card(parent)
    form.pack(fill="x", pady=10)
    ttk.Label(form, text=settings.AFFECT_PROMPT.rstrip(": "),
              style="CardTitle.TLabel").pack(anchor="w")
    row = ttk.Frame(form, style="Card.TFrame")
    row.pack(anchor="w", pady=(8, 0))
    entry_var = tk.StringVar(master=session.win)
    entry = ttk.Entry(row, textvariable=entry_var, width=8)
    entry.pack(side="left")
    error = tk.StringVar(master=session.win)
    ttk.Label(form, textvariable=error, style="CardMuted.TLabel").pack(anchor="w", pady=(6, 0))

    def submit() -> None:
        if session.engine.submit_affect(entry_var.get()):
            session.after_input()
        else:
            error.set(f"Please enter a whole number from {settings.AFFECT_MIN} to {settings.AFFECT_MAX}.")
            entry.selection_range(0, "end")

    ttk.Button(row, text="Continue", style="Accent.TButton", command=submit).pack(side="left", padx=(8, 0))
    _bind_enter(session, submit)
    entry.focus_set()


def render_trial(session: Any) -> None:
    if not session.window_exists():
        return
    session.clear()
    engine = session.engine
    stage = engine.active_stage()
    session.rendered_stage = stage
    _bind_enter(session, None)
    root = ttk.Frame(session.win, style="Bg.TFrame", padding=22)
    root.pack(fill="both", expand=True)

    if stage == "completion":
        ttk.Label(root, text="TFL Session Complete", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
        if engine.last_feedback:
            info_block(root, "Final trial feedback", engine.last_feedback)
        info_block(root, "Session saved", session.completion_message)
        if engine.save_errors:
            info_block(root, "Save problems", "\n".join(engine.save_errors[-5:]))
        ttk.Button(root, text="Close", command=session.close_windows).pack(anchor="e", pady=(12, 0))
        return

    trial = engine.current_trial
    ttk.Label(root, text=f"Trial {engine.progress_label()}", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        root,
        text=f"Mode: {format_run_mode(trial['run_mode'])}  |  Block: {trial['block']}",
        style="Muted.TLabel",
    ).pack(anchor="w", pady=(2, 12))
    content = ttk.Frame(root, style="Bg.TFrame")
    content.pack(fill="both", expand=True)

    if stage == "cue":
        if engine.last_feedback:
            info_block(content, "Previous trial", engine.last_feedback)
        info_block(content, "Cue/context", trial["cue"])
        info_block(content, "Prior instruction",
                   f"Interpretation {trial['prior_instruction']} is more likely.")
        view = lambda: _submit(session, engine.continue_cue)  # noqa: E731
        ttk.Button(content, text="View Stimulus", style="Accent.TButton", command=view).pack(anchor="e", pady=10)
        _bind_enter(session, view)
    else:
        info_block(content, "Ambiguous stimulus", trial["ambiguous_text"])
        info_block(content, "Interpretation A", trial["interpretation_a"])
        info_block(content, "Interpretation B", trial["interpretation_b"])
        if stage == "prediction":
            _choice_row(session, content, "Predicted interpretation (A/B)", engine.submit_prediction, ("A", "B"))
        elif stage == "affect":
            _affect_form(session, content)
        elif stage == "perturbation":
            info_block(content, "Perturbation step", engine.perturbation_instruction())
            done = lambda: _submit(session, engine.continue_perturbation)  # noqa: E731
            ttk.Button(content, text="Completed", style="Accent.TButton", command=done).pack(anchor="e", pady=10)
            _bind_enter(session, done)
        elif stage == "post_perturbation_probe":
            _choice_row(session, content,
                        "Which interpretation is most active immediately after the perturbation? (A/B/U)",
                        engine.submit_post_perturbation_probe, ("A", "B", "U"))
        elif stage == "behavioral_choice":
            _choice_row(session, content, "Final behavioral choice (A/B)",
                        engine.submit_behavioral_choice, ("A", "B"))
        elif stage == "content_probe":
            if engine.current_feedback:
                info_block(content, "Feedback", engine.current_feedback)
            _choice_row(session, content,
                        "Probe: Which interpretation is most active in your mind right now? (A/B/U for uncodable)",
                        engine.submit_content_probe, ("A", "B", "U"))

    actions = ttk.Frame(root, style="Bg.TFrame")
    actions.pack(fill="x", pady=(10, 0))
    ttk.Button(actions, text="Cancel Run", command=session.cancel).pack(side="left")
    ttk.Label(actions, text=session.save_status(), style="Muted.TLabel").pack(side="right")


__all__ = ["render_trial", "info_block"]
