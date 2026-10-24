# Brisart Research Archive — AIO Launcher architecture (0.9.3 ALPHA)

## Principles

- **Standard library only.** No third-party packages. Tkinter is the only GUI toolkit and is imported only by GUI modules; the command line, the TFL engine, output, and analysis never import it.
- **One protocol, many front ends.** TFL behavior lives in one engine. The GUI and the CLI are thin drivers that display engine state and forward input; neither decides what happens next.
- **The reference is the specification.** The 02_Execution TFL Baseline Reference Implementation v2.6 defines trial generation, procedure, wording, row contents, and analysis rules. Archive additions (the optional response timer, per-session files, the GUI, the CLI) are opt-in or presentation-only and are named as such.

## Layer ownership

| Path | Responsibility |
| --- | --- |
| `main.py` | Entry point. GUI by default; `--cli` forwards to `cli.py` without importing Tk. |
| `cli.py` | Command-line suite: numbered menu plus `list`, `run`, `analyze`, `where` subcommands. Uses framework metadata only. |
| `app/headless.py` | Builds a started TFL engine on a virtual clock for tests and automation. |
| `config/` | Settings persistence, output folders, framework registry, page registry, GUI state, activity log. |
| `controllers/` | GUI application actions and logging. |
| `engine/timing.py` | Timer contract: `MonotonicTimer` (GUI), `DeadlineOnlyTimer` (console), `NullSchedulerTimer` (tests). |
| `frameworks/TFL/settings.py` | Every tunable TFL value. Reference defaults; timer off. |
| `frameworks/TFL/config.py` | Run configuration, default/modified labelling, shared "Current Settings" text. |
| `frameworks/TFL/stimuli.py` | Embedded 60-item library, text identical to the reference CSV. |
| `frameworks/TFL/trial_builder.py` | Reference trial algorithm on a private `random.Random(seed)`. |
| `frameworks/TFL/feedback.py` | Feedback outcomes, feedback sentences, perturbation instructions (reference wording). |
| `frameworks/TFL/engine.py` | `TFLSessionEngine`: the trial state machine, validation, timer, row construction. |
| `frameworks/TFL/schema.py` | 27 reference columns, then 3 timer columns. |
| `frameworks/TFL/output.py` | `SessionWriter`: one flushed row per trial into a session file; publishes `tfl_output.csv` on completion. |
| `frameworks/TFL/analysis.py` | Standard-library port of the reference analysis report and completion gate. |
| `frameworks/TFL/cli_runner.py` | Console driver: startup menu, numbered options menu, prompt-by-prompt trials. |
| `frameworks/TFL/options_screen.py`, `screen.py`, `session_gui.py` | GUI driver: options screen, stage screens, session lifecycle. |
| `frameworks/shared/schema.py` | Legacy import path for the TFL schema. |
| `gui/` | Host window, pages, components, theme. |
| `services/` | Framework launching, TFL analysis bridge for the GUI, signing, updater. |
| `tests/` | `test_merged.py` (host, registry, headers, updater) and `test_tfl_protocol.py` (TFL parity, timer, output, analysis, CLI, GUI doubles, dependency audit). |

## Framework contract

`FRAMEWORK_METADATA` in `frameworks/<ID>/framework.py` declares `runner_module`/`runner_class` (GUI), `cli_module`/`cli_function` (command line), `analysis_module` (exposes `analyze_output(path=None)`), and `results_filename`. Frameworks without a CLI runner are listed by the CLI and refused with a message. Framework modules are trusted local code, not sandboxed plug-ins.

## TFL session flow

```
options (defaults = reference) ──► build_trials(config, stimuli) ──► SessionWriter(output_dir)
                                                                     │
TFLSessionEngine ◄── GUI (screen.py) or CLI (cli_runner.py) input ───┘
  per trial: cue → prediction → affect → [perturbation → post-perturbation probe]
             → behavioral choice → (feedback computed) → [content probe] → row recorded
  row recorded ─► on_trial_recorded ─► SessionWriter.write_row (flush + fsync)
  completion   ─► SessionWriter.finalize ─► tfl_output.csv
  cancel       ─► SessionWriter.abandon  ─► session file kept, tfl_output.csv untouched
```

Feedback has no acknowledgement step. The GUI shows it with the content probe on probe trials, otherwise on the next trial's cue screen or the completion screen; the CLI prints it immediately after the behavioral choice, as the reference does.

## Response timer (optional)

On by default. When enabled from either options menu, prediction and behavioral choice each get `trial_duration_sec` seconds (3–120, default 12). Expiry records a blank response, sets the matching `*_timed_out` column, and advances. Any timer use labels the run `modified_tfl`. The GUI expires stages live through `MonotonicTimer`; the CLI cannot interrupt blocking console input, so `DeadlineOnlyTimer` treats an answer typed after the limit as a timeout.

## Output files

Per run: `tfl_output_<YYYYmmdd_HHMMSS_ffffff>.csv` in `<output folder>/TFL`, written row by row. A completed run atomically replaces `tfl_output.csv` with a copy of its session file; analysis defaults to that file. Earlier sessions are never overwritten.

## Testing boundaries

All automated tests run without Tk and without network access. GUI wiring is exercised with widget doubles in a separate interpreter; native rendering, focus, key bindings, and window management require a manual run on a machine with Tk. Updater network paths, real signing keys, and Windows executable swapping are not exercised.
