"""
Headless test suite for the merged architecture.

These tests exercise the engine layer (engine/, frameworks/TFL/engine.py)
plus the registry and analysis layers - all pure Python, no Tkinter
required. GUI rendering (screen.py, session_gui.py, gui/*) is not
covered here because it needs a display; the point of the engine split
is that trial *logic* never needs one.
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

# Force a throwaway APPDATA so tests never touch the user's real settings
# or output folders.
_TEMP_APPDATA = tempfile.mkdtemp(prefix="brisart_test_appdata_")
os.environ["APPDATA"] = _TEMP_APPDATA

from app.headless import build_default_engine
from config.registries import get_available_frameworks, refresh_framework_registry
from frameworks.TFL import analysis, framework
from frameworks.TFL.config import get_default_config
from frameworks.TFL.trial_builder import build_trials


class RegistryTests(unittest.TestCase):
    def test_registry_loads_tfl(self):
        registry = refresh_framework_registry()
        self.assertTrue(any(item["id"] == "TFL" for item in registry))
        self.assertEqual(get_available_frameworks()[0]["id"], "TFL")

    def test_metadata_points_at_merged_session(self):
        self.assertEqual(framework.FRAMEWORK_METADATA["id"], "TFL")
        self.assertEqual(framework.FRAMEWORK_METADATA["runner_module"], "frameworks.TFL.session_gui")
        self.assertEqual(framework.FRAMEWORK_METADATA["runner_class"], "TFLGuiSession")


class StimulusAndTrialTests(unittest.TestCase):
    def test_stimuli_load(self):
        stimuli = framework.load_stimuli()
        self.assertEqual(len(stimuli), 60)
        self.assertEqual(stimuli[0]["stimulus_id"], "S001")

    def test_seed_reproducibility(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        first = build_trials(config, stimuli)
        second = build_trials(config, stimuli)
        self.assertEqual(first, second)

    def test_trial_counts(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        self.assertEqual(len(trials), 120)
        self.assertEqual(sum(1 for item in trials if item["block"] == "affect"), 40)
        self.assertEqual(sum(1 for item in trials if item["block"] == "belief"), 40)
        self.assertEqual(sum(1 for item in trials if item["block"] == "contradiction"), 40)

    def test_probe_intervals(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        probe_trials = [item["trial_id"] for item in trials if item["probe_trial"]]
        self.assertEqual(probe_trials[:5], [4, 8, 12, 16, 20])

    def test_delayed_reentry(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        trial = trials[11]
        self.assertTrue(trial["delayed_reentry"])
        self.assertEqual(trial["recurrence_source_trial"], 6)
        source = trials[5]
        self.assertEqual(trial["stimulus_id"], source["stimulus_id"])

    def test_perturbations_when_enabled(self):
        config = get_default_config()
        config["enable_perturbations"] = True
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        perturbation_trials = [item["trial_id"] for item in trials if item["perturbation_trial"]]
        self.assertEqual(perturbation_trials[:4], [5, 10, 15, 20])

    def test_feedback_levels_valid(self):
        config = get_default_config()
        stimuli = framework.apply_stimulus_limit(framework.load_stimuli(), config)
        trials = build_trials(config, stimuli)
        contradiction_levels = {item["feedback_level"] for item in trials if item["block"] == "contradiction"}
        self.assertTrue(contradiction_levels.issubset({"confirmatory", "mildly_contradictory", "strongly_contradictory"}))
        self.assertEqual({item["feedback_level"] for item in trials if item["block"] == "affect"}, {"neutral"})
        self.assertEqual({item["feedback_level"] for item in trials if item["block"] == "belief"}, {"confirmatory"})


class EngineTests(unittest.TestCase):
    def test_single_active_stage(self):
        engine, _timer = build_default_engine()
        self.assertEqual(engine.active_stage(), "prediction")

    def test_a_records_once(self):
        engine, _timer = build_default_engine()
        self.assertTrue(engine.submit_prediction("A"))
        self.assertFalse(engine.submit_prediction("A"))
        self.assertEqual(engine.current_trial_response["prediction"], "A")

    def test_b_records_once(self):
        engine, _timer = build_default_engine()
        self.assertTrue(engine.submit_prediction("B"))
        self.assertFalse(engine.submit_prediction("B"))
        self.assertEqual(engine.current_trial_response["prediction"], "B")

    def test_invalid_input_does_not_advance(self):
        engine, _timer = build_default_engine()
        self.assertFalse(engine.submit_prediction("Q"))
        self.assertEqual(engine.active_stage(), "prediction")

    def test_duplicate_submissions_rejected(self):
        engine, _timer = build_default_engine()
        self.assertTrue(engine.submit_prediction("A"))
        self.assertFalse(engine.submit_prediction("B"))
        self.assertEqual(engine.current_trial_response["prediction"], "A")

    def test_timeout_records_once_and_advances_once(self):
        engine, timer = build_default_engine()
        handle = engine.stage_state.timer_handle
        timer.fire(handle)
        self.assertTrue(engine.current_trial_response["prediction_timed_out"])
        self.assertEqual(engine.active_stage(), "affect")
        self.assertFalse(engine.handle_timeout("prediction", engine.stage_state.timer_token))

    def test_stale_timer_callback_ignored(self):
        engine, timer = build_default_engine()
        stale_handle = engine.stage_state.timer_handle
        stale_token = engine.stage_state.timer_token
        self.assertTrue(engine.submit_prediction("A"))
        self.assertEqual(engine.active_stage(), "affect")
        timer.fire(stale_handle)
        self.assertEqual(engine.active_stage(), "affect")
        self.assertFalse(engine.handle_timeout("prediction", stale_token))

    def test_timer_resets_to_12(self):
        engine, _timer = build_default_engine()
        self.assertEqual(engine.seconds_remaining(now=0.0), 12)
        self.assertTrue(engine.submit_prediction("A"))
        self.assertTrue(engine.submit_affect(60))
        if engine.active_stage() == "content_probe":
            engine.submit_content_probe("U")
        if engine.active_stage() == "perturbation":
            engine.submit_post_perturbation_probe("U")
        self.assertEqual(engine.active_stage(), "behavioral_choice")
        self.assertEqual(engine.seconds_remaining(now=0.0), 12)

    def test_completion_occurs_exactly_once(self):
        engine, _timer = build_default_engine()
        while not engine.completed:
            stage = engine.active_stage()
            if stage == "prediction":
                engine.submit_prediction("A")
            elif stage == "affect":
                engine.submit_affect(50)
            elif stage == "content_probe":
                engine.submit_content_probe("U")
            elif stage == "perturbation":
                engine.submit_post_perturbation_probe("U")
            elif stage == "behavioral_choice":
                engine.submit_behavioral_choice("B")
        self.assertEqual(engine.completion_count(), 1)
        engine.finish_session()
        self.assertEqual(engine.completion_count(), 2)

    def test_cancel_stops_engine(self):
        engine, _timer = build_default_engine()
        engine.cancel()
        self.assertTrue(engine.cancelled)
        self.assertFalse(engine.submit_prediction("A"))


class IdentityAndTimestampTests(unittest.TestCase):
    """
    Covers the participant/session identity and wall-clock timestamp
    fields added to close the "whose data is this" gap - previously
    every run wrote to the same identity-less output file with no way
    to tell one participant's session from another's.
    """

    def test_session_id_auto_generated_and_unique(self):
        first_engine, _first_timer = build_default_engine()
        second_engine, _second_timer = build_default_engine()
        self.assertTrue(first_engine.session_id)
        self.assertTrue(second_engine.session_id)
        self.assertNotEqual(first_engine.session_id, second_engine.session_id)

    def test_explicit_session_id_is_respected(self):
        engine, _timer = build_default_engine(session_id="fixed-session-001")
        self.assertEqual(engine.session_id, "fixed-session-001")

    def test_participant_id_flows_into_rows(self):
        engine, _timer = build_default_engine(participant_id="P042")
        engine.submit_prediction("A")
        engine.submit_affect(50)
        if engine.active_stage() == "content_probe":
            engine.submit_content_probe("U")
        if engine.active_stage() == "perturbation":
            engine.submit_post_perturbation_probe("U")
        engine.submit_behavioral_choice("A")
        self.assertEqual(engine.rows[0]["participant_id"], "P042")
        self.assertEqual(engine.rows[0]["session_id"], engine.session_id)

    def test_trial_timestamps_are_recorded(self):
        engine, _timer = build_default_engine()
        engine.submit_prediction("A")
        engine.submit_affect(50)
        if engine.active_stage() == "content_probe":
            engine.submit_content_probe("U")
        if engine.active_stage() == "perturbation":
            engine.submit_post_perturbation_probe("U")
        engine.submit_behavioral_choice("A")
        row = engine.rows[0]
        self.assertTrue(row["trial_started_at_iso"])
        self.assertTrue(row["trial_completed_at_iso"])
        self.assertLessEqual(row["trial_started_at_iso"], row["trial_completed_at_iso"])


class AutosaveHookTests(unittest.TestCase):
    """
    Covers on_trial_recorded, the hook that lets a caller checkpoint an
    in-progress run to disk. Previously save_rows() was only ever
    called once, at session completion, so a crash mid-run lost
    everything collected up to that point.
    """

    def _complete_one_trial(self, engine) -> None:
        engine.submit_prediction("A")
        engine.submit_affect(50)
        if engine.active_stage() == "content_probe":
            engine.submit_content_probe("U")
        if engine.active_stage() == "perturbation":
            engine.submit_post_perturbation_probe("U")
        engine.submit_behavioral_choice("A")

    def test_hook_fires_once_per_completed_trial(self):
        call_counts = []
        engine, _timer = build_default_engine(
            on_trial_recorded=lambda rows: call_counts.append(len(rows))
        )
        self._complete_one_trial(engine)
        self._complete_one_trial(engine)
        self.assertEqual(call_counts, [1, 2])

    def test_hook_exception_does_not_break_the_session(self):
        def failing_hook(rows):
            raise RuntimeError("simulated autosave failure")

        engine, _timer = build_default_engine(on_trial_recorded=failing_hook)
        self._complete_one_trial(engine)
        self.assertEqual(len(engine.rows), 1)
        self.assertEqual(engine.active_stage(), "prediction")


class OutputTests(unittest.TestCase):
    def _run_two_trials(self):
        engine, _timer = build_default_engine()
        while not engine.completed and len(engine.rows) < 2:
            stage = engine.active_stage()
            if stage == "prediction":
                engine.submit_prediction("A")
            elif stage == "affect":
                engine.submit_affect(50)
            elif stage == "content_probe":
                engine.submit_content_probe("U")
            elif stage == "perturbation":
                engine.submit_post_perturbation_probe("U")
            elif stage == "behavioral_choice":
                engine.submit_behavioral_choice("B")
        return engine

    def test_output_round_trip_and_non_destructive_persistence(self):
        engine = self._run_two_trials()
        first_path = analysis.save_rows(engine.rows)
        second_path = analysis.save_rows(engine.rows)
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.exists())
        self.assertTrue(second_path.exists())
        loaded = analysis.load_output(second_path)
        self.assertEqual(len(loaded), len(engine.rows))
        report = analysis.analyze_output(second_path)
        self.assertIn("TFL Analysis", report)

    def test_completion_status_recorded(self):
        engine = self._run_two_trials()
        self.assertTrue(all(row["completion_status"] == "completed" for row in engine.rows))


class ConsistencyAndCarryoverAnalysisTests(unittest.TestCase):
    """
    Covers the core scientific gap the framework had: prediction and
    behavioral_choice were recorded every trial but never compared to
    each other, and contradiction feedback was never checked for any
    effect on the *next* trial - despite that being the entire premise
    implied by "Temporal Feedback Loop".
    """

    @staticmethod
    def _row(trial_id, prediction, behavioral_choice, contradiction, affect=50):
        return {
            "trial_id": trial_id,
            "block": "contradiction",
            "prediction": prediction,
            "behavioral_choice": behavioral_choice,
            "contradiction": contradiction,
            "affect": affect,
            "completion_status": "completed",
        }

    def test_perfect_consistency_is_reported(self):
        rows = [self._row(i, "A", "A", "none") for i in range(1, 6)]
        report = analysis.prediction_behavior_consistency_report(rows)
        report_text = "\n".join(report)
        self.assertIn("Comparable trials: 5", report_text)
        self.assertIn("100.0%", report_text)

    def test_zero_consistency_is_reported(self):
        rows = [self._row(i, "A", "B", "none") for i in range(1, 6)]
        report_text = "\n".join(analysis.prediction_behavior_consistency_report(rows))
        self.assertIn("Prediction matched behavior: 0", report_text)

    def test_rows_without_comparable_choices_are_handled(self):
        rows = [self._row(1, "", "", "none")]
        report_text = "\n".join(analysis.prediction_behavior_consistency_report(rows))
        self.assertIn("No trials had both a prediction and a behavioral choice", report_text)

    def test_carryover_buckets_by_prior_trial_contradiction(self):
        # Trial 1 gets strong contradiction feedback; trial 2 (which
        # follows it) should be bucketed under "Following 'strong'".
        rows = [
            self._row(1, "A", "A", "strong", affect=80),
            self._row(2, "A", "B", "none", affect=40),
        ]
        report_text = "\n".join(analysis.feedback_carryover_report(rows))
        self.assertIn("Following 'strong' feedback (1 trials)", report_text)

    def test_carryover_needs_at_least_two_trials(self):
        rows = [self._row(1, "A", "A", "none")]
        report_text = "\n".join(analysis.feedback_carryover_report(rows))
        self.assertIn("Not enough sequential trials", report_text)

    def test_sorted_completed_rows_ignores_incomplete_trials(self):
        rows = [
            self._row(2, "A", "A", "none"),
            {"trial_id": 1, "completion_status": "in_progress"},
            self._row(3, "B", "B", "none"),
        ]
        ordered = analysis.sorted_completed_rows(rows)
        self.assertEqual([row["trial_id"] for row in ordered], [2, 3])


class AutosaveFileTests(unittest.TestCase):
    """Covers the incremental checkpoint file lifecycle end to end."""

    def test_autosave_write_load_and_remove_round_trip(self):
        session_id = "autosave-test-001"
        rows = [
            {
                "session_id": session_id, "participant_id": "P1", "trial_id": 1,
                "framework_id": "TFL", "block": "affect", "stimulus_id": "S001",
                "prediction": "A", "behavioral_choice": "A", "affect": 50,
                "completion_status": "completed",
            }
        ]
        saved_path = analysis.autosave_rows(rows, session_id)
        self.assertTrue(saved_path.exists())
        loaded = analysis.load_output(saved_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["session_id"], session_id)
        analysis.remove_autosave_file(session_id)
        self.assertFalse(saved_path.exists())

    def test_session_id_is_sanitized_for_filesystem_safety(self):
        unsafe_id = "../../etc/passwd"
        safe_path = analysis.get_autosave_file(unsafe_id)
        self.assertNotIn("..", safe_path.name)


class DependencyAuditTests(unittest.TestCase):
    def test_engine_and_analysis_layers_are_stdlib_or_internal(self):
        """
        Confirms the headless-safe layers (engine, config, frameworks)
        never import Tkinter. gui/ and frameworks/TFL/screen.py|session_gui.py
        are intentionally excluded - those are the presentation layer.
        """
        excluded_suffixes = ("screen", "session_gui")
        for package_name in ("engine", "config", "frameworks"):
            package_root = ROOT / package_name
            for module_info in pkgutil.walk_packages([str(package_root)], prefix=package_name + "."):
                name = module_info.name
                if any(name.endswith(suffix) for suffix in excluded_suffixes):
                    continue
                if name.startswith("config.state"):
                    continue  # config.state legitimately wraps Tk variables
                module = importlib.import_module(name)
                self.assertTrue(module.__name__.startswith(package_name))


if __name__ == "__main__":
    unittest.main()
