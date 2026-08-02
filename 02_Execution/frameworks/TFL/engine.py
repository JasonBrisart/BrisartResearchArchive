"""
TFL session engine — the headless, testable brain of the framework.

This is the core of the merge: all trial state, timing, validation, and
recording lives here with zero Tkinter dependency, so it can be driven
by unit tests (via engine.timing.NullSchedulerTimer) or by a real GUI
(via engine.timing.MonotonicTimer bound to Tk's .after()). The GUI
layer (screen.py + session_gui.py) only renders whatever state this
class reports; it never owns trial logic itself.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.timing import TimerInterface
from . import feedback

TIMED_STAGES = {"prediction", "behavioral_choice"}


@dataclass
class StageState:
    name: str
    started_at: float | None = None
    deadline_at: float | None = None
    timer_handle: object | None = None
    timer_token: int = field(default=0)
    input_locked: bool = False


class TFLSessionEngine:
    """
    Drives one TFL run trial-by-trial. Owns: current stage, timing,
    response validation/locking, row construction, and completion
    bookkeeping. Does not know anything about Tkinter.
    """

    def __init__(self, config: dict, trials: list[dict], timer: TimerInterface):
        self.config = dict(config)
        self.trials = [dict(trial) for trial in trials]
        self.timer = timer
        self.index = 0
        self.rows: list[dict] = []
        self.completed = False
        self.cancelled = False
        self.current_stage_name = "prediction"
        self.stage_state = StageState(name="prediction")
        self.current_trial_response: dict[str, Any] = {}
        self._completion_count = 0

    # ------------------------------------------------------------
    # State accessors
    # ------------------------------------------------------------

    @property
    def current_trial(self) -> dict | None:
        if 0 <= self.index < len(self.trials):
            return self.trials[self.index]
        return None

    def active_stage(self) -> str:
        return self.current_stage_name

    def progress_label(self) -> str:
        return f"{self.index + 1} / {len(self.trials)}"

    def completion_count(self) -> int:
        return self._completion_count

    def seconds_remaining(self, now: float | None = None) -> int | None:
        if self.current_stage_name not in TIMED_STAGES:
            return None
        if self.stage_state.deadline_at is None:
            return None
        current = self.timer.now() if now is None else now
        return max(0, int((self.stage_state.deadline_at - current) + 0.999))

    # ------------------------------------------------------------
    # Stage / timer management
    # ------------------------------------------------------------

    def invalidate_timer(self) -> None:
        if self.stage_state.timer_handle is not None:
            self.timer.cancel(self.stage_state.timer_handle)
        self.stage_state.timer_handle = None
        self.stage_state.timer_token += 1

    def begin_stage(self, stage_name: str) -> None:
        self.invalidate_timer()
        self.current_stage_name = stage_name
        started_at = self.timer.now()
        self.stage_state = StageState(name=stage_name, started_at=started_at)
        if stage_name in TIMED_STAGES:
            duration = float(self.config.get("trial_duration_sec", 12))
            self.stage_state.deadline_at = started_at + duration
            self.stage_state.timer_token += 1
            token = self.stage_state.timer_token
            self.stage_state.timer_handle = self.timer.schedule(
                int(duration * 1000),
                lambda: self.handle_timeout(stage_name, token),
            )

    def start_trial(self) -> None:
        if self.current_trial is None:
            self.finish_session()
            return
        self.current_trial_response = {
            "prediction": "",
            "prediction_rt": "",
            "prediction_timed_out": False,
            "affect": 50,
            "behavioral_choice": "",
            "behavioral_rt": "",
            "behavioral_timed_out": False,
            "content_probe": "",
            "post_perturbation_probe": "",
            "perturbation_match_prediction": "",
            "completion_status": "in_progress",
        }
        self.begin_stage("prediction")

    # ------------------------------------------------------------
    # Response submission
    # ------------------------------------------------------------

    def submit_prediction(self, choice: str) -> bool:
        return self._submit_timed_choice("prediction", choice)

    def submit_behavioral_choice(self, choice: str) -> bool:
        return self._submit_timed_choice("behavioral_choice", choice)

    def _submit_timed_choice(self, stage_name: str, choice: str) -> bool:
        choice = str(choice).strip().upper()
        if self.completed or self.cancelled:
            return False
        if self.current_stage_name != stage_name or self.stage_state.input_locked:
            return False
        if choice not in {"A", "B"}:
            return False
        self.stage_state.input_locked = True
        reaction_time = ""
        if self.stage_state.started_at is not None:
            reaction_time = round(self.timer.now() - self.stage_state.started_at, 4)
        if stage_name == "prediction":
            self.current_trial_response["prediction"] = choice
            self.current_trial_response["prediction_rt"] = reaction_time
            self.current_trial_response["prediction_timed_out"] = False
            self.invalidate_timer()
            self.begin_stage("affect")
        else:
            self.current_trial_response["behavioral_choice"] = choice
            self.current_trial_response["behavioral_rt"] = reaction_time
            self.current_trial_response["behavioral_timed_out"] = False
            self.invalidate_timer()
            self.advance_after_behavioral_choice()
        return True

    def handle_timeout(self, stage_name: str, token: int) -> bool:
        if self.completed or self.cancelled:
            return False
        if self.current_stage_name != stage_name:
            return False
        if self.stage_state.timer_token != token:
            return False
        if self.stage_state.input_locked:
            return False
        self.stage_state.input_locked = True
        self.invalidate_timer()
        if stage_name == "prediction":
            self.current_trial_response["prediction"] = ""
            self.current_trial_response["prediction_rt"] = ""
            self.current_trial_response["prediction_timed_out"] = True
            self.begin_stage("affect")
            return True
        if stage_name == "behavioral_choice":
            self.current_trial_response["behavioral_choice"] = ""
            self.current_trial_response["behavioral_rt"] = ""
            self.current_trial_response["behavioral_timed_out"] = True
            self.advance_after_behavioral_choice()
            return True
        return False

    def submit_affect(self, value: int) -> bool:
        if self.completed or self.cancelled or self.current_stage_name != "affect":
            return False
        try:
            number = int(value)
        except (TypeError, ValueError):
            return False
        if not 0 <= number <= 100:
            return False
        self.current_trial_response["affect"] = number
        if self.current_trial.get("perturbation_trial"):
            self.begin_stage("perturbation")
        elif self.current_trial.get("probe_trial") or self.current_trial.get("delayed_reentry"):
            self.begin_stage("content_probe")
        else:
            self.begin_stage("behavioral_choice")
        return True

    def submit_post_perturbation_probe(self, choice: str) -> bool:
        choice = str(choice).strip().upper()
        if self.completed or self.cancelled or self.current_stage_name != "perturbation":
            return False
        if choice not in {"A", "B", "U"}:
            return False
        self.current_trial_response["post_perturbation_probe"] = choice
        prediction = self.current_trial_response.get("prediction", "")
        if choice in {"A", "B"} and prediction in {"A", "B"}:
            self.current_trial_response["perturbation_match_prediction"] = str(choice == prediction)
        if self.current_trial.get("probe_trial") or self.current_trial.get("delayed_reentry"):
            self.begin_stage("content_probe")
        else:
            self.begin_stage("behavioral_choice")
        return True

    def submit_content_probe(self, choice: str) -> bool:
        choice = str(choice).strip().upper()
        if self.completed or self.cancelled or self.current_stage_name != "content_probe":
            return False
        if choice not in {"A", "B", "U"}:
            return False
        self.current_trial_response["content_probe"] = choice
        self.begin_stage("behavioral_choice")
        return True

    # ------------------------------------------------------------
    # Advancement / recording / completion
    # ------------------------------------------------------------

    def advance_after_behavioral_choice(self) -> None:
        self.rows.append(self.build_output_row())
        self.index += 1
        if self.index >= len(self.trials):
            self.finish_session()
        else:
            self.start_trial()

    def build_output_row(self) -> dict:
        trial = dict(self.current_trial)
        prediction = self.current_trial_response.get("prediction", "")
        correct_answer, contradiction = feedback.determine_feedback(
            prediction, trial.get("feedback_level", "")
        )
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
            "prediction": self.current_trial_response["prediction"],
            "prediction_rt": self.current_trial_response["prediction_rt"],
            "prediction_timed_out": self.current_trial_response["prediction_timed_out"],
            "affect": self.current_trial_response["affect"],
            "behavioral_choice": self.current_trial_response["behavioral_choice"],
            "behavioral_rt": self.current_trial_response["behavioral_rt"],
            "behavioral_timed_out": self.current_trial_response["behavioral_timed_out"],
            "feedback_level": trial["feedback_level"],
            "correct_answer": correct_answer,
            "contradiction": contradiction,
            "probe_trial": trial["probe_trial"],
            "content_probe": self.current_trial_response["content_probe"],
            "delayed_reentry": trial["delayed_reentry"],
            "recurrence_source_trial": trial["recurrence_source_trial"],
            "perturbation_trial": trial["perturbation_trial"],
            "perturbation_type": trial["perturbation_type"],
            "post_perturbation_probe": self.current_trial_response["post_perturbation_probe"],
            "perturbation_match_prediction": self.current_trial_response["perturbation_match_prediction"],
            "completion_status": "completed",
        }

    def finish_session(self) -> None:
        self.invalidate_timer()
        self.completed = True
        self.current_stage_name = "completion"
        self._completion_count += 1

    def cancel(self) -> None:
        self.invalidate_timer()
        self.cancelled = True


__all__ = ["TFLSessionEngine", "StageState", "TIMED_STAGES"]
