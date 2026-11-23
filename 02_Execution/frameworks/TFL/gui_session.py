"""
File: frameworks/TFL/gui_session.py

Purpose
-------
Provide TFLGuiSession, which connects the TFL engine to a Tk window:
options screen, run setup, per-answer saving, keyboard input, full screen,
completion, cancellation, and the hand-off back to the Archive window.

Communication / relationships
-----------------------------
- Created by controllers/system_controller.start_tfl(), which passes the
  Archive window; the controller also calls end_run() when the Archive
  closes mid-run. The session reaches the host only through that app
  object (log, tfl_output_dir, show_page, analyze_tfl), never through
  imports of config/ or controllers/.
- Renders through frameworks/TFL/gui_options.render_options() and
  frameworks/TFL/gui_screens.render_trial().
- Saves through frameworks/TFL/output.SessionWriter; writer.save is the
  engine's on_progress hook, so the CSV is rewritten after every answer.
- After a finished run, shows the Results page and analyzes that run's
  file through app.show_page() and app.analyze_tfl(path).
- Logs through app.log().
- Owns the window's <KeyPress>, <KeyRelease>, and <FocusOut> bindings.
  Each screen publishes its valid keys in key_actions; handle_key() runs
  the matching action.

Settings / parameters
---------------------
- TFLGuiSession(app): app is required.
- Output folder: app.tfl_output_dir(), the live Output Directory setting.
- Window 1000x700, minimum 800x600; the options screen scrolls
  vertically.
- Keys: Esc stops the run (with the usual confirmation); F11 toggles full
  screen; every other key is looked up in key_actions, normalized to lower
  case ("a", "b", "u", "return"; the keypad Enter counts as "return").

Edge cases
----------
- Completion is handled once, in after_input(), never during rendering.
- Cancelling or closing the window ends the run; every answer already
  given stays in that run's CSV, including the partly answered trial
  (marked in_progress).
- A failed save is logged immediately and shown in the screen footer; the
  run continues, and the next successful save rewrites the whole session.
- A key held down acts once: further presses of the same key are ignored
  until it is released, so keyboard auto-repeat cannot answer the next
  question. Losing window focus forgets held keys. Esc and F11 are never
  held-key filtered.
- A setup failure (for example an unwritable folder) shows an error dialog
  and stays on the options screen.

Known limitations
-----------------
- Native Tk rendering is not exercised by the automated tests; wiring is
  tested with widget doubles (tests/gui_doubles_check.py).
- On X11, auto-repeat sends release/press pairs, so the held-key guard only
  suppresses repeats on Windows and macOS.

Examples
--------
- TFLGuiSession(app).start()
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from gui.theme import COLORS

from .config import get_default_config, resolve_run_config
from .engine import TFLSessionEngine
from .gui_options import render_options
from .gui_screens import render_trial
from .output import SessionWriter
from .stimuli import apply_stimulus_limit, load_stimuli
from .timing import MonotonicTimer
from .trial_builder import build_trials


class TFLGuiSession:
    def __init__(self, app):
        self.app = app
        self.config = get_default_config()
        self.option_vars: dict = {}
        self.option_widgets: dict = {}
        self.win: tk.Toplevel | None = None
        self.engine: TFLSessionEngine | None = None
        self.writer: SessionWriter | None = None
        self.completion_message = ""
        self.finished = False
        self.rendered_stage = None
        self._reported_errors = 0
        self.key_actions: dict = {}
        self.focus_target = None
        self._held_keys: set[str] = set()

    # ---------------------------------------------------------- lifecycle
    def start(self) -> None:
        self.win = tk.Toplevel(self.app)
        self.win.title("Temporal Feedback Loop")
        self.win.geometry("1000x700")
        self.win.minsize(800, 600)
        self.win.configure(bg=COLORS["bg"])
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.bind("<KeyPress>", self.handle_key)
        self.win.bind("<KeyRelease>", self.release_key)
        self.win.bind("<FocusOut>", self.forget_held_keys)
        self.win.lift()
        self.win.focus_force()
        render_options(self)

    def begin_session(self) -> None:
        try:
            run = resolve_run_config(self.config)
            trials = build_trials(run, apply_stimulus_limit(load_stimuli(), run))
            self.writer = SessionWriter(self.app.tfl_output_dir(), label=run["session_label"])
        except Exception as exc:
            self._error("TFL Setup Failed", f"TFL could not prepare this run.\n\n{type(exc).__name__}: {exc}")
            return
        self.engine = TFLSessionEngine(
            run, trials,
            MonotonicTimer(schedule_fn=self.win.after, cancel_fn=self.win.after_cancel),
            on_progress=self.writer.save,
            on_stage_advanced=self.after_input,
        )
        self.log(f"TFL run started ({run['run_mode']}, seed {run['random_seed']}): {self.writer.path}")
        self.engine.start()
        self.render()

    def render(self) -> None:
        render_trial(self)

    def save_status(self) -> str:
        if self.writer is None or self.engine is None:
            return ""
        if self.engine.last_save_error:
            return f"Last save failed. Saving to {self.writer.path.name}"
        return f"Saved after every answer to {self.writer.path.name}"

    def after_input(self) -> None:
        engine = self.engine
        if engine is not None:
            for error in engine.save_errors[self._reported_errors:]:
                self.log(f"TFL save problem: {error}")
            self._reported_errors = len(engine.save_errors)
            if engine.completed and not self.finished:
                self._finish()
        self.render()

    def _finish(self) -> None:
        self.finished = True
        path = self.writer.close()
        self.completion_message = f"Saved {self.writer.rows_saved} trials to:\n{path}"
        self.log(f"TFL run complete: {self.writer.rows_saved} trials saved to {path.name}")
        try:
            self.app.show_page("Results")
            self.app.analyze_tfl(path)
        except (AttributeError, tk.TclError) as exc:
            self.log(f"Could not show the results for this run: {exc}")

    def end_run(self, reason: str) -> None:
        """Stop an unfinished run. Answers already given are on disk."""
        if self.engine is not None and not self.engine.completed and not self.engine.cancelled:
            self.engine.cancel()
            path = self.writer.close()
            self.log(f"TFL run ended ({reason}) after {len(self.engine.rows)} complete trial(s); kept in {path.name}")

    # ---------------------------------------------------------- keyboard
    @staticmethod
    def key_name(event) -> str:
        keysym = str(getattr(event, "keysym", "") or "")
        if keysym == "KP_Enter":
            return "return"
        return keysym.lower()

    def handle_key(self, event):
        key = self.key_name(event)
        if key == "escape":
            self.cancel()
            return "break"
        if key == "f11":
            self.toggle_fullscreen()
            return "break"
        action = self.key_actions.get(key)
        if action is None or key in self._held_keys:
            return None
        self._held_keys.add(key)
        action()
        return "break"

    def release_key(self, event) -> None:
        self._held_keys.discard(self.key_name(event))

    def forget_held_keys(self, event=None) -> None:
        if event is None or getattr(event, "widget", None) is self.win:
            self._held_keys.clear()

    def toggle_fullscreen(self) -> None:
        if not self.window_exists():
            return
        try:
            self.win.attributes("-fullscreen", not bool(self.win.attributes("-fullscreen")))
        except tk.TclError:
            pass

    # ---------------------------------------------------------- windows
    def window_exists(self) -> bool:
        try:
            return self.win is not None and bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def clear(self) -> None:
        self.key_actions = {}
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
        if self.engine is not None and not self.engine.completed:
            prompt = (
                "Stop this TFL run?\n\nEvery answer given so far is already saved in:\n"
                f"{self.writer.path}"
            )
            try:
                if not messagebox.askyesno("Stop TFL Run", prompt, parent=self.win):
                    return
            except tk.TclError:
                pass
            self.end_run("cancelled")
        self.close_windows()

    def close_windows(self) -> None:
        if self.window_exists():
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None

    def _error(self, title: str, message: str) -> None:
        self.log(message.splitlines()[0])
        try:
            messagebox.showerror(title, message, parent=self.win)
        except tk.TclError:
            pass

    def log(self, text: str) -> None:
        self.app.log(text)


__all__ = ["TFLGuiSession"]

