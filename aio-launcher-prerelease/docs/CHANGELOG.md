# Changelog
All notable changes to Brisart Research Archive are documented here.

---

## [0.9.3 ALPHA] - 2026-10-24

### Release overview

TFL now runs the 02_Execution TFL Baseline Reference Implementation v2.6 procedure natively inside the Archive. The reference was not copied in or wrapped. Its behavior was rebuilt in the Archive's own modules: one front-end-independent engine, driven by a rebuilt GUI and by a new command-line suite modeled on the 02_Execution launcher. Trial generation, stimulus text, the trial sequence, feedback and perturbation wording, the 27 reference CSV columns, and the analysis rules all follow the reference. Its features that 0.9.2 lacked are now present.

The whole application is standard library only. The reference's pandas analysis was ported to plain Python, and the dependency audit now fails on any third-party import anywhere in the tree. Tkinter is imported only by GUI modules, so the CLI also runs on Python builds without Tk.

The Archive adds three things the reference does not have: an optional response timer, per-session output files, and the GUI/CLI front ends. With the timer off (the default), a run follows the reference procedure.

Verification: 53 automated tests pass on Python 3.12 without Tk (`tests/test_merged.py` 19, `tests/test_tfl_protocol.py` 34). Native Tk rendering was not exercised.

### Changed: trial generation now matches the reference (`frameworks/TFL/trial_builder.py`)

0.9.2 used a different algorithm: a shuffled stimulus pool, an alternating A/B prior only in the belief block, a fixed contradiction cycle, and a rotating perturbation order. The builder now uses the reference algorithm. For each trial it draws a random stimulus (with replacement), then a random A/B prior in every block, then a random perturbation type on perturbation trials, then a random contradiction-block feedback level, all from the same seed and in the reference's draw order. Delayed reentry is block-local and copies the stimulus from six trials back. Run length is `trials_per_block × len(blocks)`, and `num_trials` is informational, as in the reference.

The one deliberate difference is how the seed is used. Draws come from a private `random.Random(seed)` instead of the reference's process-wide `random.seed()`, so building trials no longer changes random state elsewhere in the application. A test compares every trial dictionary against a verbatim port of the reference algorithm for all 16 option combinations at seeds 0, 1, 2026, and 9017 (64 configurations). The sequences are identical, and a separate test confirms the global random state is untouched.

### Changed: settings, defaults, and stimulus text (`settings.py`, `config.py`, `stimuli.py`)

`settings.py` now holds the reference identity and wording: "TFL Baseline Reference Implementation v2.6", the session intro with its en dash, and the prediction prompt. Defaults are the reference's: three 40-trial blocks, probes every 4th trial, delayed reentry every 6th trial within a block, perturbations every 5th trial when enabled, seed 2026, and the first 20 stimuli. `AUTOSAVE_INTERVAL_TRIALS`, `VALID_BLOCKS`, and `VALID_FEEDBACK_LEVELS` were removed because nothing uses them now.

`config.py` follows the reference option rules. Restoring defaults resets every run option but keeps structural values. A run is labelled `default_tfl` only when all options are at their defaults, otherwise `modified_tfl`. The "Current Settings" text is now generated in one place and shared by both front ends.

The embedded 60-item library in `stimuli.py` now matches the reference `tfl_stimuli.csv` character for character. That includes the typographic apostrophes in S014, S024, S032, S037, S042, S050, and S059, which 0.9.2 had replaced with straight quotes. A test compares the library against a SHA-256 digest of the reference CSV rows.

### Changed: feedback and perturbation wording (`frameworks/TFL/feedback.py`)

`determine_feedback()` uses the reference semantics: neutral and unknown levels return `("", "none")`. 0.9.2 returned `("", "")` for blank predictions and the prediction itself for unknown levels. The new `feedback_text()` returns the reference sentences ("Feedback: Confirmed. Interpretation A was supported.", and the mild and strong contradiction forms). Perturbation instructions are the reference texts. The only non-reference sentence is "Feedback: No prediction was recorded before the time limit.", which replaces a sentence with an empty interpretation letter and can only appear when the optional timer has expired.

### Changed: the session engine (`frameworks/TFL/engine.py`)

`TFLSessionEngine` was rebuilt around the reference trial sequence. Each trial runs:

1. Cue and prior.
2. View stimulus.
3. Prediction (A/B).
4. Affect.
5. Optional perturbation instruction, then the A/B/U post-perturbation probe.
6. Behavioral choice (A/B).
7. Feedback.
8. Optional A/B/U content probe.
9. Row recorded.

Compared with 0.9.2:

- **Cue stage:** 0.9.2 showed the stimulus immediately. The new cue stage is the GUI and CLI equivalent of the reference's "Press Enter to view the stimulus".
- **Feedback:** 0.9.2 never presented feedback to the participant. It is now computed after the behavioral choice and shown before the content probe, with no acknowledgement step.
- **Perturbation:** the instruction is now its own step, followed by its probe. In 0.9.2 the instruction was shown on every stage of a perturbation trial.
- **Affect:** a whole number from 0 to 100, entered with `int(text.strip())` as in the reference. "50.5", blanks, and booleans are rejected. The 0.9.2 slider, which pre-filled 50 and let a participant continue without answering, is gone.
- **Untimed by default:** prediction and behavioral choice wait for a valid answer. 0.9.2 always enforced a 12-second limit.

Reaction times run from the moment each prompt appears to the answer, rounded to four decimals, as in the reference, but use the monotonic clock instead of `time.time()`. Timer generations increase for the engine's lifetime, so a stale timer callback can never act on a later stage. `finish_session()` is idempotent. A failing row writer is recorded in `record_errors` instead of stopping the session.

Tests check:

- The exact stage order for all eight probe/delayed-reentry/perturbation combinations.
- That feedback is present on the content-probe stage.
- Reference affect validation.
- Rejection of invalid and duplicate answers.
- That untimed runs accept an answer after 10,000 virtual seconds.
- Reaction times measured from each prompt.
- A full 120-trial session.

### Added: optional response timer (options screen, CLI options, engine)

The timer can be switched on before a run from either options menu, with a limit from 3 to 120 seconds (default 12). It applies to prediction and behavioral choice. An expired stage records a blank answer, sets `prediction_timed_out` or `behavioral_timed_out`, and advances. A submission at or after the deadline counts as a timeout. Any timer use labels the run `modified_tfl`, because the reference has no timer.

The GUI expires stages live and shows a countdown. Blocking console input cannot be interrupted portably, so the CLI prints the limit with each timed prompt and treats an answer typed after it as a timeout (`DeadlineOnlyTimer` in `engine/timing.py`). Tests cover live expiry, the deadline boundary (4.99 s accepted, 5.00 s timed out at a 5-second limit), stale callbacks, clamping 999 seconds to 120, and late console answers.

### Changed: TFL options screen (`frameworks/TFL/options_screen.py`)

The pre-run screen now shows the reference default-settings list, the four reference toggles with the response timer and its seconds field, and a live "Current Settings" panel that switches between Default TFL and Modified TFL as options change. The "Restore Defaults" and "Start Session" buttons were replaced by **Restore Default Settings** and **Start Experiment**, alongside Cancel.

### Changed: GUI session and trial screens (`session_gui.py`, `screen.py`)

The trial screens render the engine's stages. They include the cue screen with the previous trial's feedback, the typed affect entry, the separate perturbation step, the content probe showing the current trial's feedback, and a completion screen with the final feedback and save locations. Enter activates View Stimulus, the affect Continue, and the perturbation Continue.

The participant-ID prompt was removed because the reference has no participant field. The `participant_id` argument is still accepted so existing launch code works. Completion is handled once in the session adapter, never during rendering. Output goes to the host's live Output Directory setting. GUI wiring is exercised end to end with widget doubles in a separate interpreter (`tests/tfl_gui_doubles_check.py`): a timed, perturbation-enabled 120-trial run, a cancel after three trials, and Restore Default Settings.

### Changed: output files (`frameworks/TFL/output.py`, `schema.py`)

Like the reference, each completed trial is written and flushed before the next begins. Unlike the reference, which overwrote `tfl_output.csv` at the start of every run, each run writes its own `tfl_output_<timestamp>.csv`. A completed run then atomically publishes a copy as `tfl_output.csv`. A cancelled or interrupted run keeps its completed trials in its session file and leaves `tfl_output.csv` untouched. This replaces 0.9.2's five-trial autosave checkpoints, which could lose up to four trials.

`schema.py` now owns the columns: the 27 reference columns in reference order, then `response_timer_sec`, `prediction_timed_out`, and `behavioral_timed_out`. The 0.9.2 columns `session_id`, `participant_id`, `completion_status`, and the ISO timestamps were removed because they are not in the reference. `frameworks/shared/schema.py` re-exports the list for older imports. Tests check per-trial flushing mid-session, publishing on completion, `tfl_output.csv` left untouched after a cancel, and a failing writer reported without stopping the run.

### Changed: standard-library analysis (`frameworks/TFL/analysis.py`)

The report follows the reference analysis section by section: run metadata, trial counts, prediction and behavior, affect and reaction time, prior consistency, contradiction (with affect by level), probes (with recurrence rate), delayed reentry, perturbations, and the completion gate. A Response Timer section appears only when a timer was used. Summaries compute pandas `describe()` values (sample standard deviation, linear-interpolated quartiles). The gate uses the reference rule: A/B prediction, A/B behavioral choice, and a non-blank affect, against `int(rows × 0.8)` of the rows present.

The 0.9.2 prediction-behavior consistency and feedback-carryover reports were removed because they are not in the reference. The planned-count gate (from an unreleased draft) was also not carried forward.

As a one-off check during development, a 120-trial run with random answers, extra stimuli, and perturbations was analyzed by both this module and the reference pandas analyzer. All eleven reported figures matched (prior-consistency rates, contradiction, probe and recurrence counts, reentry and perturbation counts, gate values, unique stimuli), as did the affect and reaction-time summaries. That comparison needs pandas and is therefore not part of the shipped suite. The suite checks the gate rule, quartile and standard-deviation conventions, every section heading on a real session, and the missing-file message.

### Added: command-line suite (`cli.py`, `frameworks/TFL/cli_runner.py`, `main.py`)

`python cli.py` (or `python main.py --cli`) opens a numbered menu in the style of the 02_Execution launcher: Run Framework, Analyze Results, List Frameworks, Show Output Folder, Quit. The `list`, `run <ID>`, `analyze <ID> [--file PATH]`, and `where` subcommands support scripted use. The CLI finds runners through new `FRAMEWORK_METADATA` keys (`cli_module`, `cli_function`, `analysis_module`) and uses the same settings file and output folder as the GUI.

The TFL console runner reproduces the reference flow:

1. A startup menu (ENTER to start, O for options).
2. A numbered options menu. Items 1 to 5 match the reference; 6 toggles the response timer and 7 sets its seconds.
3. The session intro.
4. Prompt-by-prompt trials with the reference prompts and retry messages.

Ctrl+C keeps completed trials in the session file. Tests drive a full default 120-trial console run, an options-menu run (perturbations plus a 20-second timer), a late-answer timeout run, an interrupt after two trials, and the top-level commands, including unknown and reserved frameworks.

### Changed: headless builder and timers (`app/headless.py`, `engine/timing.py`)

`build_default_engine(config_overrides=None, **hooks)` builds a started engine from the defaults plus any overrides on the virtual clock. `engine/timing.py` adds `DeadlineOnlyTimer` for console runs.

### Changed: tests and documentation

`tests/test_tfl_protocol.py` is new, with 34 tests covering:

- Reference parity.
- The trial procedure.
- The timer.
- Output files.
- Analysis.
- The CLI.
- The GUI doubles check.
- An AST dependency audit that rejects any non-stdlib import in any file.
- A check that the CLI and headless paths never load Tkinter.

In `tests/test_merged.py`, 31 tests were removed that targeted the 0.9.2 engine, its autosave, and its extended analysis. The 19 host, registry, trial-structure, header, navigation, and updater tests remain. Every Python file keeps the six-section header. `docs/ARCHITECTURE.md` is new and describes the layering, the TFL flow, the timer, the output files, and the testing boundaries. `services/tfl_analysis.py` now documents `tfl_output.csv`. `version.txt` reads 0.9.3 ALPHA.

### Compatibility limits

- **Protocol change from 0.9.2.** Trial sequences, priors, feedback levels, stimulus text, and the response flow all differ from 0.9.2. Runs from the two versions are not comparable as the same protocol.
- **CSV format.** Output now uses the reference columns plus three timer columns. 0.9.2 files (34 columns) remain readable by the analysis, but their removed columns are ignored. Old `tfl_output_latest.csv` and `autosave/` files are left in place and are no longer read by default.
- **Removed APIs.** `analysis.save_rows`, `write_rows`, `autosave_rows`, `get_autosave_file`, `remove_autosave_file`, `prediction_behavior_consistency_report`, `feedback_carryover_report`, `sorted_completed_rows`, the old `TFLSessionEngine` constructor and stage API, and the participant prompt are gone. External scripts using them need updating.
- **Remaining differences from the reference in default runs.** Reaction times use the monotonic clock and include GUI interaction time. The GUI shows feedback on screen instead of in a scrolling console. Output goes to the configured output folder as a session file plus `tfl_output.csv`, instead of overwriting `TFL/data/tfl_output.csv` at the start of a run. Analysis text layout differs from pandas' printed tables, though the reported values match.
- **Untested here.** Native Tk rendering, focus, and window management were not tested (no Tk in the test environment). Updater network paths, production signing, and Windows executable swapping were not exercised. The trust anchor is still the placeholder key.
- **Concurrent runs.** Two runs into the same folder each keep their own session file, but the last run to finish owns `tfl_output.csv`.

---

## [0.9.2 ALPHA] - 2026-09-26

### Removed

- Removed the Tooling page, Tooling registry system, Tooling installer subsystem, Tooling update notifications, and Tooling startup update checks.
- Removed all Tooling navigation references. The sidebar now contains Dashboard, Frameworks, Results, Archive, and Settings.
- Brisart Research Archive now focuses on framework execution, analysis, documentation, settings, and Archive self-updating.

### Added

- **Obsolete-file removal on update** (`services/updater/install.py`, `services/updater/constants.py`): installs were overwrite-only, so existing installations would have kept the removed Tooling modules forever. `OBSOLETE_RELEASE_PATHS` lists them, and `remove_obsolete_files()` deletes them after the pre-install backup. Entries that are absolute, contain `..`, resolve outside the application folder, or are not regular files are skipped.
- **Trust-anchor guard** (`services/trust_anchor.py`, `services/updater/orchestration.py`): `is_configured()` detects the placeholder public key. While the placeholder is in place, update checks return `trust_anchor_unconfigured` without contacting the network, instead of downloading a release and reporting it as forged.
- **`docs/KNOWN_ISSUES.md`**: restored. It was referenced throughout the code but missing. It now uses the standard bug report template.
- **Tests** (`tests/test_merged.py`, 41 to 50 tests): file-header standard enforcement, sidebar contents, absence of Tooling modules, registry URL allowlisting, trust-anchor guard, and obsolete-file removal safety.

### Changed

- **Every Python file (52)** now begins with the standard header: `File:` path, then Purpose, Communication / relationships, Settings / parameters, Edge cases, Known limitations, and Examples. The header test enforces it.
- **Registry URL** (`services/updater/constants.py`): corrected to point to the AIO Launcher prerelease repository location:

  https://github.com/JasonBrisart/BrisartResearchArchive/blob/main/aio-launcher-prerelease/

  The previous changelog entry incorrectly stated that the updater registry had been redirected back to the Brisart Research Archive website tooling page. It has not been; it now points to the AIO Launcher prerelease location above, not the website tooling page.
- **Updater host allowlist** (`services/updater/constants.py`): `ALLOWED_REMOTE_HOSTS` updated to allow `github.com` so registry lookups against the corrected URL pass host validation.
- **Quiet startup check** (`services/updater/gui_integration.py`): the unattended startup check no longer reports `current`, `local_newer`, `trust_anchor_unconfigured`, `registry_error`, `network_error`, or `http_error`. Verification failures are still always shown, and the manual Check Updates button still reports every outcome.
- `services/updater/download.py` now imports `services.rsa_signing` explicitly, matching the namespace-package convention.

### Fixed

- **Startup crash** (`config/registries.py`): 12 stray backslashes in type annotations and one dictionary lookup caused `SyntaxError: unexpected character after line continuation character` on launch.
- **Updater could never reach its registry**: the registry host was not in `ALLOWED_REMOTE_HOSTS`, so every check failed URL validation before sending a request.
- **Startup switched to the Settings page**: failed unattended checks called `set_update_text()`, which navigates to Settings. With a misconfigured registry URL or host allowlist, this happened on every launch, and it would also happen on every launch of an offline machine.
- Removed stale Tooling and `services/__init__.py` references from module documentation.

### Notes

- `services/trust_anchor.py` still ships the placeholder key. Generate a keypair offline with `python signing/sign_release.py generate-keys` and paste the printed public key before publishing signed releases.
- Run the test suite with `python tests/test_merged.py`. `tests/` has no `__init__.py`, so `python -m unittest tests.test_merged` does not work.

---

## [0.9.1 ALPHA] - 2026-09-08

### Added
- **`frameworks/TFL/settings.py`** (new file): THE single place to edit TFL's tunable behavior -- trial duration, trial/block counts, probe/delayed-reentry/perturbation intervals, random seed, affect range, stimulus limit, feedback levels, perturbation types, default run-option toggles, and all prompt/intro text. A pure-data leaf module with no internal imports, so it can never create a circular import.
- **`services/timestamps.py`** (new file): the generic `timestamp()` helper used by `controllers/log_controller.py`, split out of the old `services/__init__.py`.
- **`services/tfl_analysis.py`** (new file): the four TFL-specific GUI bridge functions (`analyze_tfl`, `set_analysis_text`, `fallback_csv_summary`, `open_tfl_csv`), split out of the old `services/__init__.py` so TFL-only logic no longer lives in the generic `services` package initializer.

### Changed
- **`frameworks/TFL/config.py` rewritten** to assemble `DEFAULT_CONFIG` and the "official default startup" option set entirely from `frameworks/TFL/settings.py`. The file now holds no tunable literals of its own -- every value is read from `settings.py`, so TFL's behavior is edited in exactly one file.
- **`frameworks/TFL/framework.py`**: `BASE_STIMULUS_LIMIT`, `PREDICTION_PROMPT`, `PREDICTION_CHOICES`, and `SESSION_INTRO_TEXT` are now re-exported from `settings.py` instead of being hardcoded here as a second, separate copy.
- **`frameworks/TFL/trial_builder.py`**: `VALID_BLOCKS` and `VALID_FEEDBACK_LEVELS` now read from `settings.py` instead of local hardcoded set literals.
- **`frameworks/TFL/engine.py`**: the timed-stage countdown now falls back to `settings.TRIAL_DURATION_SEC` instead of a hardcoded `12`.
- **`frameworks/TFL/session_gui.py`**: `AUTOSAVE_INTERVAL_TRIALS` is now imported from `settings.py` instead of being defined locally.
- **`services/__init__.py` removed entirely.** `services/` is now a PEP 420 namespace package, consistent with every other package in the project -- this was the last remaining `__init__.py` file anywhere in the codebase.
- **`controllers/log_controller.py`**: import changed from `from services import timestamp` to `from services.timestamps import timestamp`.
- **`controllers/system_controller.py`**: import changed from `from services import (analyze_tfl, ...)` to `from services.tfl_analysis import (analyze_tfl, ...)`.

### Notes
- No behavior, output schema, or stored-format changes. `get_default_config()` produces byte-identical output to the pre-refactor version -- verified directly (120 trials, 40 per block, all interval/feedback/perturbation values unchanged).
- No changes were required to `frameworks/TFL/stimuli.py`, `frameworks/TFL/feedback.py`, `frameworks/TFL/analysis.py`, or `frameworks/TFL/screen.py` -- none of them referenced the old config layout.
- TFL's full edit surface is now exactly two files: `settings.py` for all tunable behavior, `stimuli.py` for all stimulus content.

---

## [0.9.0 ALPHA] - 2026-08-27

### Added
- **Tooling page**, a brand new page for downloading, running, and updating separate Brisart-family programs directly from the Archive:
  - `config/tooling_catalog.py` (new): static catalog of installable programs (BrisartIdentityTools, BrisartAI, BrisartOS, Project Context Helper, Entitle, AutoExeBuilder).
  - `config/tooling_state.py` (new): persisted on-disk record of what's installed, which version, and where.
  - `services/tooling_manager.py` (new): download, verify, install, run, and update-check logic — reuses the exact same hash-then-signature verification gate already built for the Archive's own self-updater, so an installed program is verified exactly as rigorously as an Archive update.
  - `services/tool_update_notify.py` (new): popup summary shown when an installed program has a newer version available.
  - `gui/pages/tooling_page.py` (new): one card per program, split into an **Installed** group (top) and an **Available to Download** group (bottom), each sorted alphabetically.
  - New **Tooling** sidebar entry, pinned directly above **Settings** at the bottom of the sidebar, separated by a divider.
  - `controllers/system_controller.py`: new `download_tool()`, `run_tool()`, `open_tool_folder()`, and `check_tool_updates()` methods wiring the page to the manager above.
  - An automatic Tooling update check now runs once at startup, staggered 1 second after the Archive's own self-update check.

### Changed
- **Frameworks page rebuilt** to match the Tooling page's structure and conventions:
  - Removed the "Framework Library" card and its Run Selected Framework / View Results / Refresh Registry actions from this page (all three remain available elsewhere — Dashboard and Results already have them).
  - Replaced the 2-column card grid with a single-column, one-card-per-row layout.
  - Frameworks are now split into an **Available** group (top) and an **Available to Download** group (bottom), each sorted alphabetically by name, instead of one flat list in declared order.
  - Removed the "Select" button; available frameworks now show only **Run** and **Results**.
  - Unavailable frameworks now show **"Not installed."** in the card body (matching Tooling's wording) instead of just the bare description.
  - Replaced "Reserved" / "Coming Soon" badge and button text with **"Available to Download"**, matching Tooling's terminology.
- **Activity Log now shows the newest entry at the top** instead of the bottom, for both new entries logged during the current session and persisted history loaded from previous sessions (`controllers/log_controller.py`, `gui/pages/settings_page.py`).

### Fixed
- **Window now always opens at exactly 800x600 on every launch**, regardless of any window size previously saved to `user_settings.json`. Previously, the 800x600 value was only a *default* — the very first time a user resized the window and closed the app, that saved size was read back and applied on the next launch, silently overriding the intended 800x600 starting size from then on (`gui/main_window.py`).

---

## [0.8.0 ALPHA] - 2026-08-27

### Added
- **Persistent Activity Log** (`config/activity_log.py`, new file): the Activity Log on the Settings page now survives closing and reopening the app. Every action logged via `LogController.log()` is written to a rolling, disk-backed JSON file capped at the most recent **100 entries** (oldest-first, oldest dropped automatically once the cap is reached). Previously the log only ever showed the current session and reset to blank on every relaunch.
- **Yes/No update confirmation dialog**: with "Automatically download and install updates" off and "Notify me about updates" on, the app now asks *"A new update is available. Would you like to download and install it now?"* before touching anything. Declining simply means it asks again next time — nothing is remembered or suppressed.
- **Post-install changelog popup**: when an update installs (manually confirmed or fully automatic), an "Update Installed" popup now shows a summary of what changed, sourced from an optional `changelog` field in the registry entry (`services/updater/registry.py`).
- **Dynamic text wraplength** (`bind_dynamic_wraplength()` in `gui/components/page_helpers.py`): page subtitles and card body text now recalculate their wrap width on every resize instead of using a fixed pixel value, so text reflows correctly at any window size instead of clipping.
- **`docs/KNOWN_ISSUES.md`** (new file): a standing, concise record of currently unresolved bugs — symptom, what's been tried and ruled out, and the next concrete diagnostic step. Created so open issues don't have to be re-investigated from scratch later.
- Settings page now visibly greys out "Automatically download and install updates" and "Notify me about updates" whenever "Enable update checks" is off, and force-unchecks both if they were checked — making the dependency between these three settings impossible to misconfigure.

### Changed
- **Renamed the "System" page to "Settings"** throughout: `config/registries.py`, `gui/pages/settings_page.py` (replacing `gui/pages/system_page.py`), and the sidebar. `"System"` is kept only as a backward-compatible page-name alias.
- **Settings moved to its own bottom-pinned sidebar section** (`gui/components/sidebar.py`), separated from the main nav (Dashboard/Frameworks/Results/Archive) by an expanding spacer and a thin divider line, instead of sitting in the same list as content pages.
- **Default window size reduced from 1220x780 to 800x600** (`config/runtime.py` `DEFAULT_SETTINGS`), so the app opens at a reasonable size instead of dominating the screen. `MIN_WINDOW_WIDTH`/`MIN_WINDOW_HEIGHT` (both in `config/runtime.py` and the hardcoded `self.minsize()` in `gui/main_window.py`) were lowered from 1060x700 to match — otherwise either floor would have silently clamped the new default back up.
- **Reordered the Updates card**: "Notify me about updates" moved down to sit directly above the "Check Updates" button, since that's the exact moment its Yes/No prompt actually fires. Order is now: Enable update checks → Automatically download and install updates → Notify me about updates → Check Updates.
- **Rewrote all Updates section copy** in plain, user-facing language instead of dense technical paragraphs.
- **"Notify me about updates" now governs two things, not one**: the pre-download Yes/No prompt (manual path) *and* whether the post-install changelog popup appears (automatic path). Turning it off makes both silent — the only sign an update happened is the version number itself, the next time Settings is opened.
- **"Install Update" button removed entirely.** Installation now only ever happens via the Yes/No prompt or full auto-install; there is no longer a separate manual install step to keep in sync with the rest of the flow.
- Mouse wheel scrolling architecture substantially reworked across `gui/components/page_helpers.py` and `gui/main_window.py` — see Fixed section below for the full, documented history (FIX 1 through FIX 7).
- Every Python file touched this cycle now begins with a full top-of-file documentation header (file path, purpose, what talks to it / what it talks to, explanation of every setting/parameter and its edge-case behavior) instead of a one-line comment, per new standing convention. Fix/bug history inside those headers is ordered chronologically, oldest first.

### Fixed
- **Fixed a startup crash** (`AttributeError`/`ImportError`) caused by a stale `gui/pages/system_page.py` still wired to `app.install_update`, a method that had already been removed from `controllers/system_controller.py`.
- **Fixed `config/registries.py` registering the wrong Settings page module** (`system_page` vs. the corrected `system`, and later a naming-convention swap back to `settings_page`) — the broken pre-refactor page was rendering instead of the intended one.
- **Fixed the automatic startup update check silently contacting the registry** even when both "Automatically download and install updates" and "Notify me about updates" were off. `services/updater/gui_integration.py`'s `should_run_automatic_startup_check()` now makes this a true no-op in that combination — the manual "Check Updates" button remains the only way to trigger a check.
- **Fixed mouse wheel scrolling not working anywhere except the Scrollbar itself** for a physical mouse wheel — root-caused and fixed in stages (all documented in full inside `gui/components/page_helpers.py` and `gui/main_window.py`):
  - FIX 1: hover-gated `<Enter>`/`<Leave>` binding never worked because the canvas is fully covered by its own child widgets.
  - FIX 2: `event.delta` truncation meant trackpad-style small deltas (below 120) silently produced zero scroll.
  - FIX 3/4: a focus-based theory (Windows routing `<MouseWheel>` by keyboard focus) proved insufficient.
  - FIX 5: direct per-widget instance binding fixed physical mouse wheel scrolling completely.
  - FIX 6: a global root-level handler resolving the real widget under the cursor via `winfo_containing(event.x_root, event.y_root)` — bypassing Tk's internal motion-cache — was implemented as the current best mechanism for the general page area.
- **Fixed "Update output" and "Activity Log" text boxes swallowing the mouse wheel entirely** whenever their own content already fit fully on screen (FIX 7): Tk's built-in Text-widget scroll binding was intercepting and discarding the event even with nothing to scroll internally, blocking it from ever reaching the page underneath. New `bind_text_widget_scroll_passthrough()` helper forwards the scroll to the page in that specific case.
- **Fixed page text clipping instead of wrapping** on narrower window sizes (see Added: Dynamic text wraplength).

### Known Issues (see `docs/KNOWN_ISSUES.md` for full detail)
- **Touchpad scrolling over the general page area remains unresolved.** A physical mouse wheel works everywhere on the page (FIX 5/6 above); a touchpad two-finger scroll gesture still does not scroll anything outside the Scrollbar itself. Five fix attempts have been made and ruled out; current status, confirmed environment details, and the next concrete diagnostic step are tracked in `docs/KNOWN_ISSUES.md`.

---

## [0.7.0 ALPHA] - 2026-08-16

### Added
- TFL now shows a pre-session Run Options screen before starting a session, exposing Extra Stimuli, Perturbations, Probes, and Delayed Reentry as toggles.
- Added Restore Defaults, Cancel, and Start Session controls to the new TFL options screen.
- Added an optional participant ID prompt when launching TFL from the GUI.

### Fixed
- Fixed TFL launching directly into a session and skipping the options screen entirely. `session_gui.py` previously built the engine and rendered the trial screen immediately, so `options_screen.py` was never actually called.
- Fixed the TFL options/session window potentially opening behind the main application window by forcing it to the front on open.
- Fixed silent failures when the options screen could not render. Errors are now logged and shown in a visible dialog instead of leaving a blank or invisible window.
- Fixed trial/stimuli generation now happening only after the user confirms options, instead of before the options screen is shown.

### Changed
- Reordered TFL session startup: options screen first, engine/stimuli/trials built only after "Start Session" is clicked.
- Config values chosen on the options screen are now applied directly before session build, so toggling a setting reliably changes that run's behavior.

### Notes
- No changes were required to `options_screen.py`, `screen.py`, `engine.py`, `config.py`, `stimuli.py`, or `trial_builder.py` - the fix was isolated entirely to `session_gui.py`'s startup flow.
- This closes the gap between the console AIO launcher's options menu and the GUI's TFL launch flow.

---

## [0.6.0 ALPHA] - 2026-08-16

### Changed
- Simplified the Dashboard into a minimal landing page with quick access cards for Frameworks, Results, Archive, and System.
- Removed the previous dashboard status blocks that duplicated information already available in the System page.
- Replaced the experimental workspace/output dashboard concepts with a cleaner placeholder dashboard so future dashboard features can be redesigned without clutter.
- Updated Dashboard quick actions to focus on basic navigation and currently selected framework execution.
- Removed the visible version label from the left sidebar menu to reduce visual noise and keep version details within the appropriate system-level areas.

### Fixed
- Replaced the broken Dashboard page implementation that caused a syntax error during application startup.
- Replaced the broken Sidebar implementation that caused an unterminated string literal error during application startup.
- Restored clean application launch behavior after simplifying the Dashboard and Sidebar files.

### Notes
- The Dashboard is now intentionally minimal.
- The sidebar remains the primary navigation surface.
- Future dashboard cards can be added later without changing the page registry, framework system, or application shell.

---

## [0.5.0] - 2026-08-16

### Removed
- **8 non-functional cards removed across three pages** to cut UI clutter that had no real purpose (no click action, unbuilt placeholders, or duplicated content):
  - **Archive page**: removed "Lab Workflow" (duplicated Dashboard's Recommended Workflow), "Architecture Notes", "Framework Runner Rule", "Shared Layer Rule" (pure prose, no action), and "Future Archive Areas" (placeholder wishlist for 8 unbuilt features). Archive page now contains only the functional "Open Archive Document" card.
  - **Dashboard page**: removed "Engine/Shell Split" and "Local-First Rule" (pure architecture philosophy text, no action).
  - **System page**: removed "Brisart Standards" (placeholder listing four standards docs that don't exist yet).
- Frameworks and Results pages were left unchanged — every card there already triggers a real action.

---

## [0.4.6] - 2026-08-16

### Added
- **Open Folder button** on the System page, next to Browse. Opens the
  currently configured output directory directly in the OS file explorer
  (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux).
  - Falls back to the default output folder if the configured path is blank
    or unreadable.
  - Creates the folder first if it doesn't exist yet, so this never silently
    fails on a fresh install.
  - New `SystemController.open_output_folder()` in `controllers/system_controller.py`.
  - Button placed in `gui/pages/system_page.py`, directly under Browse.

---

## [0.4.5] - 2026-08-16

Baseline version for this changelog. Confirmed working state of the
Archive architecture, with the full headless engine / GUI split,
autosave, identity/timestamp fields, and hardened updater already in place.

No changes tracked prior to this version.
