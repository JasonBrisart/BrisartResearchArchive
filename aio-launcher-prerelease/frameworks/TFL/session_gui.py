"""
File: frameworks/TFL/session_gui.py

Purpose
-------
Provide TFLGuiSession, the adapter that connects the shared TFL engine
to a Tk window: options screen, run construction, per-trial saving,
completion, cancellation, and hand-off back to the host app.

Communication / relationships
-----------------------------
- Launched by services/framework_service.py from FRAMEWORK_METADATA.
- Renders through options_screen.render_options() and
  screen.render_trial().
- Saves through output.SessionWriter (one flushed row per trial).
- Logs through app.log(); after completion opens Results and runs
  app.analyze_tfl().

Settings / parameters
---------------------
- TFLGuiSession(app=None, participant_id=""); participant_id is accepted
  for launcher compatibility and not recorded (the reference has no
  participant field).
- Output folder: the host's live Output Directory setting when an app is
  present, otherwise the saved setting.
- Window 980x720, minimum 900x650.

Edge cases
----------
- Completion is handled once, in after_input() / the timeout hook, never
  inside rendering.
- Cancelling keeps every completed trial in the session file and leaves
  tfl_output.csv untouched.
- With app=None a hidden Tk root is created and the session runs its own
  mainloop.

Known limitations
-----------------
- Native Tk rendering is not exercised by the automated tests.

Examples
--------
- TFLGuiSession(app).start()
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from engine.timing import MonotonicTimer

from .config import apply_default_options, update_run_mode
from .engine import TFLSessionEngine
from .options_screen import render_options
from .output import SessionWriter
from .screen import render_trial
from .stimuli import apply_stimulus_limit, load_stimuli
from .trial_builder import build_trials

try:
    from gui.theme import COLORS
except ImportError:
    COLORS = {"bg": "#070b14"}


class TFLGuiSession:
    def __init__(self, app=None, participant_id: str = ""):
        self.app = app
        self.participant_id = str(participant_id).strip()
        self.config = apply_default_options()
        self.option_vars: dict = {}
        self.win: tk.Toplevel | None = None
        self.engine: TFLSessionEngine | None = None
        self.writer: SessionWriter | None = None
        self.completion_message = ""
        self.finished = False
        self.parent_root = None
        self.created_parent_root = False
        self.rendered_stage = None

    # ---------------------------------------------------------- lifecycle
    def start(self) -> None:
        parent = self.app
        if parent is None:
            parent = tk.Tk()
            parent.withdraw()
            self.parent_root = parent
            self.created_parent_root = True
        self.win = tk.Toplevel(parent)
        self.win.title("Temporal Feedback Loop")
        self.win.geometry("980x720")
        self.win.minsize(900, 650)
        self.win.configure(bg=COLORS.get("bg", "#070b14"))
        self.win.protocol("WM_DELETE_WINDOW", self.cancel)
        self.win.lift()
        self.win.attributes("-topmost", True)
        self.win.after(200, lambda: self.win.attributes("-topmost", False))
        self.win.focus_force()
        try:
            render_options(self)
        except Exception as exc:
            self._error("TFL Options Failed", f"The TFL options screen could not be displayed.\n\n{type(exc).__name__}: {exc}")
        if self.app is None:
            parent.mainloop()

    def _output_dir(self):
        from config.runtime import get_framework_output_dir
        settings = self.app._collect_settings() if hasattr(self.app, "_collect_settings") else None
        return get_framework_output_dir("TFL", settings)

    def begin_session(self) -> None:
        update_run_mode(self.config)
        try:
            stimuli = apply_stimulus_limit(load_stimuli(), self.config)
            trials = build_trials(self.config, stimuli)
            self.writer = SessionWriter(self._output_dir())
        except Exception as exc:
            self._error("TFL Setup Failed", f"TFL could not prepare this run.\n\n{type(exc).__name__}: {exc}")
            return
        self.engine = TFLSessionEngine(
            self.config,
            trials,
            MonotonicTimer(schedule_fn=lambda ms, cb: self.win.after(ms, cb),
                           cancel_fn=lambda handle: self.win.after_cancel(handle)),
            on_trial_recorded=self.writer.write_row,
            on_stage_advanced=self.after_input,
        )
        self.log(f"TFL session started ({self.config['run_mode']}): {self.writer.session_file.name}")
        self.engine.start()
        self.render()

    def render(self) -> None:
        render_trial(self)

    def after_input(self) -> None:
        if self.engine is not None and self.engine.completed and not self.finished:
            self._finish()
        self.render()

    def _finish(self) -> None:
        self.finished = True
        try:
            latest = self.writer.finalize()
            self.completion_message = (
                f"Saved {self.writer.rows_written} trials to:\n{latest}\n\nSession file:\n{self.writer.session_file}"
            )
        except Exception as exc:
            self.completion_message = (
                f"The run finished, but tfl_output.csv could not be updated.\n\n{type(exc).__name__}: {exc}\n\n"
                f"All completed trials are in:\n{self.writer.session_file}"
            )
        if self.engine.record_errors:
            self.completion_message += "\n\nWrite errors:\n" + "\n".join(self.engine.record_errors)
        self.log(self.completion_message.splitlines()[0])
        if self.app is not None:
            self.after_finish_in_host_app()

    # ---------------------------------------------------------- windows
    def window_exists(self) -> bool:
        try:
            return self.win is not None and bool(self.win.winfo_exists())
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
        if self.engine is not None and not self.engine.completed:
            done = len(self.engine.rows)
            prompt = ("Cancel this TFL run?\n\n"
                      f"{done} completed trial(s) are already saved in the session file. "
                      "tfl_output.csv will not be replaced.")
            try:
                if not messagebox.askyesno("Cancel TFL Run", prompt, parent=self.win):
                    return
            except tk.TclError:
                pass
            self.engine.cancel()
            path = self.writer.abandon()
            self.log(f"TFL run cancelled after {done} trial(s); kept in {path.name}")
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
                self.parent_root.destroy()
            except tk.TclError:
                pass
            self.parent_root = None
            self.created_parent_root = False

    def after_finish_in_host_app(self) -> None:
        for name, args in (("show_page", ("Results",)), ("analyze_tfl", ())):
            method = getattr(self.app, name, None)
            if callable(method):
                try:
                    method(*args)
                except (AttributeError, tk.TclError) as exc:
                    self.log(f"Post-run {name} failed: {exc}")

    def _error(self, title: str, message: str) -> None:
        self.log(message.splitlines()[0])
        try:
            messagebox.showerror(title, message, parent=self.win)
        except tk.TclError:
            pass

    def log(self, text: str) -> None:
        if self.app is not None and hasattr(self.app, "log"):
            try:
                self.app.log(text)
                return
            except (AttributeError, tk.TclError):
                pass
        print(text)


__all__ = ["TFLGuiSession"]
