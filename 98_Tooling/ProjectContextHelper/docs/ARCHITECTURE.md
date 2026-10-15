# Architecture

Project Context Helper is a standard-library Python application within Brisart Research Archive. This document describes v4.0.0, including its current coupling and limitations. v4.0.0 keeps the v3.1.4 folder layout, file names, and desktop interface, and rebuilds the export engine underneath (background builds, single-read parallel capture, staged publication, locked persistence). It does not certify runtime behavior.

## Project layout

```text
ProjectContextHelper/
|-- run.py
|-- cli/
|   `-- cli.py
|-- core/
|   |-- builder.py
|   |-- constants.py
|   |-- events.py          (new in v4.0.0)
|   |-- exporters.py
|   |-- git_state.py
|   |-- models.py
|   |-- scanner.py
|   `-- utils.py
|-- services/
|   |-- storage.py
|   `-- updater.py
|-- gui/
|   |-- main_gui.py
|   |-- builders.py
|   |-- build_tab.py
|   |-- options_tab.py
|   |-- extras_tab.py
|   |-- profiles_section.py
|   |-- about_tab.py
|   |-- dialogs.py
|   |-- jobs.py            (new in v4.0.0)
|   `-- scroll_frame.py
|-- tests/
|   |-- test_export_safety_utilities.py
|   |-- test_v4_engine.py  (new in v4.0.0)
|   |-- test_gui_wiring.py (new in v4.0.0)
|   `-- fake_tk.py         (new in v4.0.0)
`-- docs/
    |-- README.md
    |-- ARCHITECTURE.md
    `-- CHANGELOG.md
```

## Entry point and actual dependencies

`run.py` inserts its own directory into `sys.path`, imports `cli.cli.main`, and invokes it under the main guard. The CLI dispatches management commands, an export, or the GUI when no project root is supplied.

Both frontends call `core.builder.create_context()`, but they are not isolated from one another:

- `cli/cli.py` imports `gui.main_gui` only when it launches the GUI, so command-line exports do not need tkinter.
- `core/builder.py` imports `HistoryEntry` and `append_history_entry` from `services.storage`. The core package is therefore not entirely independent of services.
- `services/storage.py` depends on `core.constants` and `core.models`.
- `services/updater.py` depends on `core.constants` and reuses `services.storage.application_dir()`.
- GUI modules depend on core and services; neither service imports the frontends.

```text
run.py -> cli.cli
              |-> gui.main_gui -> GUI components (lazy import)
              |-> core.builder <- gui.builders <- gui.jobs (worker thread)
              |       |-> core.scanner -> core.models / core.events / core.constants
              |       |-> core.exporters -> core.utils
              |       |-> core.git_state
              |       `-> services.storage -> core.constants / core.models
              `-> services.updater -> services.storage / core.constants
```

This is a modular application with shared orchestration, not a strictly layered dependency architecture.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `core/constants.py` | Application metadata, filenames, exclusion defaults, built-in presets, and legacy release endpoints. |
| `core/models.py` | Mutable `ScanSettings`, JSON conversion, and frozen file/skip/scan/build records. |
| `core/scanner.py` | Pruned discovery, file eligibility, skip records, byte budgets, single-read parallel capture, completeness enforcement, and separate tree rendering. |
| `core/events.py` | Progress records and cooperative cancellation checkpoints. |
| `core/utils.py` | Root validation, timestamps, extension normalization, heuristic redaction, hashing, line counts, and language hints. |
| `core/git_state.py` | Optional local Git metadata inspection without invoking Git. |
| `core/exporters.py` | Markdown, manifest, summary, completeness reports, and ZIP rendering from captured bytes. |
| `core/builder.py` | Settings/output validation, export orchestration, staging and publication, and best-effort history recording. |
| `services/storage.py` | Preferences, last-used settings, named profiles, and history persistence with locking. |
| `services/updater.py` | Legacy release lookup, staging, backup, source copying, and Windows executable replacement. |
| `cli/cli.py` | Argument parsing, settings precedence, management actions, and export dispatch. |
| `gui/builders.py` | Shared tkinter state, validation, settings conversion with hidden-field retention, and worker-safe export invocation. |
| `gui/jobs.py` | One background build thread and the event queue the Tk thread polls. |
| Other GUI modules | Window/tab construction, profile controls, dialogs, history/update controls, and scrolling. |

## Export lifecycle

`create_context()` performs these operations in order:

1. Resolve and validate the selected project root.
2. Use supplied settings, or the archive preset when omitted; validate a deep copy (profile, positive size limits, `workers` 1-32, non-empty output name). The caller's settings object is never changed.
3. Reject an output folder name that is absolute, drive-qualified, contains `..`, or resolves outside the project or to the project root.
4. Inspect Git metadata when requested (the output folder's name is added to the Git walk's exclusions).
5. Create the output folder and a hidden `.pch-build-*` staging folder inside it.
6. Discover files with a pruned depth-first walk: excluded folders, the output folder, `.pch-*` entries, and symlinks are recorded once and never entered. Apply per-file and total byte budgets in sorted path order (the same order v3.1.4 used).
7. Enforce completeness on discovery results, then capture the selected files with a thread pool of `workers` threads in batches of `2 x workers`. Each file is read once; its hash and line count come from those bytes, which are written to a spool inside the staging folder. A file whose size changed since discovery is skipped as `source_changed`. Enforce completeness again.
8. Write Markdown context, JSON manifest, plaintext summary, and settings JSON into staging, reading file contents from the spool.
9. Optionally create a ZIP of those outputs plus the spooled bytes under `project_files/`.
10. Delete the spool and publish: rename staging to `project_context_<timestamp>` (adding `_2`, `_3`, ... if taken), or for flat output replace the generated files in the output folder.
11. Construct `BuildResult`, attempt to record history, and return the result.

Cancellation and progress: callers may pass a `threading.Event` and a progress callback. The pipeline checks the event between directories, between capture batches, after rendering, and after zipping; once publication starts it is no longer checked. Progress phases are `discovering`, `capturing` (with counts), `rendering`, `zipping`, and `publishing`.

Any failure, completeness stop, or cancellation before publication deletes the staging folder; the output folder itself may remain. History-write failures are suppressed after publication. A hard kill or power loss can still leave a `.pch-build-*` folder, which later scans skip and which can be deleted manually.

## Settings and precedence

### Built-in presets

`settings_for_profile()` constructs fresh settings, applies shared exclusions, and applies the selected preset. Both presets enable ZIP creation and heuristic Markdown redaction and disable Git inspection.

| Setting | standard | archive |
|---|---:|---:|
| Maximum file bytes | 350000 | 2000000 |
| Maximum total bytes | 5000000 | 100000000 |
| Embedded contents, hashes, line counts, skipped details | Disabled | Enabled |
| Required eligible-source completeness | Disabled | Enabled |
| Markdown skipped-detail limit | 100 | 1000 |

Both presets use 4 capture workers. The interface default is `archive`, and `create_context(root)` without settings now uses it too. Raw `ScanSettings()` is still not an archive preset: its extension and exclusion sets are empty.

### CLI precedence

Settings are applied in this order, with later stages taking precedence:

1. Selected built-in preset.
2. Last-used settings, when `--use-last-settings` is supplied and loading succeeds.
3. Named profile, when `--load-profile` is supplied and loading succeeds.
4. Explicit CLI overrides (including `--workers`).

`--extensions` replaces the extension set; repeated exclusions extend existing sets. When both Git enable/disable flags are supplied, `--no-git-state` wins. The CLI does not automatically load or save last-used settings.

### GUI behavior

The GUI loads saved preferences and last-used export settings at startup. Successful builds save last-used export settings. Unsaved edits are not automatically saved as last-used settings.

Changing the built-in profile applies preset defaults. Named-profile loading sets the base profile first and reapplies exposed values afterward so those values survive the preset callback.

The GUI does not expose every `ScanSettings` field. `GuiState.base_settings` holds the last fully loaded settings (startup memory, a custom profile, or a preset). Building settings starts from a copy of it when its profile matches the dropdown and overlays the exposed controls, so hidden values such as custom extension/exclusion sets, `workers`, and the Git history limit survive builds and profile saves. Selecting a different built-in profile replaces them with that preset. GUI sizes use decimal MB: 1000000 bytes per MB.

## Persistence and design rationale

`services/storage.py` centralizes four persisted state files:

- `app_settings.json`: folder-opening and update preferences.
- `last_export_settings.json`: settings from the last remembered export.
- `custom_profiles.json`: named settings records.
- `build_history.json`: export history, capped at 50 entries.

The shared `application_dir()` resolves beside `run.py` in source mode and beside the executable in frozen mode; the `PCH_STATE_DIR` environment variable overrides both. The updater reuses this helper.

The documented reason for consolidation was to remove duplicated application-directory resolution and make persistence findable in one module. CLI settings memory remains opt-in for scripting determinism; GUI settings memory is automatic after successful builds.

Writes use a uniquely named `.pch-*.tmp` sibling (`tempfile.mkstemp`), flush/fsync, and `os.replace()`. Read-modify-write operations on profiles and history run inside `state_lock()`: an in-process reentrant lock plus a `.pch-state.lock` file created with `O_EXCL`. Waiting is limited to 5 seconds (then `TimeoutError`), and a lock file older than 30 seconds is treated as abandoned. This is advisory locking between processes running this code; it is untested on network filesystems and is not a multi-file transaction.

Some convenience operations still suppress errors. Profile and history writes propagate failures; the GUI and CLI report them. Preference loading now returns defaults for non-object JSON and accepts only real booleans. Profile writes refuse to overwrite an unreadable or malformed `custom_profiles.json`.

## Completeness and preservation boundaries

Completeness checks cover configured eligible source/text files, not every project file. Blocking reasons are `file_too_large`, `total_size_limit`, `size_unavailable`, `read_unavailable`, `source_changed`, and `directory_unavailable`.

Intentional exclusions, unsupported extensions, symlinks (`symlink_not_followed`), special files, the output folder (`export_output_directory`), and `.pch-*` entries (`internal_tool_file`) do not fail completeness. A PASS does not establish program correctness, test success, secret removal, or full repository preservation. Each file's hash, Markdown text, and ZIP copy come from one read, but files are captured at slightly different moments, so the export is not an atomic snapshot of the whole project.

The tree is rendered separately using exclusions, not inclusion eligibility or byte budgets. It can show files absent from the index. An excluded folder now produces one skip record for the folder rather than one per descendant file.

## Security and output limitations

- Redaction is heuristic and affects rendered text only. ZIP members retain original source bytes.
- Hashes describe original source bytes, not redacted Markdown.
- Symlinked files and folders are skipped rather than followed. Capture opens files with `O_NOFOLLOW` where the platform supports it, but there is no protection against a hostile process swapping files mid-export.
- Output folder names must stay inside the project; the output folder is always excluded from scans.
- Embedded file contents use a fence longer than any backtick run they contain, so embedded Markdown fences cannot break the document.

These are current boundaries, not assurances of safe handling of arbitrary sensitive or untrusted projects.

## Optional Git inspection

Git inspection reads `.git` at the selected root, including a supported gitdir pointer. It does not search parent directories, invoke Git, parse packfiles, interpret `.gitignore`, compare the index, or implement full linked-worktree/SHA-256 repository support.

Unavailable data produces warnings and can leave dirty status unknown. Partial subtree warnings can also coexist with a clean/dirty result. Excluded tracked files can be reported as deleted. Raw-byte comparisons do not implement Git filters or full file-mode/symlink semantics.

Treat this output as supplementary context, not authoritative Git verification.

## Legacy updates and offline operation

Local export generation does not require network access. Release checks, downloads, and opening release pages do.

The implementation still points to the legacy BrisartDevTools GitHub release endpoints. This documentation update does not migrate those endpoints or implement archive-hosted distribution.

Digest verification is conditional: absent or unsupported digests are skipped. Some UI messages claim stronger verification than the implementation guarantees. Source updates back up and overwrite files, but do not remove obsolete files or automatically roll back partial failures. Not all state files are protected from replacement.

Executable replacement uses a Windows batch script and requires the caller to exit. The script does not check move success before relaunch; delayed expansion can affect exclamation marks in paths. Update staging and copying are not a trusted-package validation system.

## GUI execution model

The Build tab validates input on the Tk thread (`prepare_build`), then starts `execute_build` on `gui.jobs.JobRunner`, a single non-daemon worker thread. The worker never touches tkinter: it reports `Progress` events and its result or exception through a queue. The Tk thread polls the queue every 80 ms with `window.after()`, updates the status bar, and on completion re-enables the button, refreshes Recent Exports, and shows the same dialogs as v3.1.4 (`ValueError` -> Build Stopped, other errors -> Build Failed).

Closing the window during a build asks for confirmation, sets the cancellation event, and destroys the window only after the worker exits. Network/update work still runs synchronously on the GUI thread. Global mouse-wheel bindings in `scroll_frame.py` can still interfere with other components.

## Validation and maintainer handoff

The included unittest suite covers the original utility tests, the full export pipeline (outputs, ZIP/manifest hash agreement, sequential vs parallel parity, cancellation and failure cleanup, output-path safety, pruning, symlinks, fences, settings parsing), locked persistence (thread and process concurrency, corrupt files, stale locks), CLI behavior, slash-branch Git State, and GUI wiring through a recording tkinter stand-in. It does not cover the updater, a real Tk display, or large-project performance.

```bash
python -m unittest discover -s tests -v
```

Run from the directory containing `run.py`. Tests point `PCH_STATE_DIR` at temporary folders and never touch real state files. Changelog verification narratives are historical records, not substitutes for executable regression coverage.

Recommended maintainer checklist:

1. Read the README, this dependency map, and the relevant module headers.
2. Record the Python version and platform used for validation.
3. Run the included tests and record the actual result.
4. Perform the README's suggested smoke test on disposable fixture data.
5. Review skip records, completeness scope, settings, and ZIP contents separately.
6. Validate changed behavior with focused regression tests before claiming support.
7. Update module headers, README, architecture, and changelog together when behavior changes.

Recommended additional regression coverage: CLI settings precedence end to end; partial/packed Git data; updater failure/verification behavior; and a manual pass of the GUI on each target platform. These are proposed validation priorities, not existing coverage.
