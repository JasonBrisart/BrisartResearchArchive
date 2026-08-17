"""
TFLGuiSession — thin adapter wiring TFLSessionEngine to a live Tk window.

Startup flow:
    1. start() creates the Toplevel window and immediately shows the
       pre-session options screen (options_screen.render_options).
    2. The user toggles Extra Stimuli / Perturbations / Probes /
       Delayed Reentry, then clicks "Start Session".
    3. begin_session() builds stimuli/trials/engine from the
       (possibly edited) config and starts the first trial.

All trial logic lives in engine.py and is fully covered by headless
tests (see tests/test_merged.py, driven through app/headless.py).
"""
from __future__ import annotations

import tkinter as tk

from engine.timing import MonotonicTimer
from . import analysis
from .config import apply_default_options
from .engine import TFLSessionEngine
from .options_screen import render_options
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

        # Config is built immediately so the options screen has real
        # default values to show. Stimuli/trials/engine are only built
        # in begin_session(), once the user confirms options on the
        # pre-session options screen. This is the key fix: previously
        # stimuli/trials/engine were built eagerly here and start()
        # jumped straight to the trial screen, so options_screen.py's
        # render_options() was never actually called by anything.
        self.config = apply_default_options()
        self.option_vars: dict = {}

        self.stimuli: list[dict] = []
        self.trials: list[dict] = []

        self.win: tk.Toplevel | None = None
        self.engine: TFLSessionEngine | None = None
        self.parent_root = None
        self.created_parent_root = False

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def start(self):
        parent = self.app
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
            self.parent_root = parent
            self.created_parent_root = True

        # Previously participant_id was a constructor parameter that
        # nothing ever actually supplied - prompting here (optional -
        # blank/cancelled is fine) is what actually makes the field
        # usable.
        if not self.participant_id:
            self.participant_id = self._prompt_for_participant_id(parent)

        self.win = tk.Toplevel(parent)
        self.win.title("TFL GUI Assay")
        self.win.geometry("980x720")
        self.win.minsize(900, 650)
        self.win.configure(bg=COLORS.get("bg", "#070b14"))
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)

        # Force the window to the front. Without this, some window
        # managers (and Toplevel windows created from a withdrawn Tk
        # root) leave the new window behind the main app window or
        # never actually grab focus, which looks like nothing opened.
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(200, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()

        # Show the pre-session options screen first. The engine is not
        # built until begin_session() runs, which happens when the user
        # clicks "Start Session" on that screen.
        self._render_options_safely()

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

    def _render_options_safely(self) -> None:
        # Wrapped in try/except so a broken options screen shows a real
        # error instead of silently leaving a blank/invisible window -
        # this was the most likely reason "Run TFL" appeared to do
        # nothing.
        try:
            render_options(self)
        except Exception as exc:
            self.log(f"TFL options screen failed to render: {type(exc).__name__}: {exc}")
            import traceback
            traceback.print_exc()
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "TFL Options Failed",
                    f"The TFL options screen could not be displayed.\n\n{type(exc).__name__}: {exc}",
                    parent=self.win,
                )
            except tk.TclError:
                pass

    def begin_session(self) -> None:
        """
        Called by the options screen once the user clicks Start
        Session. Builds stimuli/trials against the (possibly edited)
        config, then builds and starts the engine.
        """
        try:
            self.stimuli = apply_stimulus_limit(load_stimuli(), self.config)
            self.trials = build_trials(self.config, self.stimuli)
        except Exception as exc:
            self.log(f"TFL could not build trials: {type(exc).__name__}: {exc}")
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "TFL Setup Failed",
                    f"TFL could not build stimuli/trials from the current options.\n\n{type(exc).__name__}: {exc}",
                    parent=self.win,
                )
            except tk.TclError:
                pass
            return

        if not self.stimuli or not self.trials:
            self.log("TFL cannot start: no stimuli or trials were generated.")
            return

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

    def render_options(self) -> None:
        self._render_options_safely()

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