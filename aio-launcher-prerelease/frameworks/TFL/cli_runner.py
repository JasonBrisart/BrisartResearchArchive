"""
File: frameworks/TFL/cli_runner.py

Purpose
-------
Run TFL in a terminal with the 02_Execution console flow (startup menu,
numbered options menu, intro, prompt-by-prompt trials) on top of the
shared TFLSessionEngine.

Communication / relationships
-----------------------------
- Called by cli.py through FRAMEWORK_METADATA["cli_module"] and
  ["cli_function"].
- Builds runs with config.py, stimuli.py, and trial_builder.py; records
  rows with output.SessionWriter; drives engine.TFLSessionEngine.
- Uses engine/timing.DeadlineOnlyTimer when the response timer is on.

Settings / parameters
---------------------
- run_cli(input_fn=input, print_fn=print, output_dir=None, timer=None,
  config=None) -> Path | None. config pre-sets options (used by tests
  and automation); None starts from the Default TFL options.
- Options menu: 1 restore defaults, 2 perturbations, 3 extra stimuli,
  4 probes, 5 delayed reentry, 6 response timer, 7 timer seconds,
  S save and return.

Edge cases
----------
- Invalid entries repeat the prompt with the reference messages.
- With the timer on, a console answer typed after the limit is recorded
  as a timeout, because blocking console input cannot be interrupted.
- Ctrl+C or end-of-input stops the run; completed trials stay in the
  session file and tfl_output.csv is not replaced.

Known limitations
-----------------
- The CLI cannot show a live countdown; the limit is printed with each
  timed prompt.

Examples
--------
- python cli.py run TFL
- run_cli(input_fn=scripted_answers, print_fn=log.append, output_dir=tmp)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from engine.timing import DeadlineOnlyTimer, TimerInterface

from . import settings
from .config import (
    apply_default_options,
    describe_current_options,
    format_run_mode,
    normalize_timer_seconds,
    update_run_mode,
)
from .engine import TFLSessionEngine
from .output import SessionWriter
from .stimuli import apply_stimulus_limit, load_stimuli
from .trial_builder import build_trials

RULE = "-" * 80


def startup_menu(ask, say) -> str:
    say("\n" + RULE)
    say(settings.VERSION_LABEL)
    say(RULE)
    say("Default settings:")
    for line in settings.DEFAULT_MODE_DESCRIPTION:
        say(f"- {line}")
    say("")
    say("Press ENTER to start experiment")
    say("Press O for Options")
    say("Press Q to return")
    return ask("\nSelection: ").strip().upper()


def options_menu(config: dict, ask, say) -> dict:
    config = update_run_mode(dict(config))
    toggles = {
        "2": ("enable_perturbations", "Perturbations are now"),
        "3": ("enable_extra_stimuli", "Extra Stimuli are now"),
        "4": ("enable_probes", "Probes are now"),
        "5": ("enable_delayed_reentry", "Delayed Reentry is now"),
        "6": ("enable_response_timer", "Response Timer is now"),
    }
    while True:
        say("\n" + "=" * 80)
        say(f"{settings.FRAMEWORK_ID} OPTIONS MENU")
        say("=" * 80)
        say("\nCurrent Settings")
        say("-" * 60)
        for line in describe_current_options(config):
            say(line)
        say("\nOptions")
        say("-" * 60)
        say("1. Restore Default Settings")
        say("2. Toggle Perturbations")
        say("3. Toggle Extra Stimuli")
        say("4. Toggle Probes")
        say("5. Toggle Delayed Reentry")
        say("6. Toggle Response Timer")
        say("7. Set Response Timer Seconds")
        say("\nS. Save and Return")
        choice = ask("\nChoice: ").strip().upper()
        if choice == "1":
            config = apply_default_options(config)
            say("\nDefault settings restored.")
        elif choice in toggles:
            key, label = toggles[choice]
            config[key] = not config.get(key, False)
            say(f"\n{label} {'ON' if config[key] else 'OFF'}.")
        elif choice == "7":
            seconds = normalize_timer_seconds(ask(
                f"Seconds per timed response ({settings.RESPONSE_TIMER_MIN_SEC}-{settings.RESPONSE_TIMER_MAX_SEC}): "
            ))
            config["trial_duration_sec"] = seconds
            say(f"\nResponse timer limit set to {seconds} seconds.")
        elif choice == "S":
            say("\nOptions saved for this run.")
            return update_run_mode(config)
        else:
            say("Invalid choice. Please select 1-7 or S.")
        update_run_mode(config)


def print_intro(config: dict, stimuli: list[dict], say) -> None:
    say("\n" + RULE)
    say(settings.VERSION_LABEL)
    say(RULE)
    say(settings.SESSION_INTRO_TEXT)
    say("\nCurrent run configuration:")
    say(RULE)
    say(f"Stimuli Available: {len(stimuli)}")
    for line in describe_current_options(config):
        say(line)
    say(RULE)
    if config.get("enable_perturbations", False):
        say("Some trials include a brief perturbation step.")
    else:
        say("No perturbation trials will be presented in this run.")
    if config.get("enable_response_timer", False):
        say(f"Predictions and behavioral choices must be entered within "
            f"{normalize_timer_seconds(config.get('trial_duration_sec'))} seconds.")
    say("")


def _ask_choice(engine, stage, prompt, submit, allowed, ask, say) -> None:
    while engine.active_stage() == stage:
        if engine.timer_enabled and stage in {"prediction", "behavioral_choice"}:
            say(f"(Time limit: {engine.timer_seconds} seconds)")
        if submit(ask(prompt)):
            return
        if engine.active_stage() != stage:
            say("Time limit reached. No response was recorded.")
            return
        say(f"Please enter one of: {', '.join(allowed)}")


def run_trials(engine: TFLSessionEngine, ask, say) -> None:
    while not engine.completed:
        stage = engine.active_stage()
        trial = engine.current_trial
        if stage == "cue":
            say("\n" + "=" * 60)
            say(f"Trial {trial['trial_id']} / {len(engine.trials)}")
            say(f"Framework: {trial['framework_id']}")
            say(f"Mode: {format_run_mode(trial['run_mode'])}")
            say(f"Block: {trial['block']}")
            say(f"Cue/context: {trial['cue']}")
            say(f"Prior instruction: Interpretation {trial['prior_instruction']} is more likely.")
            ask("\nPress Enter to view the stimulus...")
            engine.continue_cue()
            say("\nAmbiguous stimulus:")
            say(trial["ambiguous_text"])
            say("\nInterpretation A:")
            say(trial["interpretation_a"])
            say("\nInterpretation B:")
            say(trial["interpretation_b"])
        elif stage == "prediction":
            _ask_choice(engine, stage, settings.PREDICTION_PROMPT, engine.submit_prediction, ["A", "B"], ask, say)
        elif stage == "affect":
            if not engine.submit_affect(ask("Affect intensity for this prediction (0\u2013100): ")):
                say(f"Please enter a whole number from {settings.AFFECT_MIN} to {settings.AFFECT_MAX}.")
        elif stage == "perturbation":
            say("\nPerturbation step:")
            say(engine.perturbation_instruction())
            ask("Press Enter once completed...")
            engine.continue_perturbation()
        elif stage == "post_perturbation_probe":
            _ask_choice(engine, stage,
                        "Which interpretation is most active immediately after the perturbation? (A/B/U): ",
                        engine.submit_post_perturbation_probe, ["A", "B", "U"], ask, say)
        elif stage == "behavioral_choice":
            recorded = len(engine.rows)
            _ask_choice(engine, stage, "Final behavioral choice (A/B): ",
                        engine.submit_behavioral_choice, ["A", "B"], ask, say)
            text = engine.current_feedback if engine.active_stage() == "content_probe" else (
                engine.last_feedback if len(engine.rows) > recorded else "")
            if text:
                say(text)
        elif stage == "content_probe":
            say("\nProbe:")
            _ask_choice(engine, stage,
                        "Which interpretation is most active in your mind right now? (A/B/U for uncodable): ",
                        engine.submit_content_probe, ["A", "B", "U"], ask, say)
        else:
            raise RuntimeError(f"Unexpected TFL stage: {stage}")


def run_cli(
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[..., None] = print,
    output_dir: Path | str | None = None,
    timer: TimerInterface | None = None,
    config: dict | None = None,
) -> Path | None:
    say = print_fn
    config = apply_default_options() if config is None else update_run_mode({**apply_default_options(), **config})
    try:
        while True:
            selection = startup_menu(input_fn, say)
            if selection == "Q":
                return None
            if selection == "O":
                config = options_menu(config, input_fn, say)
                continue
            break
    except (KeyboardInterrupt, EOFError):
        say("\nTFL run cancelled before it started.")
        return None

    config = update_run_mode(config)
    stimuli = apply_stimulus_limit(load_stimuli(), config)
    trials = build_trials(config, stimuli)
    writer = SessionWriter(output_dir)
    engine = TFLSessionEngine(config, trials, timer or DeadlineOnlyTimer(), on_trial_recorded=writer.write_row)
    print_intro(config, stimuli, say)
    engine.start()
    try:
        run_trials(engine, input_fn, say)
    except (KeyboardInterrupt, EOFError):
        engine.cancel()
        path = writer.abandon()
        say(f"\nTFL run interrupted. {len(engine.rows)} completed trial(s) were kept in: {path}")
        return None
    latest = writer.finalize()
    if engine.record_errors:
        say("\nWarning: some trials could not be written:")
        for error in engine.record_errors:
            say(f"- {error}")
    say(f"\nExperiment complete. Data saved to: {latest}")
    say(f"Session file: {writer.session_file}")
    return latest


__all__ = ["run_cli", "startup_menu", "options_menu", "run_trials"]
