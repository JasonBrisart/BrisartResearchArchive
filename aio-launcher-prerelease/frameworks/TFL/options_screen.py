"""
File: frameworks/TFL/options_screen.py

Purpose:
Render the pre-session Run Options screen, where the user toggles Extra
Stimuli, Perturbations, Probes, and Delayed Reentry before a TFL run.

Communication / relationships:
- render_options(session) is called by frameworks/TFL/session_gui.py.
- Writes toggle values into session.config.
- Start Session calls session.begin_session(); Cancel calls
  session.cancel().
- Restore Defaults uses frameworks/TFL/config.apply_default_options().
- Uses COLORS and FONT_HEAD from gui/theme.py and Card from
  gui/widgets/card.py, with local fallbacks.

Settings / parameters:
- TOGGLE_DEFINITIONS: (config key, title, description) for each toggle.
- The mode label reads "Default TFL" when all toggles match the
  defaults, otherwise "Modified TFL".

Edge cases:
- Returns silently if the session window is missing or destroyed.
- Rebuilds the screen from scratch on every call.
- Falls back to built-in colors and a plain Card when the GUI modules
  cannot be imported.
- A TclError while reading a toggle leaves that config key unchanged.

Known limitations:
- Only the four toggles are editable; timing, intervals, and the seed
  are set in frameworks/TFL/settings.py.
- Label wraplengths are fixed at 760 and 860 pixels.

Examples:
- render_options(session)
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Any
from .config import apply_default_options
try:
    from gui.theme import COLORS, FONT_HEAD
except ImportError:
    COLORS = {
        "bg": "#070b14",
        "panel": "#0c1320",
        "text": "#eef4fb",
        "muted": "#8a96aa",
        "accent": "#14b8a6",
    }
    FONT_HEAD = ("Segoe UI", 13, "bold")
try:
    from gui.widgets.card import Card
except ImportError:
    class Card(ttk.Frame):
        def __init__(self, parent, *args, **kwargs):
            kwargs.setdefault("style", "Card.TFrame")
            kwargs.setdefault("padding", (16, 14))
            super().__init__(parent, *args, **kwargs)

TOGGLE_DEFINITIONS = [
    (
        "enable_extra_stimuli",
        "Extra Stimuli",
        "Use the full stimulus library instead of the first 20 baseline items.",
    ),
    (
        "enable_perturbations",
        "Perturbations",
        "Insert brief perturbation steps on the configured trial interval.",
    ),
    (
        "enable_probes",
        "Probes",
        "Ask which interpretation feels most active on probe-interval trials.",
    ),
    (
        "enable_delayed_reentry",
        "Delayed Reentry",
        "Re-present an earlier trial's stimulus later in the run to test recurrence.",
    ),
]


def _current_mode_label(config: dict) -> str:
    is_default = (
        config.get("enable_extra_stimuli", False) is False
        and config.get("enable_perturbations", False) is False
        and config.get("enable_probes", True) is True
        and config.get("enable_delayed_reentry", True) is True
    )
    return "Default TFL" if is_default else "Modified TFL"


def _build_toggle_row(parent, session, key: str, title: str, description: str, row: int) -> None:
    initial_value = bool(session.config.get(key, False))
    variable = tk.BooleanVar(master=session.win, value=initial_value)
    session.option_vars[key] = variable
    ttk.Checkbutton(
        parent,
        text=title,
        variable=variable,
    ).grid(row=row, column=0, sticky="w", pady=(10, 0))
    ttk.Label(
        parent,
        text=description,
        style="CardMuted.TLabel",
        wraplength=760,
        justify="left",
    ).grid(row=row + 1, column=0, sticky="w", pady=(2, 0))


def _apply_restore_defaults(session) -> None:
    defaults = apply_default_options()
    session.config.update(defaults)
    for key, variable in session.option_vars.items():
        variable.set(bool(session.config.get(key, False)))
    render_options(session)


def _apply_start(session) -> None:
    for key, variable in session.option_vars.items():
        try:
            session.config[key] = bool(variable.get())
        except tk.TclError:
            pass
    session.begin_session()


def render_options(session: Any) -> None:
    """
    Render the pre-session options screen for a TFLGuiSession.
    Safe to call repeatedly; always rebuilds from scratch.
    """
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
    ttk.Label(
        root,
        text="TFL Run Options",
        style="Title.TLabel",
    ).pack(anchor="w")
    ttk.Label(
        root,
        text=(
            f"Current mode: {_current_mode_label(session.config)}\n"
            "Adjust any setting below, or start with the current configuration."
        ),
        style="Muted.TLabel",
        wraplength=860,
        justify="left",
    ).pack(anchor="w", pady=(4, 18))
    card = Card(root)
    card.pack(fill="x", pady=(0, 16))
    card.grid_columnconfigure(0, weight=1)
    for index, (key, title, description) in enumerate(TOGGLE_DEFINITIONS):
        row = index * 2
        _build_toggle_row(card, session, key, title, description, row)
    actions = ttk.Frame(root, style="Bg.TFrame")
    actions.pack(fill="x", pady=(4, 0))
    ttk.Button(
        actions,
        text="Restore Defaults",
        command=lambda: _apply_restore_defaults(session),
    ).pack(side="left")
    ttk.Button(
        actions,
        text="Cancel",
        command=session.cancel,
    ).pack(side="left", padx=(8, 0))
    ttk.Button(
        actions,
        text="Start Session",
        style="Accent.TButton",
        command=lambda: _apply_start(session),
    ).pack(side="right")


__all__ = ["render_options", "TOGGLE_DEFINITIONS"]
