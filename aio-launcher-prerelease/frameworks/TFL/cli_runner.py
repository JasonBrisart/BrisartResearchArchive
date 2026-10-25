"""
File: frameworks/TFL/cli_runner.py

Purpose
-------
Run TFL in a terminal with the 02_Execution console flow: startup menu,
numbered options menu, session intro, and prompt-by-prompt trials, on
top of the same engine and saving the GUI uses.

Communication / relationships
-----------------------------
- Called by cli.py ("run", or menu item 1).
- Builds runs with frameworks/TFL/config.py, frameworks/TFL/stimuli.py, and
  frameworks/TFL/trial_builder.py; drives frameworks/TFL/engine.TFLSessionEngine; saves with
  frameworks/TFL/output.SessionWriter after every answer.
- Uses frameworks/TFL/timing.DeadlineOnlyTimer when the response timer is on.

Settings / parameters
---------------------
- run_cli(input_fn=input, print_fn=print, output_dir=None, timer=None,
  options=None) -> Path | None. options pre-sets values through
  set_option() (used by tests and automation).
- Options menu: 1 restores defaults; 2 onward follow OPTION_SPECS, so 2
  to 5 are perturbations, extra stimuli, probes, and delayed reentry as
  in the reference, then the Archive options; S saves and returns.

Edge cases
----------
- Invalid answers repeat the prompt with the reference messages; invalid
  option values print the reason and leave the option unchanged.
- With the timer on, an answer typed after the limit is recorded as a
  timeout, because blocking console input cannot be interrupted.
- Unknown startup selections repeat the menu rather than starting a run.
- Ctrl+C or end-of-input stops the run; every answer already given is
  in the CSV.
- A failed save is printed as a warning immediately; the run continues.

Known limitations
-----------------
- No live countdown in the console; the limit is printed with each
  timed prompt.

Examples
--------
- python cli.py run
- run_cli(input_fn=scripted, print_fn=log.append, output_dir=tmp)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import settings
from .config import (
    OPTION_SPECS,
    default_mode_description,
    describe_current_options,
    format_run_mode,
    get_default_config,
    resolve_run_config,
    restore_defaults,
    set_option,
    toggle_option,
)
from .engine import TFLSessionEngine
from .output import SessionWriter
from .stimuli import apply_stimulus_limit, load_stimuli
from .timing import DeadlineOnlyTimer, TimerInterface
from .trial_builder import build_trials

RULE = "-" * 80
VALUE_PROMPTS = {
    "int": lambda spec: f"{spec.label} ({spec.minimum}-{spec.maximum}): ",
    "blocks": lambda spec: "Blocks to run, separated by commas (affect, belief, contradiction): ",
    "seed": lambda spec: f"Random seed (0-{settings.SEED_MAX}, or R for a new random seed each run): ",
    "text": lambda spec: "Session label (letters, digits, - and _; blank for none): ",
}


def startup_menu(ask, say) -> str:
    say("\n" + RULE)
    say(settings.VERSION_LABEL)
    say(RULE)
    say("Default settings:")
    for line in default_mode_description():
        say(f"- {line}")
    say("")
    say("Press ENTER to start experiment")
    say("Press O for Options")
    say("Press Q to return")
    return ask("\nSelection: ").strip().upper()


def options_menu(config: dict, ask, say) -> dict:
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
        for number, spec in enumerate(OPTION_SPECS, start=2):
            verb = "Toggle" if spec.kind == "toggle" else "Set"
            say(f"{number}. {verb} {spec.label}")
        say("\nS. Save and Return")
        choice = ask("\nChoice: ").strip().upper()
        if choice == "S":
            say("\nOptions saved for this run.")
            return config
        if choice == "1":
            config = restore_defaults(config)
            say("\nDefault settings restored.")
            continue
        if not choice.isdigit() or not 2 <= int(choice) < 2 + len(OPTION_SPECS):
            say(f"Invalid choice. Please select 1-{1 + len(OPTION_SPECS)} or S.")
            continue
        spec = OPTION_SPECS[int(choice) - 2]
        if spec.kind == "toggle":
            ok, message = toggle_option(config, spec.key)
        else:
            ok, message = set_option(config, spec.key, ask(VALUE_PROMPTS[spec.kind](spec)))
        say(f"\n{message}" if ok else f"\nNot changed: {message}")


def print_intro(config: dict, stimuli: list[dict], path: Path, say) -> None:
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
    if config.get("enable_perturbations"):
        say("Some trials include a brief perturbation step.")
    else:
        say("No perturbation trials will be presented in this run.")
    if config.get("enable_response_timer"):
        say(f"Predictions and behavioral choices must be entered within {config['trial_duration_sec']} seconds.")
    say(f"Every answer is saved to: {path}")
    say("")


class ConsoleDriver:
    def __init__(self, engine: TFLSessionEngine, ask, say):
        self.engine, self.ask, self.say = engine, ask, say
        self.reported = 0

    def warn_save_errors(self) -> None:
        for error in self.engine.save_errors[self.reported:]:
            self.say(f"WARNING: could not save ({error}). Your answers are kept and will be saved again on the next answer.")
        self.reported = len(self.engine.save_errors)

    def ask_choice(self, stage, prompt, submit, allowed) -> None:
        engine = self.engine
        while engine.active_stage() == stage:
            if engine.timer_enabled and stage in {"prediction", "behavioral_choice"}:
                self.say(f"(Time limit: {engine.timer_seconds} seconds)")
            if submit(self.ask(prompt)):
                return
            if engine.active_stage() != stage:
                self.say("Time limit reached. No response was recorded.")
                return
            self.say(f"Please enter one of: {', '.join(allowed)}")

    def show_cue(self, trial) -> None:
        say = self.say
        say("\n" + "=" * 60)
        say(f"Trial {trial['trial_id']} / {len(self.engine.trials)}")
        say(f"Framework: {trial['framework_id']}")
        say(f"Mode: {format_run_mode(trial['run_mode'])}")
        say(f"Block: {trial['block']}")
        say(f"Cue/context: {trial['cue']}")
        say(f"Prior instruction: Interpretation {trial['prior_instruction']} is more likely.")
        self.ask("\nPress Enter to view the stimulus...")
        self.engine.continue_cue()
        for title, key in (("Ambiguous stimulus:", "ambiguous_text"), ("Interpretation A:", "interpretation_a"),
                           ("Interpretation B:", "interpretation_b")):
            say(f"\n{title}")
            say(trial[key])

    def run(self) -> None:
        engine, say = self.engine, self.say
        while not engine.completed:
            stage, trial = engine.active_stage(), engine.current_trial
            if stage == "cue":
                self.show_cue(trial)
            elif stage == "prediction":
                self.ask_choice(stage, settings.PREDICTION_PROMPT, engine.submit_prediction, ["A", "B"])
            elif stage == "affect":
                if not engine.submit_affect(self.ask(settings.AFFECT_PROMPT)):
                    say(f"Please enter a whole number from {settings.AFFECT_MIN} to {settings.AFFECT_MAX}.")
            elif stage == "perturbation":
                say("\nPerturbation step:")
                say(engine.perturbation_instruction())
                self.ask("Press Enter once completed...")
                engine.continue_perturbation()
            elif stage == "post_perturbation_probe":
                self.ask_choice(stage, settings.POST_PERTURBATION_PROMPT,
                                engine.submit_post_perturbation_probe, ["A", "B", "U"])
            elif stage == "behavioral_choice":
                completed_before = len(engine.rows)
                self.ask_choice(stage, settings.BEHAVIORAL_PROMPT, engine.submit_behavioral_choice, ["A", "B"])
                text = engine.current_feedback if engine.active_stage() == "content_probe" else (
                    engine.last_feedback if len(engine.rows) > completed_before else "")
                if text:
                    say(text)
            elif stage == "content_probe":
                say("\nProbe:")
                self.ask_choice(stage, settings.CONTENT_PROBE_PROMPT, engine.submit_content_probe, ["A", "B", "U"])
            else:
                raise RuntimeError(f"Unexpected TFL stage: {stage}")
            self.warn_save_errors()


def run_cli(
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[..., None] = print,
    output_dir: Path | str | None = None,
    timer: TimerInterface | None = None,
    options: dict | None = None,
) -> Path | None:
    say = print_fn
    config = get_default_config()
    for key, value in (options or {}).items():
        ok, message = set_option(config, key, value)
        if not ok:
            raise ValueError(message)
    try:
        while True:
            selection = startup_menu(input_fn, say)
            if selection == "Q":
                return None
            if selection == "O":
                config = options_menu(config, input_fn, say)
                continue
            if selection == "":
                break
            say("Invalid choice. Press ENTER, O, or Q.")
    except (KeyboardInterrupt, EOFError):
        say("\nTFL run cancelled before it started.")
        return None

    run = resolve_run_config(config)
    stimuli = apply_stimulus_limit(load_stimuli(), run)
    writer = SessionWriter(output_dir, label=run["session_label"])
    engine = TFLSessionEngine(run, build_trials(run, stimuli), timer or DeadlineOnlyTimer(), on_progress=writer.save)
    print_intro(run, stimuli, writer.path, say)
    engine.start()
    try:
        ConsoleDriver(engine, input_fn, say).run()
    except (KeyboardInterrupt, EOFError):
        engine.cancel()
        path = writer.close()
        say(f"\nTFL run stopped. {len(engine.rows)} complete trial(s) and every answer since are saved in: {path}")
        return None
    path = writer.close()
    say(f"\nExperiment complete. {writer.rows_saved} trials saved to: {path}")
    return path


__all__ = ["run_cli", "startup_menu", "options_menu"]
