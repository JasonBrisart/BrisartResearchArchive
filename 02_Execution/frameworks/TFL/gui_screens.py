"""
File: frameworks/TFL/gui_screens.py

Purpose
-------
Render the TFL trial screens. Pure presentation: show the engine's current
stage in a low-clutter, large-type layout, offer every answer as both a
button and a keyboard key, forward input to engine methods, and never
write files or decide protocol behavior.

Communication / relationships
-----------------------------
- render_trial(session) is called by
  frameworks/TFL/gui_session.TFLGuiSession.render().
- Reads session.engine; after each input calls session.after_input(), which
  handles completion and redraws.
- Publishes the keys valid on the current screen in session.key_actions;
  TFLGuiSession owns the window key bindings and dispatches through it.
- Shows session.save_status() in the footer of every trial screen.
- Uses gui/components/card.py, bind_dynamic_wraplength() from
  gui/components/page_helpers.py, and the test-taking styles in gui/theme.py.

Settings / parameters
---------------------
- Layout: header (trial number, live countdown on timed stages), block and
  run mode, progress bar, the stage content, then a footer with the
  keyboard hint and save status. The bar shows completed trials, not the
  trial in progress.
- Keys: A/B (and U where uncodable is allowed) answer choice stages; Enter
  views the stimulus, submits affect, confirms a perturbation, and closes
  the completion screen. Esc and F11 are handled by the session.
- COUNTDOWN_REFRESH_MS (250): countdown refresh period.
- COUNTDOWN_WARN_SECONDS (3): the countdown turns to the warning colour at
  or below this many seconds.

Edge cases
----------
- Invalid affect text shows "Please enter a whole number from 0 to 100",
  keeps the typed text selected, and stays on the stage.
- The countdown stops as soon as its label is destroyed or time runs out.
- Answer buttons do not take keyboard focus, so Space cannot press a button
  left focused from an earlier screen.
- A key that is not valid on the current screen does nothing.
- The completion screen lists the last five save problems, if any.

Known limitations
-----------------
- The screen is rebuilt on every stage change.
- Requires Tk; the CLI and the headless tests never import this module.
- The on-screen question wording is shorter than the reference prompts in
  frameworks/TFL/settings.py (the CLI uses those); stored answers and
  feedback sentences are identical.
- Native rendering, fonts, and DPI scaling are verified by hand on the
  target machine, not by the automated tests.

Examples
--------
- render_trial(session)
- session.key_actions["a"]()  # same as clicking A
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from gui.components.card import Card
from gui.components.page_helpers import bind_dynamic_wraplength

from . import settings
from .config import format_run_mode

COUNTDOWN_REFRESH_MS = 250
COUNTDOWN_WARN_SECONDS = 3

CHOICE_PROMPTS = {
    "prediction": ("Which interpretation do you predict?", ("A", "B")),
    "post_perturbation_probe": ("Which interpretation is most active immediately after the perturbation?",
                                ("A", "B", "U")),
    "behavioral_choice": ("Final behavioral choice", ("A", "B")),
    "content_probe": ("Which interpretation is most active in your mind right now?", ("A", "B", "U")),
}
SUBMITTERS = {
    "prediction": "submit_prediction",
    "post_perturbation_probe": "submit_post_perturbation_probe",
    "behavioral_choice": "submit_behavioral_choice",
    "content_probe": "submit_content_probe",
}


# ------------------------------------------------------------------ helpers
def _card(parent, title: str, body: Any, body_style: str = "CardMuted.TLabel") -> Card:
    card = Card(parent)
    card.pack(fill="x", pady=5)
    if title:
        ttk.Label(card, text=str(title), style="CardTitle.TLabel").pack(anchor="w")
    label = ttk.Label(card, text=str(body), style=body_style, justify="left")
    label.pack(anchor="w", fill="x", pady=(6 if title else 0, 0))
    bind_dynamic_wraplength(label, card, margin=36)
    return card


def _submit(session, method: Callable, value=None) -> None:
    accepted = method() if value is None else method(value)
    if accepted or session.engine.active_stage() != getattr(session, "rendered_stage", None):
        session.after_input()


def _action_button(session, parent, text: str, key_label: str, action: Callable) -> None:
    row = ttk.Frame(parent, style="Bg.TFrame")
    row.pack(fill="x", pady=(12, 0))
    ttk.Button(row, text=text, style="Accent.TButton", command=action, takefocus=False).pack(side="right")
    ttk.Label(row, text=f"Press {key_label}", style="Hint.TLabel").pack(side="right", padx=(0, 10))


def _options_pair(parent, trial: dict) -> None:
    pair = ttk.Frame(parent, style="Bg.TFrame")
    pair.pack(fill="x", pady=5)
    pair.grid_columnconfigure(0, weight=1, uniform="option")
    pair.grid_columnconfigure(1, weight=1, uniform="option")
    for column, (letter, key) in enumerate((("A", "interpretation_a"), ("B", "interpretation_b"))):
        card = Card(pair)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 5) if column == 0 else (5, 0))
        ttk.Label(card, text=letter, style="OptionKey.TLabel").pack(anchor="w")
        text = ttk.Label(card, text=trial[key], style="Option.TLabel", justify="left")
        text.pack(anchor="w", fill="x", pady=(4, 0))
        bind_dynamic_wraplength(text, card, margin=36)


def _choice_prompt(session, parent, stage: str) -> None:
    prompt, choices = CHOICE_PROMPTS[stage]
    method = getattr(session.engine, SUBMITTERS[stage])
    ttk.Label(parent, text=prompt, style="Prompt.TLabel").pack(anchor="w", pady=(14, 8))
    row = ttk.Frame(parent, style="Bg.TFrame")
    row.pack(anchor="w")
    for choice in choices:
        action = lambda value=choice: _submit(session, method, value)  # noqa: E731
        ttk.Button(row, text=choice, style="Choice.TButton", width=4,
                   command=action, takefocus=False).pack(side="left", padx=(0, 10))
        session.key_actions[choice.lower()] = action
    keys = " or ".join(choices)
    hint = f"Press {keys} on the keyboard, or click." + ("  U = uncodable." if "U" in choices else "")
    ttk.Label(parent, text=hint, style="Hint.TLabel").pack(anchor="w", pady=(8, 0))


def _affect_form(session, parent) -> None:
    ttk.Label(parent, text=settings.AFFECT_PROMPT.rstrip(": "), style="Prompt.TLabel").pack(anchor="w", pady=(14, 8))
    row = ttk.Frame(parent, style="Bg.TFrame")
    row.pack(anchor="w")
    entry_var = tk.StringVar(master=session.win)
    entry = ttk.Entry(row, textvariable=entry_var, width=6, font=("Segoe UI", 16))
    entry.pack(side="left")
    error = tk.StringVar(master=session.win)

    def submit() -> None:
        if session.engine.submit_affect(entry_var.get()):
            session.after_input()
        else:
            error.set(f"Please enter a whole number from {settings.AFFECT_MIN} to {settings.AFFECT_MAX}.")
            entry.selection_range(0, "end")

    ttk.Button(row, text="Continue", style="Accent.TButton", command=submit,
               takefocus=False).pack(side="left", padx=(10, 0))
    ttk.Label(parent, text="Type a whole number from 0 to 100, then press Enter.",
              style="Hint.TLabel").pack(anchor="w", pady=(8, 0))
    ttk.Label(parent, textvariable=error, style="CountdownLow.TLabel").pack(anchor="w", pady=(6, 0))
    session.key_actions["return"] = submit
    session.focus_target = entry


def _tick(session, label) -> None:
    try:
        if not label.winfo_exists():
            return
        remaining = session.engine.seconds_remaining()
        if remaining is None:
            return
        label.configure(text=f"{remaining} s",
                        style="CountdownLow.TLabel" if remaining <= COUNTDOWN_WARN_SECONDS else "Countdown.TLabel")
        if remaining > 0:
            session.win.after(COUNTDOWN_REFRESH_MS, lambda: _tick(session, label))
    except tk.TclError:
        return


# ------------------------------------------------------------------ screens
def _render_completion(session, root) -> None:
    engine = session.engine
    ttk.Label(root, text="Session complete", style="Title.TLabel").pack(anchor="w", pady=(0, 14))
    if engine.last_feedback:
        _card(root, "Final trial feedback", engine.last_feedback)
    _card(root, "Session saved", session.completion_message)
    if engine.save_errors:
        _card(root, "Save problems", "\n".join(engine.save_errors[-5:]))
    _action_button(session, root, "Close", "Enter", session.close_windows)
    session.key_actions["return"] = session.close_windows


def _render_header(session, root, stage: str) -> None:
    engine, trial = session.engine, session.engine.current_trial
    header = ttk.Frame(root, style="Bg.TFrame")
    header.pack(fill="x")
    ttk.Label(header, text=f"Trial {engine.progress_label().replace(' / ', ' of ')}",
              style="Title.TLabel").pack(side="left")
    if engine.seconds_remaining() is not None:
        countdown = ttk.Label(header, style="Countdown.TLabel")
        countdown.pack(side="right")
        _tick(session, countdown)
    ttk.Label(root, text=f"Block: {trial['block']}  \u00b7  {format_run_mode(trial['run_mode'])}",
              style="Muted.TLabel").pack(anchor="w", pady=(2, 6))
    progress = ttk.Progressbar(root, style="Trial.Horizontal.TProgressbar", mode="determinate",
                               maximum=max(1, len(engine.trials)), value=len(engine.rows))
    progress.pack(fill="x", pady=(0, 14))


def _render_stage(session, content, stage: str) -> None:
    engine, trial = session.engine, session.engine.current_trial
    if stage == "cue":
        if engine.last_feedback:
            _card(content, "Previous trial", engine.last_feedback)
        _card(content, "Context", trial["cue"])
        _card(content, "Prior", f"Interpretation {trial['prior_instruction']} is more likely.")
        view = lambda: _submit(session, engine.continue_cue)  # noqa: E731
        _action_button(session, content, "View Stimulus", "Enter", view)
        session.key_actions["return"] = view
        return
    _card(content, "", trial["ambiguous_text"], body_style="Stimulus.TLabel")
    _options_pair(content, trial)
    if stage == "affect":
        _affect_form(session, content)
    elif stage == "perturbation":
        _card(content, "Perturbation step", engine.perturbation_instruction())
        done = lambda: _submit(session, engine.continue_perturbation)  # noqa: E731
        _action_button(session, content, "Completed", "Enter", done)
        session.key_actions["return"] = done
    elif stage in CHOICE_PROMPTS:
        if stage == "content_probe" and engine.current_feedback:
            _card(content, "Feedback", engine.current_feedback)
        _choice_prompt(session, content, stage)
    else:
        raise RuntimeError(f"Unexpected TFL stage: {stage}")


def render_trial(session: Any) -> None:
    if not session.window_exists():
        return
    session.clear()
    session.key_actions = {}
    session.focus_target = session.win
    stage = session.engine.active_stage()
    session.rendered_stage = stage
    root = ttk.Frame(session.win, style="Bg.TFrame", padding=(28, 22))
    root.pack(fill="both", expand=True)
    if stage == "completion":
        _render_completion(session, root)
    else:
        _render_header(session, root, stage)
        content = ttk.Frame(root, style="Bg.TFrame")
        content.pack(fill="both", expand=True)
        _render_stage(session, content, stage)
        footer = ttk.Frame(root, style="Bg.TFrame")
        footer.pack(fill="x", side="bottom", pady=(12, 0))
        ttk.Label(footer, text="Esc: stop run  \u00b7  F11: full screen", style="Hint.TLabel").pack(side="left")
        ttk.Label(footer, text=session.save_status(), style="Hint.TLabel").pack(side="right")
    try:
        session.focus_target.focus_set()
    except (tk.TclError, AttributeError):
        pass


__all__ = ["render_trial", "COUNTDOWN_WARN_SECONDS"]
