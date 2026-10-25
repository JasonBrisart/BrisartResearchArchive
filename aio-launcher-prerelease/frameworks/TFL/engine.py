"""
File: frameworks/TFL/engine.py

Purpose
-------
Run one TFL session as a front-end-independent state machine that
reproduces the 02_Execution trial procedure, and hand a complete
snapshot of the session to the save hook after every single answer.
The GUI and the CLI both drive this one engine; neither owns protocol
logic.

Communication / relationships
-----------------------------
- Uses TimerInterface from frameworks/TFL/timing.py and frameworks/TFL/feedback.py.
- Driven by frameworks/TFL/gui_screens.py through frameworks/TFL/gui_session.py, by
  frameworks/TFL/cli_runner.py, and by frameworks/TFL/headless.py in tests.
- on_progress(rows) is normally frameworks/TFL/output.SessionWriter.save.
- on_stage_advanced() lets the GUI redraw after a timer expiry.

Settings / parameters
---------------------
- Stage order per trial: cue -> prediction -> affect ->
  [perturbation -> post_perturbation_probe] -> behavioral_choice ->
  [content_probe] -> row complete -> next cue or completion.
- Feedback is computed after the behavioral choice and exposed as
  current_feedback (shown with the content probe) and last_feedback
  (shown on the next cue or completion screen). There is no
  acknowledgement step, as in the reference.
- Saving: after every accepted answer and every timeout, on_progress
  receives all completed rows plus the current trial as an
  "in_progress" row.
- Timer: only with enable_response_timer; applies to prediction and
  behavioral_choice for trial_duration_sec seconds.

Edge cases
----------
- Invalid choices and invalid affect return False, do not advance, and
  do not save.
- Affect follows the reference: int(text.strip()) from 0 to 100; "50.5",
  blanks, and booleans are rejected.
- A submission at or after the deadline is recorded as a timeout.
- Timer generations increase for the engine's lifetime, so a stale
  callback can never act on a later stage.
- Save-hook exceptions are recorded in save_errors and never stop the
  session. Because every save is a full snapshot, the next successful
  save restores anything a failed save missed.
- finish_session() is idempotent.
- last_save_error clears on recovery; save_errors retains failure history.

Known limitations
-----------------
- Reaction times use the injected timer (monotonic clock), rounded to
  four decimals; the reference used time.time().
- Cue and perturbation "continue" steps are not answers and do not
  trigger a save.

Examples
--------
- engine = TFLSessionEngine(config, trials, NullSchedulerTimer(), on_progress=writer.save)
- engine.start(); engine.continue_cue(); engine.submit_prediction("A")
"""
from __future__ import annotations

from typing import Any, Callable

from . import feedback
from .timing import TimerInterface

TIMED_STAGES = {"prediction", "behavioral_choice"}
CHOICES_AB = {"A", "B"}
CHOICES_ABU = {"A", "B", "U"}


class TFLSessionEngine:
    def __init__(
        self,
        config: dict,
        trials: list[dict],
        timer: TimerInterface,
        *,
        on_progress: Callable[[list[dict]], None] | None = None,
        on_stage_advanced: Callable[[], None] | None = None,
    ):
        self.config = dict(config)
        self.trials = [dict(trial) for trial in trials]
        self.timer = timer
        self.on_progress = on_progress
        self.on_stage_advanced = on_stage_advanced
        self.timer_enabled = bool(self.config.get("enable_response_timer", False))
        self.timer_seconds = int(self.config.get("trial_duration_sec", 12)) if self.timer_enabled else None
        self.index = 0
        self.rows: list[dict] = []
        self.save_errors: list[str] = []
        self.last_save_error = ""
        self.saves = 0
        self.stage = "idle"
        self.completed = False
        self.cancelled = False
        self.response: dict[str, Any] = {}
        self.current_feedback = ""
        self.last_feedback = ""
        self._answered = False
        self._stage_started_at: float | None = None
        self._deadline_at: float | None = None
        self._timer_handle: object | None = None
        self._generation = 0
        self._completion_count = 0

    # ---------------------------------------------------------- state
    @property
    def current_trial(self) -> dict | None:
        if 0 <= self.index < len(self.trials):
            return self.trials[self.index]
        return None

    def active_stage(self) -> str:
        return self.stage

    def progress_label(self) -> str:
        return f"{min(self.index + 1, len(self.trials))} / {len(self.trials)}"

    def completion_count(self) -> int:
        return self._completion_count

    def perturbation_instruction(self) -> str:
        trial = self.current_trial or {}
        return feedback.make_perturbation_instruction(trial.get("perturbation_type", ""))

    def seconds_remaining(self) -> int | None:
        if self.stage not in TIMED_STAGES or self._deadline_at is None:
            return None
        return max(0, int((self._deadline_at - self.timer.now()) + 0.999))

    def snapshot(self) -> list[dict]:
        rows = list(self.rows)
        if self._answered and not self.completed and self.current_trial is not None:
            rows.append(self.build_output_row("in_progress"))
        return rows

    # ---------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self.stage != "idle":
            return
        if not self.trials:
            self.finish_session()
            return
        self._begin_trial()

    def cancel(self) -> None:
        self._invalidate_timer()
        self.cancelled = True

    def finish_session(self) -> None:
        if self.completed:
            return
        self._invalidate_timer()
        self.completed = True
        self.stage = "completion"
        self._completion_count += 1

    def _active(self, stage: str) -> bool:
        return not (self.completed or self.cancelled) and self.stage == stage

    def _begin_trial(self) -> None:
        self.response = {
            "prediction": "", "prediction_rt": "", "prediction_timed_out": False,
            "affect": "", "behavioral_choice": "", "behavioral_rt": "", "behavioral_timed_out": False,
            "post_perturbation_probe": "", "perturbation_match_prediction": "",
            "content_probe": "", "correct_answer": "", "contradiction": "",
        }
        self._answered = False
        self.current_feedback = ""
        self._begin_stage("cue")

    def _begin_stage(self, stage: str) -> None:
        self._invalidate_timer()
        self.stage = stage
        self._stage_started_at = self.timer.now()
        self._deadline_at = None
        if stage in TIMED_STAGES and self.timer_enabled:
            self._deadline_at = self._stage_started_at + self.timer_seconds
            generation = self._generation
            self._timer_handle = self.timer.schedule(
                int(self.timer_seconds * 1000), lambda: self.handle_timeout(stage, generation),
            )

    def _invalidate_timer(self) -> None:
        if self._timer_handle is not None:
            self.timer.cancel(self._timer_handle)
        self._timer_handle = None
        self._generation += 1

    def _deadline_passed(self) -> bool:
        return self._deadline_at is not None and self.timer.now() >= self._deadline_at

    def _elapsed(self) -> float | str:
        if self._stage_started_at is None:
            return ""
        return round(self.timer.now() - self._stage_started_at, 4)

    def _save(self) -> None:
        if self.on_progress is None:
            return
        rows = self.snapshot()
        try:
            self.on_progress(rows)
            self.saves += 1
            self.last_save_error = ""
        except Exception as exc:
            self.last_save_error = f"save of {len(rows)} row(s) failed: {type(exc).__name__}: {exc}"
            self.save_errors.append(self.last_save_error)

    # ---------------------------------------------------------- answers
    def continue_cue(self) -> bool:
        if not self._active("cue"):
            return False
        self._begin_stage("prediction")
        return True

    def submit_prediction(self, choice: Any) -> bool:
        return self._submit_timed("prediction", choice)

    def submit_behavioral_choice(self, choice: Any) -> bool:
        return self._submit_timed("behavioral_choice", choice)

    def _submit_timed(self, stage: str, choice: Any) -> bool:
        if not self._active(stage):
            return False
        if self._deadline_passed():
            self._expire(stage)
            return False
        value = str(choice).strip().upper()
        if value not in CHOICES_AB:
            return False
        elapsed = self._elapsed()
        self._answered = True
        if stage == "prediction":
            self.response.update(prediction=value, prediction_rt=elapsed)
            self._begin_stage("affect")
            self._save()
        else:
            self.response.update(behavioral_choice=value, behavioral_rt=elapsed)
            self._after_behavioral_choice()
        return True

    def handle_timeout(self, stage: str, generation: int) -> bool:
        if not self._active(stage) or generation != self._generation:
            return False
        self._expire(stage)
        if self.on_stage_advanced is not None:
            try:
                self.on_stage_advanced()
            except Exception:
                pass
        return True

    def _expire(self, stage: str) -> None:
        self._answered = True
        if stage == "prediction":
            self.response.update(prediction="", prediction_rt="", prediction_timed_out=True)
            self._begin_stage("affect")
            self._save()
        else:
            self.response.update(behavioral_choice="", behavioral_rt="", behavioral_timed_out=True)
            self._after_behavioral_choice()

    def submit_affect(self, value: Any) -> bool:
        if not self._active("affect") or isinstance(value, bool):
            return False
        try:
            number = int(str(value).strip())
        except ValueError:
            return False
        if not 0 <= number <= 100:
            return False
        self.response["affect"] = number
        self._begin_stage("perturbation" if self.current_trial.get("perturbation_trial") else "behavioral_choice")
        self._save()
        return True

    def continue_perturbation(self) -> bool:
        if not self._active("perturbation"):
            return False
        self._begin_stage("post_perturbation_probe")
        return True

    def submit_post_perturbation_probe(self, choice: Any) -> bool:
        if not self._active("post_perturbation_probe"):
            return False
        value = str(choice).strip().upper()
        if value not in CHOICES_ABU:
            return False
        self.response["post_perturbation_probe"] = value
        prediction = self.response["prediction"]
        if value in CHOICES_AB and prediction in CHOICES_AB:
            self.response["perturbation_match_prediction"] = value == prediction
        self._begin_stage("behavioral_choice")
        self._save()
        return True

    def _after_behavioral_choice(self) -> None:
        trial = self.current_trial
        prediction = self.response["prediction"]
        correct_answer, contradiction = feedback.determine_feedback(prediction, trial["feedback_level"])
        self.response.update(correct_answer=correct_answer, contradiction=contradiction)
        self.current_feedback = feedback.feedback_text(trial["feedback_level"], prediction, correct_answer)
        if trial.get("probe_trial") or trial.get("delayed_reentry"):
            self._begin_stage("content_probe")
            self._save()
        else:
            self._complete_trial()

    def submit_content_probe(self, choice: Any) -> bool:
        if not self._active("content_probe"):
            return False
        value = str(choice).strip().upper()
        if value not in CHOICES_ABU:
            return False
        self.response["content_probe"] = value
        self._complete_trial()
        return True

    # ---------------------------------------------------------- recording
    def build_output_row(self, status: str = "complete") -> dict:
        trial, r = self.current_trial, self.response
        return {
            "trial_id": trial["trial_id"],
            "framework_id": trial["framework_id"],
            "run_mode": trial["run_mode"],
            "block": trial["block"],
            "block_trial_num": trial["block_trial_num"],
            "stimulus_id": trial["stimulus_id"],
            "cue": trial["cue"],
            "ambiguous_text": trial["ambiguous_text"],
            "interpretation_a": trial["interpretation_a"],
            "interpretation_b": trial["interpretation_b"],
            "prior_instruction": trial["prior_instruction"],
            "prediction": r["prediction"],
            "prediction_rt": r["prediction_rt"],
            "affect": r["affect"],
            "behavioral_choice": r["behavioral_choice"],
            "behavioral_rt": r["behavioral_rt"],
            "feedback_level": trial["feedback_level"],
            "correct_answer": r["correct_answer"],
            "contradiction": r["contradiction"],
            "probe_trial": trial["probe_trial"],
            "content_probe": r["content_probe"],
            "delayed_reentry": trial["delayed_reentry"],
            "recurrence_source_trial": trial["recurrence_source_trial"],
            "perturbation_trial": trial["perturbation_trial"],
            "perturbation_type": trial["perturbation_type"],
            "post_perturbation_probe": r["post_perturbation_probe"],
            "perturbation_match_prediction": r["perturbation_match_prediction"],
            "response_timer_sec": self.timer_seconds if self.timer_enabled else "",
            "prediction_timed_out": r["prediction_timed_out"],
            "behavioral_timed_out": r["behavioral_timed_out"],
            "session_label": self.config.get("session_label", ""),
            "random_seed": self.config.get("random_seed", ""),
            "trial_status": status,
        }

    def _complete_trial(self) -> None:
        self._invalidate_timer()
        self.rows.append(self.build_output_row("complete"))
        self._answered = False
        self.last_feedback = self.current_feedback
        self.current_feedback = ""
        self.index += 1
        if self.index >= len(self.trials):
            self.finish_session()
        else:
            self._begin_trial()
        self._save()


__all__ = ["TFLSessionEngine", "TIMED_STAGES"]
