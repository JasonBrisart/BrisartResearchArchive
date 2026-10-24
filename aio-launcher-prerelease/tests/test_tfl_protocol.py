"""
File: tests/test_tfl_protocol.py

Purpose
-------
Prove that the native TFL implementation reproduces the 02_Execution
reference procedure, and test the Archive additions (optional response
timer, per-trial session files, standard-library analysis, CLI).

Communication / relationships
-----------------------------
- Imports app/headless.py, cli.py, and frameworks/TFL headless modules.
- Never imports Tkinter; runs on Python builds without Tk.

Settings / parameters
---------------------
- APPDATA is redirected to a temporary folder before project imports.
- reference_build_trials() is a verbatim port of the reference
  algorithm using the process-wide random module, used as the oracle.
- REFERENCE_STIMULI_SHA256 is the digest of the reference
  tfl_stimuli.csv rows serialized as sorted-key JSON.

Edge cases
----------
- Console runs are scripted through input_fn/print_fn; timers use the
  virtual NullSchedulerTimer clock.

Known limitations
-----------------
- No native GUI rendering coverage.

Examples
--------
- python tests/test_tfl_protocol.py
"""
from __future__ import annotations

import ast
import csv
import hashlib
import itertools
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="brisart_tfl_test_")

from app.headless import build_default_engine  # noqa: E402
from engine.timing import NullSchedulerTimer  # noqa: E402
from frameworks.TFL import analysis, cli_runner, feedback  # noqa: E402
from frameworks.TFL.config import get_default_config, update_run_mode  # noqa: E402
from frameworks.TFL.engine import TFLSessionEngine  # noqa: E402
from frameworks.TFL.output import SessionWriter  # noqa: E402
from frameworks.TFL.schema import REFERENCE_FIELDNAMES, TRIAL_FIELDNAMES  # noqa: E402
from frameworks.TFL.stimuli import apply_stimulus_limit, load_stimuli  # noqa: E402
from frameworks.TFL.trial_builder import build_trials  # noqa: E402

REFERENCE_STIMULI_SHA256 = "ba4983fed0e170eaeb60c69fbd08fb236ba7c3789b6e79131b7c50fb5ba011e0"
TOGGLES = ["enable_extra_stimuli", "enable_perturbations", "enable_probes", "enable_delayed_reentry"]


# ------------------------------------------------------------------ oracle
def reference_build_trials(config, stimuli):
    """02_Execution TFL/framework.py build_trials, process-wide random."""
    random.seed(config.get("random_seed", None))
    probe_interval = config.get("probe_interval", 0)
    reentry_interval = config.get("delayed_reentry_interval", 0)
    perturbation_interval = config.get("perturbation_interval", 0) if config.get("enable_perturbations", False) else 0
    trials, trial_id = [], 1
    for block in config["blocks"]:
        for block_trial_num in range(1, config["trials_per_block"] + 1):
            stimulus = random.choice(stimuli)
            prior = random.choice(["A", "B"])
            probe = bool(config.get("enable_probes", True) and probe_interval and probe_interval > 0
                         and trial_id % probe_interval == 0)
            delayed, source = False, ""
            if (config.get("enable_delayed_reentry", True) and reentry_interval and reentry_interval > 0
                    and trial_id > reentry_interval and block_trial_num % reentry_interval == 0):
                old = trials[-reentry_interval]
                stimulus = {k: old[k] for k in ("stimulus_id", "cue", "ambiguous_text", "interpretation_a", "interpretation_b")}
                delayed, source = True, old["trial_id"]
            perturbed, kind = False, ""
            if perturbation_interval and perturbation_interval > 0 and trial_id % perturbation_interval == 0:
                perturbed, kind = True, random.choice(config["perturbation_types"])
            if block == "affect":
                level = "neutral"
            elif block == "belief":
                level = "confirmatory"
            else:
                level = random.choice(["confirmatory", "mildly_contradictory", "strongly_contradictory"])
            trials.append({
                "trial_id": trial_id, "framework_id": "TFL", "run_mode": config.get("run_mode", "default_tfl"),
                "block": block, "block_trial_num": block_trial_num,
                "stimulus_id": stimulus["stimulus_id"], "cue": stimulus["cue"],
                "ambiguous_text": stimulus["ambiguous_text"], "interpretation_a": stimulus["interpretation_a"],
                "interpretation_b": stimulus["interpretation_b"], "prior_instruction": prior,
                "feedback_level": level, "probe_trial": probe, "delayed_reentry": delayed,
                "recurrence_source_trial": source, "perturbation_trial": perturbed, "perturbation_type": kind,
            })
            trial_id += 1
    return trials


def answer(stage, engine):
    return {"cue": None, "prediction": "A", "affect": "50", "perturbation": None,
            "post_perturbation_probe": "U", "behavioral_choice": "B", "content_probe": "U"}[stage]


def drive(engine, max_steps=10_000):
    steps = 0
    while not engine.completed:
        stage = engine.active_stage()
        method = {
            "cue": engine.continue_cue, "prediction": engine.submit_prediction,
            "affect": engine.submit_affect, "perturbation": engine.continue_perturbation,
            "post_perturbation_probe": engine.submit_post_perturbation_probe,
            "behavioral_choice": engine.submit_behavioral_choice, "content_probe": engine.submit_content_probe,
        }[stage]
        value = answer(stage, engine)
        assert (method() if value is None else method(value))
        steps += 1
        assert steps < max_steps


def single_trial_engine(**flags):
    config = get_default_config()
    trial = build_trials(config, apply_stimulus_limit(load_stimuli(), config))[0]
    trial.update(probe_trial=flags.get("probe", False), delayed_reentry=flags.get("delayed", False),
                 perturbation_trial=flags.get("perturb", False),
                 perturbation_type="scene_shift" if flags.get("perturb") else "",
                 feedback_level=flags.get("level", "strongly_contradictory"))
    config.update(flags.get("config", {}))
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(config, [trial], timer)
    engine.start()
    return engine, timer


# ------------------------------------------------------------------ tests
class ReferenceParityTests(unittest.TestCase):
    def test_stimulus_library_matches_reference_csv(self):
        digest = hashlib.sha256(json.dumps(load_stimuli(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest, REFERENCE_STIMULI_SHA256)
        self.assertEqual(len(load_stimuli()), 60)

    def test_trial_generation_matches_reference_for_all_toggles_and_seeds(self):
        stimuli_all = load_stimuli()
        for flags in itertools.product([False, True], repeat=4):
            for seed in (0, 1, 2026, 9017):
                with self.subTest(flags=flags, seed=seed):
                    config = get_default_config()
                    config.update(zip(TOGGLES, flags))
                    config["random_seed"] = seed
                    update_run_mode(config)
                    stimuli = apply_stimulus_limit(stimuli_all, config)
                    self.assertEqual(build_trials(config, stimuli), reference_build_trials(config, stimuli))

    def test_builder_does_not_touch_global_random_state(self):
        random.seed(77)
        expected = random.random()
        random.seed(77)
        build_trials(get_default_config(), apply_stimulus_limit(load_stimuli(), get_default_config()))
        self.assertEqual(random.random(), expected)

    def test_defaults_match_reference(self):
        config = get_default_config()
        self.assertEqual(config["blocks"], ["affect", "belief", "contradiction"])
        self.assertEqual(config["trials_per_block"], 40)
        self.assertEqual([config[k] for k in TOGGLES], [False, False, True, True])
        self.assertFalse(config["enable_response_timer"])
        self.assertEqual(config["run_mode"], "default_tfl")
        self.assertEqual(len(build_trials(config, apply_stimulus_limit(load_stimuli(), config))), 120)

    def test_run_mode_labels(self):
        for key in TOGGLES + ["enable_response_timer"]:
            config = get_default_config()
            config[key] = not config[key]
            self.assertEqual(update_run_mode(config)["run_mode"], "modified_tfl", key)

    def test_schema_keeps_reference_columns_first(self):
        self.assertEqual(len(REFERENCE_FIELDNAMES), 27)
        self.assertEqual(TRIAL_FIELDNAMES[:27], REFERENCE_FIELDNAMES)
        self.assertEqual(TRIAL_FIELDNAMES[27:], ["response_timer_sec", "prediction_timed_out", "behavioral_timed_out"])

    def test_feedback_wording_and_outcomes(self):
        self.assertEqual(feedback.determine_feedback("A", "strongly_contradictory"), ("B", "strong"))
        self.assertEqual(feedback.determine_feedback("A", "neutral"), ("", "none"))
        self.assertEqual(feedback.feedback_text("confirmatory", "A", "A"),
                         "Feedback: Confirmed. Interpretation A was supported.")
        self.assertEqual(feedback.feedback_text("neutral", "A", ""), "Feedback: No outcome feedback on this trial.")
        self.assertEqual(feedback.make_perturbation_instruction("breath_reset"),
                         "Take one slow breath in and out before continuing.")


class ProcedureTests(unittest.TestCase):
    def test_stage_order_for_every_trial_variant(self):
        for probe, delayed, perturb in itertools.product([False, True], repeat=3):
            with self.subTest(probe=probe, delayed=delayed, perturb=perturb):
                engine, _ = single_trial_engine(probe=probe, delayed=delayed, perturb=perturb)
                seen = []
                while not engine.completed:
                    seen.append(engine.active_stage())
                    if engine.active_stage() == "content_probe":
                        self.assertIn("Strong contradiction", engine.current_feedback)
                    drive_step(engine)
                expected = ["cue", "prediction", "affect"]
                expected += ["perturbation", "post_perturbation_probe"] if perturb else []
                expected += ["behavioral_choice"] + (["content_probe"] if probe or delayed else [])
                self.assertEqual(seen, expected)
                self.assertIn("Strong contradiction", engine.last_feedback)
                row = engine.rows[0]
                self.assertEqual(list(row), TRIAL_FIELDNAMES)
                self.assertEqual((row["correct_answer"], row["contradiction"]), ("B", "strong"))
                if perturb:
                    self.assertEqual(row["post_perturbation_probe"], "U")
                    self.assertEqual(row["perturbation_match_prediction"], "")

    def test_affect_validation_matches_reference(self):
        engine, _ = single_trial_engine()
        engine.continue_cue()
        engine.submit_prediction("a")
        for bad in ("50.5", "-1", "101", "", "fifty", True, 50.0):
            self.assertFalse(engine.submit_affect(bad), bad)
        self.assertTrue(engine.submit_affect(" 50 "))
        self.assertEqual(engine.response["affect"], 50)

    def test_invalid_and_duplicate_choices_do_not_advance(self):
        engine, _ = single_trial_engine()
        self.assertFalse(engine.submit_prediction("A"))  # still on cue
        engine.continue_cue()
        self.assertFalse(engine.submit_prediction("U"))
        self.assertTrue(engine.submit_prediction("b"))
        self.assertFalse(engine.submit_prediction("A"))
        self.assertEqual(engine.response["prediction"], "B")

    def test_untimed_runs_have_no_deadline(self):
        engine, timer = single_trial_engine()
        engine.continue_cue()
        self.assertIsNone(engine.seconds_remaining())
        self.assertEqual(timer.callbacks, {})
        timer.advance(10_000)
        self.assertTrue(engine.submit_prediction("A"))
        self.assertEqual(engine.response["prediction_rt"], 10_000.0)

    def test_reaction_times_measured_from_prompt(self):
        engine, timer = single_trial_engine(probe=False)
        timer.advance(3)
        engine.continue_cue()
        timer.advance(2.5)
        engine.submit_prediction("A")
        engine.submit_affect("40")
        timer.advance(1.25)
        engine.submit_behavioral_choice("B")
        row = engine.rows[0]
        self.assertEqual((row["prediction_rt"], row["behavioral_rt"]), (2.5, 1.25))
        self.assertEqual((row["response_timer_sec"], row["prediction_timed_out"]), ("", False))

    def test_finish_is_idempotent(self):
        engine, _ = single_trial_engine()
        drive(engine)
        engine.finish_session()
        self.assertEqual(engine.completion_count(), 1)

    def test_full_default_session(self):
        recorded = []
        engine, _ = build_default_engine(on_trial_recorded=lambda row, rows: recorded.append(row["trial_id"]))
        drive(engine)
        self.assertEqual(recorded, list(range(1, 121)))


def drive_step(engine):
    stage = engine.active_stage()
    method = {
        "cue": engine.continue_cue, "prediction": engine.submit_prediction, "affect": engine.submit_affect,
        "perturbation": engine.continue_perturbation,
        "post_perturbation_probe": engine.submit_post_perturbation_probe,
        "behavioral_choice": engine.submit_behavioral_choice, "content_probe": engine.submit_content_probe,
    }[stage]
    value = answer(stage, engine)
    assert (method() if value is None else method(value))


class ResponseTimerTests(unittest.TestCase):
    def timed(self, seconds=12):
        return single_trial_engine(config={"enable_response_timer": True, "trial_duration_sec": seconds})

    def test_timeout_records_blank_and_advances(self):
        advanced = []
        engine, timer = self.timed()
        engine.on_stage_advanced = lambda: advanced.append(engine.active_stage())
        engine.continue_cue()
        self.assertEqual(engine.seconds_remaining(), 12)
        timer.fire(next(iter(timer.callbacks)))
        self.assertEqual(engine.active_stage(), "affect")
        self.assertTrue(engine.response["prediction_timed_out"])
        self.assertEqual(advanced, ["affect"])
        engine.submit_affect("10")
        timer.fire(next(iter(timer.callbacks)))
        row = engine.rows[0]
        self.assertEqual((row["prediction"], row["behavioral_choice"]), ("", ""))
        self.assertEqual((row["prediction_timed_out"], row["behavioral_timed_out"], row["response_timer_sec"]),
                         (True, True, 12))
        self.assertEqual(engine.last_feedback, "Feedback: No prediction was recorded before the time limit.")

    def test_submission_at_deadline_is_a_timeout(self):
        engine, timer = self.timed(5)
        engine.continue_cue()
        timer.advance(5)
        self.assertFalse(engine.submit_prediction("A"))
        self.assertEqual(engine.active_stage(), "affect")
        self.assertTrue(engine.response["prediction_timed_out"])

    def test_answer_before_deadline_is_recorded(self):
        engine, timer = self.timed(5)
        engine.continue_cue()
        timer.advance(4.99)
        self.assertTrue(engine.submit_prediction("A"))
        self.assertFalse(engine.response["prediction_timed_out"])

    def test_stale_callback_is_ignored(self):
        engine, timer = self.timed()
        engine.continue_cue()
        stale = timer.callbacks.copy()
        engine.submit_prediction("A")
        engine.submit_affect("20")
        for callback in stale.values():
            callback()
        self.assertEqual(engine.active_stage(), "behavioral_choice")

    def test_timer_seconds_are_clamped(self):
        engine, _ = self.timed(999)
        self.assertEqual(engine.timer_seconds, 120)


class OutputTests(unittest.TestCase):
    def test_rows_flushed_per_trial_and_published_on_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            engine, _ = build_default_engine(on_trial_recorded=writer.write_row)
            for _ in range(3):
                while len(engine.rows) < _ + 1:
                    drive_step(engine)
                with open(writer.session_file, newline="", encoding="utf-8") as f:
                    self.assertEqual(len(list(csv.DictReader(f))), _ + 1)
            self.assertFalse((Path(directory) / "tfl_output.csv").exists())
            drive(engine)
            latest = writer.finalize()
            writer.finalize()
            with open(latest, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.assertEqual(reader.fieldnames, TRIAL_FIELDNAMES)
                self.assertEqual(len(list(reader)), 120)

    def test_abandon_keeps_rows_and_leaves_latest_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            latest = Path(directory) / "tfl_output.csv"
            latest.write_text("previous run", encoding="utf-8")
            writer = SessionWriter(directory)
            engine, _ = build_default_engine(on_trial_recorded=writer.write_row)
            while len(engine.rows) < 2:
                drive_step(engine)
            engine.cancel()
            path = writer.abandon()
            self.assertEqual(latest.read_text(encoding="utf-8"), "previous run")
            with open(path, newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)

    def test_writer_failure_is_reported_not_fatal(self):
        def broken(row, rows):
            raise OSError("disk full")
        engine, _ = build_default_engine(on_trial_recorded=broken)
        while len(engine.rows) < 1:
            drive_step(engine)
        self.assertEqual(engine.record_errors, ["trial 1: OSError: disk full"])
        self.assertEqual(engine.active_stage(), "cue")


class AnalysisTests(unittest.TestCase):
    def write_csv(self, directory, rows):
        path = Path(directory) / "data.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=TRIAL_FIELDNAMES)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in TRIAL_FIELDNAMES})
        return path

    def test_completion_gate_uses_reference_rule(self):
        rows = [{"prediction": "A", "behavioral_choice": "B", "affect": "50"}] * 3 + \
               [{"prediction": "", "behavioral_choice": "B", "affect": "50"}]
        self.assertEqual(analysis.completion_gate(rows), (3, 3, True))
        rows = rows[:2] + [{"prediction": "", "behavioral_choice": "", "affect": ""}] * 3
        self.assertEqual(analysis.completion_gate(rows), (2, 4, False))

    def test_describe_matches_pandas_conventions(self):
        stats = analysis.describe([1, 2, 3, 4])
        self.assertEqual((stats["25%"], stats["50%"], stats["75%"]), (1.75, 2.5, 3.25))
        self.assertAlmostEqual(stats["std"], 1.2909944487358056)

    def test_full_report_from_real_session(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            engine, _ = build_default_engine({"enable_perturbations": True}, on_trial_recorded=writer.write_row)
            drive(engine)
            report = analysis.analyze_output(writer.finalize())
        for heading in ("Run Metadata", "Trial Counts", "Prediction and Behavior", "Affect and Reaction Time",
                        "Prior Consistency", "Contradiction", "Probes", "Delayed Reentry", "Perturbations",
                        "Completion Gate"):
            self.assertIn(heading, report)
        self.assertIn("PASS \u2014 120 / 120 usable trials", report)
        self.assertIn("Perturbation trial count:\n24", report)
        self.assertNotIn("Response Timer", report)

    def test_missing_file_message(self):
        self.assertIn("does not exist", analysis.analyze_output(Path(tempfile.gettempdir()) / "nope_tfl.csv"))


class CommandLineTests(unittest.TestCase):
    def scripted(self, answers_for):
        log = []

        def ask(prompt):
            log.append(prompt)
            return answers_for(prompt)
        return ask, log

    @staticmethod
    def default_answers(prompt):
        if "Selection" in prompt or "Press Enter" in prompt:
            return ""
        if "Predicted interpretation" in prompt:
            return "A"
        if "Affect intensity" in prompt:
            return "50"
        if "Final behavioral choice" in prompt:
            return "B"
        if "most active" in prompt:
            return "U"
        raise AssertionError(prompt)

    def test_full_default_cli_run(self):
        with tempfile.TemporaryDirectory() as directory:
            ask, _ = self.scripted(self.default_answers)
            output = []
            latest = cli_runner.run_cli(ask, output.append, output_dir=directory, timer=NullSchedulerTimer())
            with open(latest, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 120)
            self.assertEqual({r["run_mode"] for r in rows}, {"default_tfl"})
            self.assertTrue(any(line.startswith("Feedback: Strong contradiction") for line in output))
            self.assertIn("TFL Baseline Reference Implementation v2.6", output)

    def test_options_menu_toggles_and_timer(self):
        with tempfile.TemporaryDirectory() as directory:
            pending = ["O", "2", "6", "7", "20", "S", ""]

            def ask(prompt):
                if ("Selection" in prompt or "Choice" in prompt or "Seconds" in prompt) and pending:
                    return pending.pop(0)
                return self.default_answers(prompt)
            latest = cli_runner.run_cli(ask, lambda *a: None, output_dir=directory, timer=NullSchedulerTimer())
            with open(latest, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual({r["run_mode"] for r in rows}, {"modified_tfl"})
        self.assertEqual({r["response_timer_sec"] for r in rows}, {"20"})
        self.assertEqual(sum(r["perturbation_trial"] == "True" for r in rows), 24)

    def test_late_console_answer_counts_as_timeout(self):
        timer = NullSchedulerTimer()
        config = get_default_config()
        config.update(enable_response_timer=True, trial_duration_sec=5)

        def ask(prompt):
            if "Predicted interpretation" in prompt:
                timer.advance(6)
            return self.default_answers(prompt)
        with tempfile.TemporaryDirectory() as directory:
            output = []
            latest = cli_runner.run_cli(ask, output.append, output_dir=directory, timer=timer, config=config)
            with open(latest, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertTrue(all(r["prediction_timed_out"] == "True" and r["prediction"] == "" for r in rows))
        self.assertIn("Time limit reached. No response was recorded.", output)

    def test_interrupt_keeps_completed_trials(self):
        calls = {"n": 0}

        def ask(prompt):
            if "Final behavioral choice" in prompt:
                calls["n"] += 1
                if calls["n"] == 3:
                    raise KeyboardInterrupt
            return self.default_answers(prompt)
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(cli_runner.run_cli(ask, lambda *a: None, output_dir=directory, timer=NullSchedulerTimer()))
            files = sorted(Path(directory).glob("tfl_output_*.csv"))
            self.assertEqual(len(files), 1)
            self.assertFalse((Path(directory) / "tfl_output.csv").exists())
            with open(files[0], newline="", encoding="utf-8") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 2)

    def test_top_level_cli_commands(self):
        import cli
        self.assertEqual(cli.main(["list"]), 0)
        self.assertEqual(cli.main(["run", "NOPE"]), 1)
        self.assertEqual(cli.main(["run", "SST"]), 1)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "x.csv"
            self.assertEqual(cli.main(["analyze", "TFL", "--file", str(missing)]), 0)


class GuiAdapterTests(unittest.TestCase):
    def test_gui_adapter_with_widget_doubles(self):
        result = subprocess.run([sys.executable, str(ROOT / "tests" / "tfl_gui_doubles_check.py")],
                                cwd=ROOT, capture_output=True, text=True,
                                env={**os.environ, "APPDATA": tempfile.mkdtemp()})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GUI adapter double check passed", result.stdout)


class DependencyTests(unittest.TestCase):
    def test_every_import_is_stdlib_or_internal(self):
        internal = {p.name for p in ROOT.iterdir() if p.is_dir()} | {p.stem for p in ROOT.glob("*.py")}
        for path in ROOT.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else []
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    self.assertIn(name, sys.stdlib_module_names | internal, f"{path}: {name}")

    def test_headless_and_cli_paths_never_load_tkinter(self):
        code = ("import sys; import cli; from app.headless import build_default_engine; "
                "from frameworks.TFL import analysis, cli_runner, output; "
                "assert 'tkinter' not in sys.modules, 'tkinter loaded'")
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True,
                       env={**os.environ, "APPDATA": tempfile.mkdtemp()})


if __name__ == "__main__":
    unittest.main(verbosity=1)
