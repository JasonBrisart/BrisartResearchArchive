"""
File: frameworks/TFL/gui_options.py

Purpose
-------
Render the pre-run TFL options screen. Every control is generated from
frameworks/TFL/config.OPTION_SPECS, so the GUI offers exactly the options the CLI
offers, with the same validation.

Communication / relationships
-----------------------------
- render_options(session) is called by frameworks/TFL/gui_session.py.
- Writes values into session.config through config.set_option();
  Start Experiment calls session.begin_session(); Cancel calls
  session.cancel().
- Uses gui/components/card.py and gui/theme.py styles.

Settings / parameters
---------------------
- toggle options: Checkbutton. int options: Spinbox within the spec's
  limits. blocks: one Checkbutton per block. seed and text: Entry.
- Options whose "requires" toggle is off are disabled until it is on.
- Buttons: Restore Default Settings, Cancel, Start Experiment.

Edge cases
----------
- Every change re-reads all controls and refreshes the Current Settings
  panel, including the Default TFL / Modified TFL label.
- Invalid values are listed under the buttons and Start Experiment
  does not start until they are fixed; nothing is silently clamped.
- Restore Default Settings keeps the session label.

Known limitations
-----------------
- The option list does not scroll. The TFL window opens at 1100x900 so
  every option is visible; on screens shorter than that, maximize the
  window. Native layout has not been checked on a real display.

Examples
--------
- render_options(session)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from gui.components.card import Card

from . import settings
from .config import OPTION_SPECS, default_mode_description, describe_current_options, restore_defaults, set_option


def _read_controls(session) -> list[str]:
    errors = []
    for spec in OPTION_SPECS:
        variable = session.option_vars.get(spec.key)
        if variable is None:
            continue
        try:
            raw = [b for b, v in variable.items() if v.get()] if spec.kind == "blocks" else variable.get()
        except tk.TclError:
            continue
        ok, message = set_option(session.config, spec.key, raw)
        if not ok:
            errors.append(message)
    return errors


def _refresh(session) -> list[str]:
    errors = _read_controls(session)
    try:
        session.summary_var.set("\n".join(describe_current_options(session.config)))
        session.error_var.set("\n".join(errors))
        for spec in OPTION_SPECS:
            if spec.requires:
                enabled = bool(session.config.get(spec.requires))
                for widget in session.option_widgets.get(spec.key, []):
                    widget.configure(state="normal" if enabled else "disabled")
    except (tk.TclError, AttributeError):
        pass
    return errors


def _restore(session) -> None:
    session.config = restore_defaults(session.config)
    render_options(session)


def _start(session) -> None:
    if not _refresh(session):
        session.begin_session()


def _build_control(session, parent, spec, row: int) -> None:
    value = session.config.get(spec.key)
    on_change = lambda *_args: _refresh(session)  # noqa: E731
    widgets = []
    if spec.kind == "toggle":
        variable = tk.BooleanVar(master=session.win, value=bool(value))
        widgets.append(ttk.Checkbutton(parent, text=spec.label, variable=variable, command=on_change))
        widgets[0].grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
    else:
        ttk.Label(parent, text=spec.label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=(8, 0))
        if spec.kind == "blocks":
            variable = {block: tk.BooleanVar(master=session.win, value=block in value) for block in settings.BLOCKS}
            frame = ttk.Frame(parent, style="Card.TFrame")
            frame.grid(row=row, column=1, sticky="w", pady=(8, 0))
            for block in settings.BLOCKS:
                ttk.Checkbutton(frame, text=block, variable=variable[block], command=on_change).pack(side="left", padx=(0, 10))
        else:
            variable = tk.StringVar(master=session.win, value=str(value))
            if spec.kind == "int":
                widget = ttk.Spinbox(parent, from_=spec.minimum, to=spec.maximum, width=8,
                                     textvariable=variable, command=on_change)
            else:
                widget = ttk.Entry(parent, width=22, textvariable=variable)
            widget.grid(row=row, column=1, sticky="w", pady=(8, 0))
            widget.bind("<FocusOut>", on_change, add="+")
            widget.bind("<KeyRelease>", on_change, add="+")
            widgets.append(widget)
    ttk.Label(parent, text=spec.description, style="CardMuted.TLabel", wraplength=480,
              justify="left").grid(row=row + 1, column=0, columnspan=2, sticky="w")
    session.option_vars[spec.key] = variable
    session.option_widgets[spec.key] = widgets


def render_options(session: Any) -> None:
    if not session.window_exists():
        return
    session.clear()
    session.option_vars, session.option_widgets = {}, {}
    root = ttk.Frame(session.win, style="Bg.TFrame", padding=18)
    root.pack(fill="both", expand=True)
    ttk.Label(root, text=settings.VERSION_LABEL, style="Title.TLabel").pack(anchor="w")
    ttk.Label(root, text="Default settings: " + " \u00b7 ".join(default_mode_description()),
              style="Muted.TLabel", wraplength=1000, justify="left").pack(anchor="w", pady=(4, 10))

    body = ttk.Frame(root, style="Bg.TFrame")
    body.pack(fill="both", expand=True)
    body.grid_columnconfigure(0, weight=3)
    body.grid_columnconfigure(1, weight=2)
    options = Card(body)
    options.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    ttk.Label(options, text="Run Options", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
    for index, spec in enumerate(OPTION_SPECS):
        _build_control(session, options, spec, 1 + index * 2)

    summary = Card(body)
    summary.grid(row=0, column=1, sticky="nsew")
    ttk.Label(summary, text="Current Settings", style="CardTitle.TLabel").pack(anchor="w")
    session.summary_var = tk.StringVar(master=session.win)
    ttk.Label(summary, textvariable=session.summary_var, style="CardMuted.TLabel", justify="left").pack(anchor="w", pady=(8, 0))

    actions = ttk.Frame(root, style="Bg.TFrame")
    actions.pack(fill="x", pady=(12, 0))
    ttk.Button(actions, text="Restore Default Settings", command=lambda: _restore(session)).pack(side="left")
    ttk.Button(actions, text="Cancel", command=session.cancel).pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Start Experiment", style="Accent.TButton", command=lambda: _start(session)).pack(side="right")
    session.error_var = tk.StringVar(master=session.win)
    ttk.Label(root, textvariable=session.error_var, style="Muted.TLabel", justify="left").pack(anchor="w", pady=(8, 0))
    _refresh(session)


__all__ = ["render_options"]
