"""
File: tests/test_merged.py

Purpose:
Headless test suite covering the registry, stimuli and trial building,
the TFL engine, identity and timestamps, autosave, analysis, the
dependency audit, the file-header standard, updater configuration,
obsolete-file removal, and the trust-anchor guard.

Communication / relationships:
- Imports app/headless.py, config/registries.py, frameworks/TFL/
  modules, services/trust_anchor.py, and the non-GUI updater modules.
- Never imports Tkinter page modules, so it runs without a display.

Settings / parameters:
- APPDATA is redirected to a temporary folder before any project
  import, so tests never touch real settings or output folders.
- STANDARD_HEADER_SECTIONS lists the six required header sections in
  order.

Edge cases:
- The header test parses every .py file with ast, so a syntax error in
  any file fails the suite.
- The updater tests never make network requests.

Known limitations:
- No GUI rendering coverage.
- tests/ has no __init__.py, so run this file directly rather than with
  python -m unittest tests.test_merged.

Examples:
- python tests/test_merged.py
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


class StageAdvancedHookTests(unittest.TestCase):
    """
    Covers on_stage_advanced, the hook that fixes a real GUI freeze: when
    a prediction/behavioral-choice timeout fires, the engine changes
    stage on its own initiative (not in response to any submit_*() call
    from the GUI), so without this hook nothing ever tells the window
    to redraw - it keeps showing buttons for a stage that no longer
    exists, and clicking them becomes a silent no-op forever.
    """
    def test_hook_fires_on_prediction_timeout(self):
        calls = []
        engine, timer = build_default_engine(on_stage_advanced=lambda: calls.append(engine.active_stage()))
        handle = engine.stage_state.timer_handle
        timer.fire(handle)
        self.assertEqual(calls, ["affect"])

    def test_hook_fires_on_behavioral_choice_timeout(self):
        calls = []
        engine, timer = build_default_engine(on_stage_advanced=lambda: calls.append(engine.active_stage()))
        engine.submit_prediction("A")
        engine.submit_affect(50)
        if engine.active_stage() == "content_probe":
            engine.submit_content_probe("U")
        if engine.active_stage() == "perturbation":
            engine.submit_post_perturbation_probe("U")
        calls.clear()
        self.assertEqual(engine.active_stage(), "behavioral_choice")
        handle = engine.stage_state.timer_handle
        timer.fire(handle)
        self.assertEqual(len(calls), 1)

    def test_hook_does_not_fire_on_explicit_submission(self):
        """
        submit_prediction() is a direct caller-initiated call, already
        followed by session.render() in the GUI's own _submit_and_render
        wrapper - the engine must not double-notify for that path.
        """
        calls = []
        engine, _timer = build_default_engine(on_stage_advanced=lambda: calls.append(1))
        engine.submit_prediction("A")
        self.assertEqual(calls, [])

    def test_hook_exception_does_not_break_the_session(self):
        def failing_hook():
            raise RuntimeError("simulated GUI redraw failure")
        engine, timer = build_default_engine(on_stage_advanced=failing_hook)
        handle = engine.stage_state.timer_handle
        self.assertTrue(timer.fire(handle) is None)  # fire() itself never raises
        self.assertEqual(engine.active_stage(), "affect")

    def test_no_hook_configured_is_safe(self):
        engine, timer = build_default_engine()
        handle = engine.stage_state.timer_handle
        timer.fire(handle)  # must not raise even with on_stage_advanced=None
        self.assertEqual(engine.active_stage(), "affect")


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


STANDARD_HEADER_SECTIONS = (
    "Purpose:",
    "Communication / relationships:",
    "Settings / parameters:",
    "Edge cases:",
    "Known limitations:",
    "Examples:",
)


class HeaderStandardTests(unittest.TestCase):
    """
    Enforces the archive-wide file header standard: every Python file
    starts with a module docstring whose first line is "File: <path>"
    followed by the six standard sections, in order. Parsing every file
    also means any syntax error anywhere in the project fails the suite.
    """

    def _python_files(self):
        return sorted(
            path for path in ROOT.rglob("*.py")
            if "__pycache__" not in path.parts
            and "PROJECT_CONTEXT_EXPORTS" not in path.parts
        )

    def test_every_python_file_has_the_standard_header(self):
        import ast

        for path in self._python_files():
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(file=relative):
                source = path.read_text(encoding="utf-8")
                docstring = ast.get_docstring(ast.parse(source), clean=False) or ""
                lines = [line.strip() for line in docstring.strip().splitlines()]
                self.assertTrue(lines, "missing module docstring")
                self.assertEqual(lines[0], f"File: {relative}")
                positions = []
                for section in STANDARD_HEADER_SECTIONS:
                    self.assertIn(section, lines, f"missing section {section}")
                    positions.append(lines.index(section))
                self.assertEqual(positions, sorted(positions), "sections out of order")


class NavigationTests(unittest.TestCase):
    def test_sidebar_has_no_tooling_entry(self):
        from config.registries import NAV_ITEMS, SETTINGS_NAV_ITEM

        names = [name for name, _icon in NAV_ITEMS] + [SETTINGS_NAV_ITEM[0]]
        self.assertEqual(names, ["Dashboard", "Frameworks", "Results", "Archive", "Settings"])

    def test_removed_tooling_modules_are_absent_from_source(self):
        from services.updater.constants import OBSOLETE_RELEASE_PATHS

        for relative in OBSOLETE_RELEASE_PATHS:
            with self.subTest(path=relative):
                self.assertFalse((ROOT / relative).exists())


class UpdaterConfigurationTests(unittest.TestCase):
    def test_registry_url_passes_the_host_allowlist(self):
        from services.updater.constants import REGISTRY_PAGE_URL
        from services.updater.http_utils import validate_remote_url

        self.assertEqual(validate_remote_url(REGISTRY_PAGE_URL), REGISTRY_PAGE_URL)

    def test_placeholder_trust_anchor_is_reported_as_unconfigured(self):
        from services import trust_anchor

        self.assertEqual(trust_anchor.PUBLIC_KEY_DICT["n"], "0x0")
        self.assertFalse(trust_anchor.is_configured())

    def test_unconfigured_trust_anchor_blocks_update_before_network(self):
        from services.updater import orchestration

        def must_not_fetch():
            raise AssertionError("registry must not be contacted")

        original = orchestration.fetch_registry_entry
        orchestration.fetch_registry_entry = must_not_fetch
        try:
            result = orchestration.check_and_maybe_install(lambda _line: None, auto_install=True)
            startup = orchestration.startup_update_check(lambda _line: None)
        finally:
            orchestration.fetch_registry_entry = original
        self.assertEqual(result["status"], "trust_anchor_unconfigured")
        self.assertEqual(startup["status"], "trust_anchor_unconfigured")

    def test_configured_trust_anchor_is_accepted(self):
        from services import rsa_signing, trust_anchor

        public_key, _private_key = rsa_signing.generate_keypair(bits=2048)
        original = dict(trust_anchor.PUBLIC_KEY_DICT)
        trust_anchor.PUBLIC_KEY_DICT.update(rsa_signing.public_key_to_dict(public_key))
        try:
            self.assertTrue(trust_anchor.is_configured())
        finally:
            trust_anchor.PUBLIC_KEY_DICT.clear()
            trust_anchor.PUBLIC_KEY_DICT.update(original)


class ObsoleteFileRemovalTests(unittest.TestCase):
    def test_listed_files_are_removed_and_others_kept(self):
        from services.updater.install import remove_obsolete_files

        with tempfile.TemporaryDirectory() as directory:
            app_dir = Path(directory)
            (app_dir / "config").mkdir()
            obsolete = app_dir / "config" / "tooling_state.py"
            kept = app_dir / "config" / "runtime.py"
            obsolete.write_text("old", encoding="utf-8")
            kept.write_text("keep", encoding="utf-8")
            removed = remove_obsolete_files(app_dir, ("config/tooling_state.py", "gui/pages/missing.py"))
            self.assertEqual(removed, [obsolete.resolve()])
            self.assertFalse(obsolete.exists())
            self.assertTrue(kept.exists())

    def test_unsafe_entries_are_never_deleted(self):
        from services.updater.install import remove_obsolete_files

        with tempfile.TemporaryDirectory() as outer:
            outside = Path(outer) / "outside.py"
            outside.write_text("do not delete", encoding="utf-8")
            app_dir = Path(outer) / "app"
            (app_dir / "folder").mkdir(parents=True)
            removed = remove_obsolete_files(
                app_dir,
                ("../outside.py", str(outside), "folder", "C:/Windows/win.ini"),
            )
            self.assertEqual(removed, [])
            self.assertTrue(outside.exists())
            self.assertTrue((app_dir / "folder").is_dir())


if __name__ == "__main__":
    unittest.main()
