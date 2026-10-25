"""
File: tests/test_tfl.py

Purpose
-------
Prove that TFL reproduces the 02_Execution reference procedure with
default options, and test everything the Archive adds: the run options,
saving after every answer, never overwriting a file, AppData output,
standard-library analysis, the command line, and the GUI adapter.

Communication / relationships
-----------------------------
- Imports frameworks/TFL/ headless modules, cli.py, and config/runtime.py.
- Runs tests/gui_doubles_check.py in a separate interpreter.
- Never imports Tkinter itself.

Settings / parameters
---------------------
- APPDATA is redirected to a temporary folder before any project import,
  so tests never touch real settings or sessions.
- reference_build_trials() is a verbatim port of the reference
  algorithm using the process-wide random module; it is the oracle.
- REFERENCE_STIMULI_SHA256: digest of the reference tfl_stimuli.csv rows
  serialized as sorted-key JSON.

Edge cases
----------
- Console runs are scripted through input_fn/print_fn; timers use the
  virtual NullSchedulerTimer clock.

Known limitations
-----------------
- No native GUI rendering coverage.

Examples
--------
- python tests/test_tfl.py
"""
from __future__ import annotations

import ast
import csv
import hashlib
import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
APPDATA = tempfile.mkdtemp(prefix="brisart_tfl_test_")
os.environ["APPDATA"] = APPDATA

from config.runtime import get_tfl_output_dir  # noqa: E402
from frameworks.TFL import analysis, cli_runner, feedback  # noqa: E402
from frameworks.TFL.config import (  # noqa: E402
    OPTION_SPECS, get_default_config, resolve_run_config, restore_defaults, set_option, update_run_mode,
)
from frameworks.TFL.engine import TFLSessionEngine  # noqa: E402
from frameworks.TFL.headless import build_engine  # noqa: E402
from frameworks.TFL.output import SessionWriter, latest_session_file, list_session_files  # noqa: E402
from frameworks.TFL.schema import REFERENCE_FIELDNAMES, TRIAL_FIELDNAMES  # noqa: E402
from frameworks.TFL.stimuli import apply_stimulus_limit, load_stimuli  # noqa: E402
from frameworks.TFL.timing import NullSchedulerTimer  # noqa: E402
from frameworks.TFL.trial_builder import build_trials  # noqa: E402

REFERENCE_STIMULI_SHA256 = "ba4983fed0e170eaeb60c69fbd08fb236ba7c3789b6e79131b7c50fb5ba011e0"
TOGGLES = ["enable_extra_stimuli", "enable_perturbations", "enable_probes", "enable_delayed_reentry"]
ANSWERS = {
    "prediction": ("submit_prediction", "A"), "affect": ("submit_affect", "50"),
    "post_perturbation_probe": ("submit_post_perturbation_probe", "U"),
    "behavioral_choice": ("submit_behavioral_choice", "B"), "content_probe": ("submit_content_probe", "U"),
}


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


def step(engine) -> None:
    stage = engine.active_stage()
    if stage == "cue":
        assert engine.continue_cue()
    elif stage == "perturbation":
        assert engine.continue_perturbation()
    else:
        method, value = ANSWERS[stage]
        assert getattr(engine, method)(value)


def drive(engine) -> None:
    while not engine.completed:
        step(engine)


def read_csv(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def single_trial_engine(probe=False, delayed=False, perturb=False, options=None, on_progress=None):
    config = get_default_config()
    for key, value in (options or {}).items():
        set_option(config, key, value)
    run = resolve_run_config(config)
    trial = build_trials(run, apply_stimulus_limit(load_stimuli(), run))[0]
    trial.update(probe_trial=probe, delayed_reentry=delayed, perturbation_trial=perturb,
                 perturbation_type="scene_shift" if perturb else "", feedback_level="strongly_contradictory")
    timer = NullSchedulerTimer()
    engine = TFLSessionEngine(run, [trial], timer, on_progress=on_progress)
    engine.start()
    return engine, timer


class ReferenceParityTests(unittest.TestCase):
    def test_stimulus_library_matches_reference_csv(self):
        digest = hashlib.sha256(json.dumps(load_stimuli(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        self.assertEqual(digest, REFERENCE_STIMULI_SHA256)

    def test_trial_generation_matches_reference_for_all_toggles_and_seeds(self):
        for flags in itertools.product([False, True], repeat=4):
            for seed in (0, 1, 2026, 9017):
                with self.subTest(flags=flags, seed=seed):
                    config = get_default_config()
                    for key, flag in zip(TOGGLES, flags):
                        set_option(config, key, flag)
                    set_option(config, "random_seed", seed)
                    run = resolve_run_config(config)
                    stimuli = apply_stimulus_limit(load_stimuli(), run)
                    self.assertEqual(build_trials(run, stimuli), reference_build_trials(run, stimuli))

    def test_builder_does_not_touch_global_random_state(self):
        random.seed(77)
        expected = random.random()
        random.seed(77)
        run = resolve_run_config(get_default_config())
        build_trials(run, apply_stimulus_limit(load_stimuli(), run))
        self.assertEqual(random.random(), expected)

    def test_defaults_are_the_reference(self):
        run = resolve_run_config(get_default_config())
        self.assertEqual(run["blocks"], ["affect", "belief", "contradiction"])
        self.assertEqual((run["trials_per_block"], run["probe_interval"], run["delayed_reentry_interval"],
                          run["perturbation_interval"], run["random_seed"]), (40, 4, 6, 5, 2026))
        self.assertEqual([run[k] for k in TOGGLES], [False, False, True, True])
        self.assertFalse(run["enable_response_timer"] or run["shuffle_blocks"])
        self.assertEqual(run["run_mode"], "default_tfl")
        self.assertEqual(len(build_trials(run, apply_stimulus_limit(load_stimuli(), run))), 120)

    def test_schema(self):
        self.assertEqual(TRIAL_FIELDNAMES[:27], REFERENCE_FIELDNAMES)
        self.assertEqual(TRIAL_FIELDNAMES[27:], ["response_timer_sec", "prediction_timed_out", "behavioral_timed_out",
                                                 "session_label", "random_seed", "trial_status"])

    def test_feedback_wording(self):
        self.assertEqual(feedback.determine_feedback("A", "strongly_contradictory"), ("B", "strong"))
        self.assertEqual(feedback.determine_feedback("A", "neutral"), ("", "none"))
        self.assertEqual(feedback.feedback_text("confirmatory", "A", "A"), "Feedback: Confirmed. Interpretation A was supported.")


class OptionTests(unittest.TestCase):
    def test_every_protocol_option_marks_the_run_modified_and_label_does_not(self):
        changes = {
            "enable_perturbations": True, "enable_extra_stimuli": True, "enable_probes": False,
            "enable_delayed_reentry": False, "enable_response_timer": True, "trial_duration_sec": 20,
            "trials_per_block": 10, "blocks": "affect", "shuffle_blocks": True, "probe_interval": 3,
            "delayed_reentry_interval": 5, "perturbation_interval": 7, "random_seed": 5,
        }
        self.assertEqual(set(changes) | {"session_label"}, {spec.key for spec in OPTION_SPECS})
        for key, value in changes.items():
            config = get_default_config()
            self.assertTrue(set_option(config, key, value)[0], key)
            self.assertEqual(config["run_mode"], "modified_tfl", key)
        config = get_default_config()
        set_option(config, "session_label", "pilot 01")
        self.assertEqual((config["session_label"], config["run_mode"]), ("pilot_01", "default_tfl"))

    def test_invalid_values_are_rejected_and_leave_config_unchanged(self):
        for key, bad in (("trials_per_block", "0"), ("trials_per_block", "abc"), ("trial_duration_sec", "500"),
                         ("probe_interval", "0"), ("blocks", ""), ("blocks", "affect, nope"),
                         ("random_seed", "-1"), ("random_seed", "x"), ("session_label", "!!!"),
                         ("session_label", "x" * 41), ("enable_probes", "maybe")):
            with self.subTest(key=key, bad=bad):
                config = get_default_config()
                before = dict(config)
                ok, message = set_option(config, key, bad)
                self.assertFalse(ok)
                self.assertTrue(message)
                self.assertEqual(config, before)

    def test_trials_per_block_blocks_and_intervals_shape_the_run(self):
        config = get_default_config()
        for key, value in (("trials_per_block", 6), ("blocks", "belief, contradiction"), ("probe_interval", 2),
                           ("enable_perturbations", True), ("perturbation_interval", 3)):
            set_option(config, key, value)
        run = resolve_run_config(config)
        trials = build_trials(run, apply_stimulus_limit(load_stimuli(), run))
        self.assertEqual(len(trials), 12)
        self.assertEqual([t["block"] for t in trials], ["belief"] * 6 + ["contradiction"] * 6)
        self.assertEqual([t["trial_id"] for t in trials if t["probe_trial"]], [2, 4, 6, 8, 10, 12])
        self.assertEqual([t["trial_id"] for t in trials if t["perturbation_trial"]], [3, 6, 9, 12])

    def test_shuffled_blocks_are_reproducible_from_the_seed(self):
        orders = set()
        for seed in range(12):
            config = get_default_config()
            set_option(config, "shuffle_blocks", True)
            set_option(config, "random_seed", seed)
            run = resolve_run_config(config)
            first = build_trials(run, apply_stimulus_limit(load_stimuli(), run))
            second = build_trials(run, apply_stimulus_limit(load_stimuli(), run))
            self.assertEqual(first, second)
            order = tuple(dict.fromkeys(t["block"] for t in first))
            self.assertEqual(sorted(order), ["affect", "belief", "contradiction"])
            orders.add(order)
        self.assertGreater(len(orders), 1)

    def test_random_seed_is_drawn_per_run_and_recorded(self):
        config = get_default_config()
        set_option(config, "random_seed", "random")
        seeds = {resolve_run_config(config)["random_seed"] for _ in range(5)}
        self.assertGreater(len(seeds), 1)
        engine, _ = build_engine({"random_seed": "r"})
        drive(engine)
        self.assertEqual(len({row["random_seed"] for row in engine.rows}), 1)
        self.assertIsInstance(engine.rows[0]["random_seed"], int)
        self.assertEqual(engine.rows[0]["run_mode"], "modified_tfl")

    def test_restore_defaults_keeps_label(self):
        config = get_default_config()
        set_option(config, "trials_per_block", 9)
        set_option(config, "session_label", "p2")
        restored = restore_defaults(config)
        self.assertEqual((restored["trials_per_block"], restored["session_label"], restored["run_mode"]),
                         (40, "p2", "default_tfl"))


class ProcedureTests(unittest.TestCase):
    def test_stage_order_for_every_trial_variant(self):
        for probe, delayed, perturb in itertools.product([False, True], repeat=3):
            with self.subTest(probe=probe, delayed=delayed, perturb=perturb):
                engine, _ = single_trial_engine(probe, delayed, perturb)
                seen = []
                while not engine.completed:
                    seen.append(engine.active_stage())
                    if engine.active_stage() == "content_probe":
                        self.assertIn("Strong contradiction", engine.current_feedback)
                    step(engine)
                expected = ["cue", "prediction", "affect"] + (["perturbation", "post_perturbation_probe"] if perturb else [])
                expected += ["behavioral_choice"] + (["content_probe"] if probe or delayed else [])
                self.assertEqual(seen, expected)
                self.assertEqual(list(engine.rows[0]), TRIAL_FIELDNAMES)
                self.assertEqual(engine.rows[0]["trial_status"], "complete")

    def test_affect_validation_matches_reference(self):
        engine, _ = single_trial_engine()
        engine.continue_cue()
        engine.submit_prediction("a")
        for bad in ("50.5", "-1", "101", "", "fifty", True, 50.0):
            self.assertFalse(engine.submit_affect(bad), bad)
        self.assertTrue(engine.submit_affect(" 50 "))

    def test_untimed_runs_have_no_deadline_and_measure_rt(self):
        engine, timer = single_trial_engine()
        engine.continue_cue()
        self.assertIsNone(engine.seconds_remaining())
        timer.advance(10_000)
        self.assertTrue(engine.submit_prediction("A"))
        self.assertEqual(engine.response["prediction_rt"], 10_000.0)

    def test_timer_timeout_deadline_and_stale_callbacks(self):
        engine, timer = single_trial_engine(options={"enable_response_timer": True, "trial_duration_sec": 5})
        engine.continue_cue()
        stale = dict(timer.callbacks)
        timer.advance(4.99)
        self.assertTrue(engine.submit_prediction("A"))
        for callback in stale.values():
            callback()
        self.assertEqual(engine.active_stage(), "affect")
        engine.submit_affect("10")
        timer.advance(5)
        self.assertFalse(engine.submit_behavioral_choice("B"))
        row = engine.rows[0]
        self.assertEqual((row["behavioral_choice"], row["behavioral_timed_out"], row["response_timer_sec"]), ("", True, 5))

    def test_full_default_session(self):
        engine, _ = build_engine()
        drive(engine)
        self.assertEqual([row["trial_id"] for row in engine.rows], list(range(1, 121)))
        self.assertEqual(engine.completion_count(), 1)


class SavingTests(unittest.TestCase):
    def test_every_answer_is_saved_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            engine, _ = build_engine({"enable_perturbations": True}, on_progress=writer.save)
            answers = 0
            while not engine.completed:
                stage = engine.active_stage()
                step(engine)
                if stage in ANSWERS:
                    answers += 1
                    rows = read_csv(writer.path)
                    self.assertEqual(engine.saves, answers)
                    self.assertEqual(rows, [{k: str(v) for k, v in r.items()} for r in engine.snapshot()])
            self.assertEqual(len(read_csv(writer.path)), 120)
            self.assertEqual(engine.save_errors, [])

    def test_partial_trial_is_on_disk_after_a_single_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            engine, _ = single_trial_engine(on_progress=writer.save)
            engine.continue_cue()
            engine.submit_prediction("B")
            rows = read_csv(writer.path)
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["prediction"], rows[0]["affect"], rows[0]["trial_status"]), ("B", "", "in_progress"))
            engine.submit_affect("70")
            self.assertEqual(read_csv(writer.path)[0]["affect"], "70")

    def test_files_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            moment = datetime(2026, 10, 24, 18, 45, 12)
            existing = Path(directory) / "tfl_output_2026-10-24_18-45-12.csv"
            existing.write_text("earlier session", encoding="utf-8")
            first = SessionWriter(directory, started_at=moment)
            second = SessionWriter(directory, started_at=moment)
            self.assertEqual(existing.read_text(encoding="utf-8"), "earlier session")
            self.assertEqual(first.path.name, "tfl_output_2026-10-24_18-45-12_2.csv")
            self.assertEqual(second.path.name, "tfl_output_2026-10-24_18-45-12_3.csv")
            labelled = SessionWriter(directory, label="pilot01", started_at=moment)
            self.assertEqual(labelled.path.name, "tfl_output_pilot01_2026-10-24_18-45-12.csv")

    def test_file_name_ends_with_date_and_time(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            self.assertRegex(writer.path.name, r"^tfl_output_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(_\d+)?\.csv$")

    def test_default_output_is_in_appdata(self):
        expected = Path(APPDATA) / "Brisart Research Archive" / "outputs" / "TFL"
        self.assertEqual(get_tfl_output_dir(), expected)
        writer = SessionWriter()
        self.assertEqual(writer.path.parent, expected)
        writer.close()
        writer.path.unlink()

    def test_failed_save_is_recovered_by_the_next_save(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            failures = {"left": 1}

            def flaky(rows):
                if failures["left"]:
                    failures["left"] -= 1
                    raise PermissionError("file locked")
                writer.save(rows)
            engine, _ = single_trial_engine(on_progress=flaky)
            drive(engine)
            self.assertEqual(len(engine.save_errors), 1)
            self.assertIn("PermissionError", engine.save_errors[0])
            self.assertEqual(read_csv(writer.path)[0]["trial_status"], "complete")

    def test_closed_writer_refuses_saves_and_temp_files_are_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            writer.save([])
            writer.close()
            with self.assertRaises(RuntimeError):
                writer.save([])
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), [writer.path.name])

    def test_latest_session_is_the_most_recently_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            older = SessionWriter(directory, started_at=datetime(2026, 1, 1))
            newer = SessionWriter(directory, started_at=datetime(2026, 1, 2))
            os.utime(older.path, (1_000, 1_000))
            os.utime(newer.path, (2_000, 2_000))
            self.assertEqual(latest_session_file(directory), newer.path)
            self.assertEqual(list_session_files(directory), [older.path, newer.path])


class AnalysisTests(unittest.TestCase):
    def test_completion_gate_reference_rule(self):
        rows = [{"prediction": "A", "behavioral_choice": "B", "affect": "50"}] * 3 + \
               [{"prediction": "", "behavioral_choice": "B", "affect": "50"}]
        self.assertEqual(analysis.completion_gate(rows), (3, 3, True))

    def test_describe_matches_pandas_conventions(self):
        stats = analysis.describe([1, 2, 3, 4])
        self.assertEqual((stats["25%"], stats["50%"], stats["75%"]), (1.75, 2.5, 3.25))
        self.assertAlmostEqual(stats["std"], 1.2909944487358056)

    def test_report_from_real_session(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory, label="pilot")
            engine, _ = build_engine({"enable_perturbations": True, "session_label": "pilot"}, on_progress=writer.save)
            drive(engine)
            report = analysis.analyze_output(writer.path)
        for heading in ("Session", "Run Metadata", "Trial Counts", "Prediction and Behavior", "Affect and Reaction Time",
                        "Prior Consistency", "Contradiction", "Probes", "Delayed Reentry", "Perturbations", "Completion Gate"):
            self.assertIn(heading, report)
        self.assertIn("PASS \u2014 120 / 120 usable trials", report)
        self.assertIn("Session label: pilot", report)
        self.assertIn("Random seed: 2026", report)

    def test_interrupted_trial_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SessionWriter(directory)
            engine, _ = build_engine(on_progress=writer.save)
            while len(engine.rows) < 3:
                step(engine)
            engine.continue_cue()
            engine.submit_prediction("A")
            writer.close()
            report = analysis.analyze_output(writer.path)
        self.assertIn("Complete trials: 3", report)
        self.assertIn("Incomplete trials excluded: 1", report)
        self.assertIn("3 / 3 usable trials", report)

    def test_legacy_file_without_status_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tfl_output.csv"
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=REFERENCE_FIELDNAMES)
                writer.writeheader()
                writer.writerow({k: "" for k in REFERENCE_FIELDNAMES} | {"prediction": "A", "behavioral_choice": "B", "affect": "4"})
            self.assertIn("1 / 1 usable trials", analysis.analyze_output(path))

    def test_messages_for_missing_and_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn("does not exist", analysis.analyze_output(Path(directory) / "x.csv"))
            writer = SessionWriter(directory)
            self.assertIn("no completed trials", analysis.analyze_output(writer.path))


class CommandLineTests(unittest.TestCase):
    @staticmethod
    def answer(prompt):
        if "Selection" in prompt or "Press Enter" in prompt:
            return ""
        for key, value in (("Predicted interpretation", "A"), ("Affect intensity", "50"),
                           ("Final behavioral choice", "B"), ("most active", "U")):
            if key in prompt:
                return value
        raise AssertionError(prompt)

    def test_full_default_run(self):
        with tempfile.TemporaryDirectory() as directory:
            output = []
            path = cli_runner.run_cli(self.answer, output.append, output_dir=directory, timer=NullSchedulerTimer())
            rows = read_csv(path)
        self.assertEqual(len(rows), 120)
        self.assertEqual({r["run_mode"] for r in rows}, {"default_tfl"})
        self.assertIn("TFL Baseline Reference Implementation v2.6", output)
        self.assertTrue(any(line.startswith("Feedback: Strong contradiction") for line in output))

    def test_options_menu_drives_the_option_table(self):
        numbers = {spec.key: str(i) for i, spec in enumerate(OPTION_SPECS, start=2)}
        script = ["O", numbers["enable_perturbations"], numbers["enable_response_timer"],
                  numbers["trial_duration_sec"], "20", numbers["trials_per_block"], "5",
                  numbers["session_label"], "pilot02", numbers["trials_per_block"], "999", "S", ""]

        def ask(prompt):
            if script and any(k in prompt for k in ("Selection", "Choice", "Seconds", "Trials Per Block", "Response Timer", "label")):
                return script.pop(0)
            return self.answer(prompt)
        with tempfile.TemporaryDirectory() as directory:
            output = []
            path = cli_runner.run_cli(ask, output.append, output_dir=directory, timer=NullSchedulerTimer())
            rows = read_csv(path)
        self.assertTrue(path.name.startswith("tfl_output_pilot02_"))
        self.assertEqual(len(rows), 15)
        self.assertEqual({(r["run_mode"], r["response_timer_sec"], r["session_label"]) for r in rows},
                         {("modified_tfl", "20", "pilot02")})
        self.assertEqual(sum(r["perturbation_trial"] == "True" for r in rows), 3)
        self.assertTrue(any(line.startswith("\nNot changed: Trials Per Block must be from 1 to 200") for line in output))

    def test_late_console_answer_is_a_timeout(self):
        timer = NullSchedulerTimer()

        def ask(prompt):
            if "Predicted interpretation" in prompt:
                timer.advance(6)
            return self.answer(prompt)
        with tempfile.TemporaryDirectory() as directory:
            output = []
            path = cli_runner.run_cli(ask, output.append, output_dir=directory, timer=timer,
                                      options={"enable_response_timer": True, "trial_duration_sec": 5, "trials_per_block": 2})
            rows = read_csv(path)
        self.assertTrue(all(r["prediction_timed_out"] == "True" and r["prediction"] == "" for r in rows))
        self.assertIn("Time limit reached. No response was recorded.", output)

    def test_interrupt_keeps_every_answer(self):
        calls = {"n": 0}

        def ask(prompt):
            if "Affect intensity" in prompt:
                calls["n"] += 1
                if calls["n"] == 3:
                    raise KeyboardInterrupt
            return self.answer(prompt)
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(cli_runner.run_cli(ask, lambda *a: None, output_dir=directory, timer=NullSchedulerTimer()))
            files = list(Path(directory).glob("tfl_output_*.csv"))
            self.assertEqual(len(files), 1)
            rows = read_csv(files[0])
        self.assertEqual([r["trial_status"] for r in rows], ["complete", "complete", "in_progress"])
        self.assertEqual((rows[2]["prediction"], rows[2]["affect"]), ("A", ""))

    def test_top_level_commands(self):
        import cli
        self.assertEqual(cli.main(["where"]), 0)
        self.assertEqual(cli.main(["sessions"]), 0)
        self.assertEqual(cli.main(["analyze"]), 0)
        self.assertEqual(cli.main(["analyze", "--file", str(Path(APPDATA) / "missing.csv")]), 1)


class IsolationTests(unittest.TestCase):
    def test_gui_adapter_with_widget_doubles(self):
        result = subprocess.run([sys.executable, str(ROOT / "tests" / "gui_doubles_check.py")], cwd=ROOT,
                                capture_output=True, text=True, env={**os.environ, "APPDATA": tempfile.mkdtemp()})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("GUI adapter double check passed", result.stdout)

    def test_cli_and_headless_paths_never_load_tkinter(self):
        code = ("import sys; import cli; import frameworks.TFL.headless, frameworks.TFL.analysis, frameworks.TFL.output, frameworks.TFL.cli_runner; "
                "assert 'tkinter' not in sys.modules")
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True, env={**os.environ, "APPDATA": tempfile.mkdtemp()})


if __name__ == "__main__":
    unittest.main()
