"""
TFLGuiSession — thin adapter wiring TFLSessionEngine to a live Tk window.

This class intentionally owns almost no logic. Its only jobs are:
    1. build the engine + config + trials
    2. create/destroy the Tk Toplevel
    3. bind the engine's timer to Tk's .after()/.after_cancel()
    4. ask screen.render_trial() to redraw whenever engine state changes

All trial logic lives in engine.py and is fully covered by headless
tests (see tests/test_merged.py, driven through app/headless.py).
"""
from __future__ import annotations

import tkinter as tk

from engine.timing import MonotonicTimer
from . import analysis
from .config import apply_default_options
from .engine import TFLSessionEngine
from .screen import render_trial
from .stimuli import apply_stimulus_limit, load_stimuli
from .trial_builder import build_trials

try:
    from gui.theme import COLORS
except ImportError:
    COLORS = {"bg": "#070b14"}

# How often (in completed trials) the in-progress run is checkpointed to
# disk. Previously the only save() call happened once, at the very end
# of a session, so a crash or forced window close silently lost every
# trial collected up to that point.
AUTOSAVE_INTERVAL_TRIALS = 5


class TFLGuiSession:
    """GUI-native TFL runner. Delegates all state to TFLSessionEngine."""

    def __init__(self, app=None, participant_id: str = ""):
        self.app = app
        self.participant_id = str(participant_id).strip()
        self.config = apply_default_options()
        self.stimuli = apply_stimulus_limit(load_stimuli(), self.config)
        self.trials = build_trials(self.config, self.stimuli)
        self.win: tk.Toplevel | None = None
        self.engine: TFLSessionEngine | None = None
        self.parent_root = None
        self.created_parent_root = False

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def start(self):
        if not self.stimuli or not self.trials:
            self.log("TFL cannot start: no stimuli or trials were generated.")
            return
        parent = self.app
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
            self.parent_root = parent
            self.created_parent_root = True

        # Previously participant_id was a constructor parameter that
        # nothing ever actually supplied - FrameworkService always
        # created runners with just `runner_type(self.app)`, so every
        # row in every CSV had a permanently blank participant_id even
        # though the engine and schema fully support it. Prompting here
        # (optional - blank/cancelled is fine) is what actually makes
        # the field usable.
        if not self.participant_id:
            self.participant_id = self._prompt_for_participant_id(parent)

        self.win = tk.Toplevel(parent)
        self.win.title("TFL GUI Assay")
        self.win.geometry("980x720")
        self.win.minsize(900, 650)
        self.win.configure(bg=COLORS.get("bg", "#070b14"))
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)

        self.engine = TFLSessionEngine(
            self.config,
            self.trials,
            MonotonicTimer(
                schedule_fn=lambda ms, cb: self.win.after(ms, cb),
                cancel_fn=lambda handle: self.win.after_cancel(handle),
            ),
            participant_id=self.participant_id,
            on_trial_recorded=self._autosave_if_due,
            # Without this, a prediction/behavioral-choice timeout moves
            # the engine's internal stage forward but the window keeps
            # showing the old stage's buttons - which then silently do
            # nothing when clicked, since the engine has already moved
            # on. This is what makes the screen re-render immediately
            # when a 12-second window expires unattended.
            on_stage_advanced=self.render,
        )
        self.log(f"TFL session started: {self.engine.session_id}")
        self.engine.start_trial()
        self.render()
        if self.app is None:
            parent.mainloop()

    def _prompt_for_participant_id(self, dialog_parent) -> str:
        """
        Optional participant ID prompt. Returns "" (not mandatory) if
        the user cancels, closes the dialog, or leaves it blank - a
        blank participant_id is a perfectly valid, pre-existing state
        that the engine and analysis layer already handle correctly.
        """
        try:
            from tkinter import simpledialog
            entered = simpledialog.askstring(
                "TFL Participant",
                "Participant ID (optional - leave blank to skip):",
                parent=dialog_parent,
            )
        except tk.TclError:
            return ""
        return str(entered or "").strip()

    def render(self) -> None:
        render_trial(self)

    def _autosave_if_due(self, rows: list[dict]) -> None:
        """Checkpoint to disk every AUTOSAVE_INTERVAL_TRIALS completed trials."""
        if self.engine is None or not rows:
            return
        if len(rows) % AUTOSAVE_INTERVAL_TRIALS != 0:
            return
        try:
            path = analysis.autosave_rows(rows, self.engine.session_id)
        except Exception as exc:
            self.log(f"Autosave failed at {len(rows)} trials: {type(exc).__name__}: {exc}")
            return
        self.log(f"Autosaved {len(rows)} trials to {path.name}")

    def window_exists(self) -> bool:
        if self.win is None:
            return False
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def clear(self) -> None:
        if not self.window_exists():
            return
        for child in self.win.winfo_children():
            try:
                child.destroy()
            except tk.TclError:
                pass

    def cancel(self) -> None:
        if not self.window_exists():
            return
        completed_trial_count = len(self.engine.rows) if self.engine is not None else 0
        if completed_trial_count > 0:
            cancel_prompt = (
                "Cancel this TFL GUI run?\n\n"
                f"{completed_trial_count} completed trial(s) were already autosaved and will remain on disk, "
                "but no final output file will be produced for this run."
            )
        else:
            cancel_prompt = "Cancel this TFL GUI run?\n\nNo trials have been completed yet."
        try:
            from tkinter import messagebox
            should_cancel = messagebox.askyesno("Cancel TFL Run", cancel_prompt, parent=self.win)
        except tk.TclError:
            should_cancel = True
        if not should_cancel:
            return
        if self.engine is not None:
            self.engine.cancel()
        self.log("TFL GUI assay cancelled.")
        self.close_windows()

    def close_windows(self) -> None:
        if self.window_exists():
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None
        if self.created_parent_root and self.parent_root is not None:
            try:
                if self.parent_root.winfo_exists():
                    self.parent_root.destroy()
            except tk.TclError:
                pass
            self.parent_root = None
            self.created_parent_root = False

    def after_finish_in_host_app(self) -> None:
        if self.app is None:
            return
        try:
            if not self.app.winfo_exists():
                return
        except (AttributeError, tk.TclError):
            return
        if hasattr(self.app, "show_page"):
            try:
                self.app.show_page("Results")
            except (AttributeError, tk.TclError) as exc:
                self.log(f"Could not open Results page: {exc}")
        if hasattr(self.app, "analyze_tfl"):
            try:
                self.app.analyze_tfl()
            except (AttributeError, tk.TclError) as exc:
                self.log(f"Could not start TFL analysis: {exc}")

    def log(self, text: str) -> None:
        if self.app is not None and hasattr(self.app, "log"):
            try:
                self.app.log(text)
                return
            except (AttributeError, tk.TclError):
                pass
        print(text)


__all__ = ["TFLGuiSession"]
