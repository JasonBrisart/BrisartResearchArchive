"""
TFL trial screen — pure presentation layer.

Renders whatever TFLSessionEngine reports and forwards user input back
into the engine (session.engine.submit_*). This module owns zero trial
state; the engine (engine.py) is the single source of truth. That
separation is what makes the engine unit-testable without Tkinter.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from . import analysis, feedback

try:
    from gui.widgets.card import Card
except ImportError:
    class Card(ttk.Frame):
        def __init__(self, parent, *args, **kwargs):
            super().__init__(parent, *args, style="Card.TFrame", **kwargs)

WINDOW_PADDING = 22
CONTENT_WRAP_LENGTH = 860
HEADER_WRAP_LENGTH = 900
PREDICTION_CHOICES = ("A", "B")
PROBE_CHOICES = ("A", "B", "U")


# ============================================================
# Validation
# ============================================================

def validate_session(session: Any) -> None:
    """
    Validate the minimum rendering interface expected from a GUI
    session adapter. Catches wiring problems before Tkinter creates
    only part of the screen.
    """
    required_attributes = ("win", "engine")
    missing_attributes = [name for name in required_attributes if not hasattr(session, name)]
    if missing_attributes:
        raise AttributeError("TFL GUI session is missing required attributes: " + ", ".join(missing_attributes))
    required_methods = ("clear", "render", "cancel", "window_exists")
    missing_methods = [name for name in required_methods if not callable(getattr(session, name, None))]
    if missing_methods:
        raise AttributeError("TFL GUI session is missing required methods: " + ", ".join(missing_methods))


def session_window_exists(session: Any) -> bool:
    try:
        return bool(session.window_exists())
    except (AttributeError, tk.TclError):
        return False


# ============================================================
# Presentation helpers
# ============================================================

def build_header(session: Any, root: ttk.Frame, trial: dict) -> ttk.Frame:
    header = ttk.Frame(root, style="Bg.TFrame")
    header.pack(fill="x")
    ttk.Label(
        header,
        text=f"TFL Trial {session.engine.progress_label()}",
        style="Title.TLabel",
    ).pack(anchor="w")
    prior_instruction = str(trial.get("prior_instruction", "")).strip()
    prior_text = f"Interpretation {prior_instruction} is more likely" if prior_instruction else "No directed prior"
    ttk.Label(
        header,
        text=f"Block: {trial['block']} | Cue: {trial['cue']} | Prior: {prior_text}",
        style="Muted.TLabel",
        wraplength=HEADER_WRAP_LENGTH,
        justify="left",
    ).pack(anchor="w", pady=(4, 18))
    return header


def info_block(parent, title: str, body: Any) -> Card:
    card = Card(parent)
    card.pack(fill="x", pady=6)
    ttk.Label(card, text=str(title), style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(
        card, text=str(body), style="CardMuted.TLabel",
        wraplength=CONTENT_WRAP_LENGTH, justify="left",
    ).pack(anchor="w", pady=(6, 0))
    return card


def build_trial_information(content: ttk.Frame, trial: dict) -> None:
    info_block(content, "Ambiguous stimulus", trial["ambiguous_text"])
    info_block(content, "Interpretation A", trial["interpretation_a"])
    info_block(content, "Interpretation B", trial["interpretation_b"])
    if trial.get("perturbation_trial", False):
        perturbation_type = str(trial.get("perturbation_type", "")).strip()
        try:
            instruction = feedback.make_perturbation_instruction(perturbation_type)
        except Exception as exc:
            instruction = f"Perturbation instruction unavailable: {type(exc).__name__}: {exc}"
        info_block(content, "Perturbation", instruction)


def build_action_bar(session: Any, root: ttk.Frame) -> ttk.Frame:
    actions = ttk.Frame(root, style="Bg.TFrame")
    actions.pack(fill="x", pady=(12, 0))
    ttk.Button(actions, text="Cancel Run", command=session.cancel).pack(side="left")
    return actions


# ============================================================
# Stage-specific response sections
# ============================================================

def render_timed_choice_stage(session: Any, content: ttk.Frame, title: str, submit_fn) -> None:
    form = Card(content)
    form.pack(fill="x", pady=12)
    ttk.Label(form, text=title, style="CardTitle.TLabel").pack(anchor="w")
    if session.engine.seconds_remaining() is not None:
        countdown_text = tk.StringVar(master=session.win)
        countdown_label = ttk.Label(form, textvariable=countdown_text, style="CardMuted.TLabel")
        countdown_label.pack(anchor="w")
        _tick_countdown(session, countdown_text, countdown_label)
    row = ttk.Frame(form, style="Card.TFrame")
    row.pack(anchor="w", pady=(10, 4))
    for choice in PREDICTION_CHOICES:
        ttk.Button(
            row, text=choice,
            command=lambda value=choice: _submit_and_render(session, submit_fn, value),
        ).pack(side="left", padx=(0, 8))


def _tick_countdown(session: Any, countdown_text: "tk.StringVar", countdown_label: ttk.Label) -> None:
    """
    Self-updating countdown, previously a single static label computed
    once at render time - meaning it displayed e.g. "Time remaining: 12
    seconds" forever, never counting down, until the whole screen got
    rebuilt by some other action. This reschedules itself every 250ms
    and stops cleanly (via the TclError guard) the moment the widget is
    destroyed by the next full screen redraw, so it never leaks a
    runaway .after() loop onto a screen that has already moved on.
    """
    try:
        if not countdown_label.winfo_exists():
            return
    except tk.TclError:
        return
    remaining = session.engine.seconds_remaining()
    if remaining is None:
        return
    try:
        countdown_text.set(f"Time remaining: {remaining} seconds")
    except tk.TclError:
        return
    if remaining <= 0:
        return
    try:
        session.win.after(250, lambda: _tick_countdown(session, countdown_text, countdown_label))
    except tk.TclError:
        return


def render_affect_stage(session: Any, content: ttk.Frame) -> None:
    """
    ttk.Scale reports continuous float positions while being dragged
    (e.g. 50.317), not just clean integer stops. Binding that directly
    to a tk.IntVar - as this used to do - makes Tk raise
    "expected integer but got '50.317'" the instant a user drags the
    handle instead of just clicking it, which is exactly the kind of
    thing that makes a screen feel "sort of working but not really."
    The fix: let the Scale drive a float DoubleVar, and keep a separate
    IntVar (rounded on every change) for display and for what actually
    gets submitted to the engine.
    """
    form = Card(content)
    form.pack(fill="x", pady=12)
    ttk.Label(form, text="Affect intensity: 0-100", style="CardTitle.TLabel").pack(anchor="w")

    initial_value = int(session.engine.current_trial_response.get("affect", 50))
    raw_scale_value = tk.DoubleVar(master=session.win, value=float(initial_value))
    display_value = tk.IntVar(master=session.win, value=initial_value)

    def _sync_display(_value: str = "") -> None:
        try:
            display_value.set(round(raw_scale_value.get()))
        except (tk.TclError, ValueError):
            pass

    scale = ttk.Scale(
        form, from_=0, to=100, orient="horizontal",
        variable=raw_scale_value, command=_sync_display,
    )
    scale.pack(fill="x", pady=(8, 4))
    value_label = ttk.Label(form, textvariable=display_value, style="Card.TLabel")
    value_label.pack(anchor="e")
    ttk.Button(
        form, text="Continue", style="Accent.TButton",
        command=lambda: _submit_and_render(session, session.engine.submit_affect, display_value.get()),
    ).pack(anchor="e", pady=(10, 0))


def render_probe_stage(session: Any, content: ttk.Frame, title: str, submit_fn) -> None:
    form = Card(content)
    form.pack(fill="x", pady=12)
    ttk.Label(form, text=title, style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(form, text="Required", style="CardMuted.TLabel").pack(anchor="w", pady=(0, 6))
    row = ttk.Frame(form, style="Card.TFrame")
    row.pack(anchor="w")
    for choice in PROBE_CHOICES:
        ttk.Button(
            row, text=choice,
            command=lambda value=choice: _submit_and_render(session, submit_fn, value),
        ).pack(side="left", padx=(0, 8))


def render_completion_stage(session: Any, content: ttk.Frame) -> None:
    try:
        output_file = analysis.save_rows(session.engine.rows)
        message = f"TFL Complete. Saved {len(session.engine.rows)} trials to:\n{output_file}"
        # The final save fully supersedes the incremental autosave
        # checkpoint, so it can be safely removed now.
        analysis.remove_autosave_file(session.engine.session_id)
    except Exception as exc:
        message = (
            f"TFL run finished, but the final save failed.\n\n{type(exc).__name__}: {exc}\n\n"
            "The autosave checkpoint from during the run was left in place."
        )
    info_block(content, "Session Complete", message)
    session.log(message.splitlines()[0])
    if getattr(session, "app", None) is not None:
        session.after_finish_in_host_app()


def _submit_and_render(session: Any, submit_fn, value) -> None:
    if submit_fn(value):
        session.render()


# ============================================================
# Orchestration
# ============================================================

def render_trial(session: Any) -> None:
    """
    Render whatever state the engine currently reports. Safe to call
    repeatedly - it always rebuilds the screen from scratch.
    """
    validate_session(session)
    if not session_window_exists(session):
        return
    session.clear()
    if not session_window_exists(session):
        return

    root = ttk.Frame(session.win, style="Bg.TFrame", padding=WINDOW_PADDING)
    root.pack(fill="both", expand=True)

    engine = session.engine
    stage = engine.active_stage()

    if stage == "completion":
        ttk.Label(root, text="TFL Session Complete", style="Title.TLabel").pack(anchor="w", pady=(0, 18))
        render_completion_stage(session, root)
        build_action_bar(session, root)
        return

    trial = engine.current_trial
    if trial is None:
        ttk.Label(root, text="No active trial.", style="TLabel").pack(anchor="w")
        return

    build_header(session, root, trial)
    content = ttk.Frame(root, style="Bg.TFrame")
    content.pack(fill="both", expand=True)
    build_trial_information(content, trial)

    if stage == "prediction":
        render_timed_choice_stage(session, content, "Prediction", engine.submit_prediction)
    elif stage == "affect":
        render_affect_stage(session, content)
    elif stage == "perturbation":
        render_probe_stage(session, content, "Post-perturbation probe", engine.submit_post_perturbation_probe)
    elif stage == "content_probe":
        render_probe_stage(session, content, "Content probe", engine.submit_content_probe)
    elif stage == "behavioral_choice":
        render_timed_choice_stage(session, content, "Final behavioral choice", engine.submit_behavioral_choice)

    build_action_bar(session, root)


__all__ = ["render_trial"]
