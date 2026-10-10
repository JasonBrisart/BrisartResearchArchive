# Architecture

Project Context Helper is a standard-library Python application within Brisart Research Archive. This document describes the supplied v3.1.4 implementation, including its current coupling and limitations. It does not describe a proposed refactor or certify runtime behavior.

## Project layout

```text
ProjectContextHelper/
|-- run.py
|-- cli/
|   `-- cli.py
|-- core/
|   |-- builder.py
|   |-- constants.py
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
|   `-- scroll_frame.py
|-- tests/
|   `-- test_export_safety_utilities.py
`-- docs/
    |-- README.md
    |-- ARCHITECTURE.md
    `-- CHANGELOG.md
```

## Entry point and actual dependencies

`run.py` inserts its own directory into `sys.path`, imports `cli.cli.main`, and invokes it under the main guard. The CLI dispatches management commands, an export, or the GUI when no project root is supplied.

Both frontends call `core.builder.create_context()`, but they are not isolated from one another:

- `cli/cli.py` imports `gui.main_gui` at module load. Consequently, source CLI operations also require tkinter to be importable.
- `core/builder.py` imports `HistoryEntry` and `append_history_entry` from `services.storage`. The core package is therefore not entirely independent of services.
- `services/storage.py` depends on `core.constants` and `core.models`.
- `services/updater.py` depends on `core.constants` and reuses `services.storage.application_dir()`.
- GUI modules depend on core and services; neither service imports the frontends.

```text
run.py -> cli.cli
              |-> gui.main_gui -> GUI components
              |-> core.builder <- gui.builders
              |       |-> core.scanner -> core.models / core.utils
              |       |-> core.exporters
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
| `core/scanner.py` | File eligibility, skip records, byte budgets, completeness enforcement, and separate tree rendering. |
| `core/utils.py` | Root validation, timestamps, extension normalization, heuristic redaction, hashing, line counts, and language hints. |
| `core/git_state.py` | Optional local Git metadata inspection without invoking Git. |
| `core/exporters.py` | Markdown, manifest, summary, completeness reports, and ZIP rendering. |
| `core/builder.py` | Export orchestration and best-effort history recording. |
| `services/storage.py` | Preferences, last-used settings, named profiles, and history persistence. |
| `services/updater.py` | Legacy release lookup, staging, backup, source copying, and Windows executable replacement. |
| `cli/cli.py` | Argument parsing, settings precedence, management actions, and export dispatch. |
| `gui/builders.py` | Shared tkinter state, validation, settings conversion, and export invocation. |
| Other GUI modules | Window/tab construction, profile controls, dialogs, history/update controls, and scrolling. |

## Export lifecycle

`create_context()` performs these operations in order:

1. Resolve and validate the selected project root.
2. Use supplied settings, or construct raw `ScanSettings()` when omitted.
3. Inspect Git metadata when requested.
4. Create the output directory and output paths.
5. Scan eligible files and enforce configured completeness.
6. Write Markdown context, JSON manifest, plaintext summary, and settings JSON sequentially.
7. Optionally create a ZIP containing those outputs and original included source files.
8. Construct `BuildResult`, attempt to record history, and return the result.

History-write failures are suppressed after export creation. A completeness failure occurs before rendering, but the output directory may already exist.

Outputs are not written as a transaction. A failure can leave partial output. Source files are read at multiple stages, so a changing project can produce different scan hashes, rendered contents, and ZIP bytes. Timestamped directories have one-second resolution and can be reused by builds started in the same second.

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

The interface default is `archive`. Raw `ScanSettings()` is not an archive preset: its extension and exclusion sets are empty. Direct callers should explicitly use `settings_for_profile()`.

### CLI precedence

Settings are applied in this order, with later stages taking precedence:

1. Selected built-in preset.
2. Last-used settings, when `--use-last-settings` is supplied and loading succeeds.
3. Named profile, when `--load-profile` is supplied and loading succeeds.
4. Explicit CLI overrides.

`--extensions` replaces the extension set; repeated exclusions extend existing sets. When both Git enable/disable flags are supplied, `--no-git-state` wins. The CLI does not automatically load or save last-used settings.

### GUI behavior

The GUI loads saved preferences and last-used export settings at startup. Successful builds save last-used export settings. Unsaved edits are not automatically saved as last-used settings.

Changing the built-in profile applies preset defaults. Named-profile loading sets the base profile first and reapplies exposed values afterward so those values survive the preset callback.

The GUI does not expose every `ScanSettings` field. Building settings starts from a preset and overlays exposed controls; custom extension/exclusion sets, a custom Git history limit, and other hidden values can be lost. GUI sizes use decimal MB: 1000000 bytes per MB.

## Persistence and design rationale

`services/storage.py` centralizes four persisted state files:

- `app_settings.json`: folder-opening and update preferences.
- `last_export_settings.json`: settings from the last remembered export.
- `custom_profiles.json`: named settings records.
- `build_history.json`: export history, capped at 50 entries.

The shared `application_dir()` resolves beside `run.py` in source mode and beside the executable in frozen mode. The updater reuses this helper.

The documented reason for consolidation was to remove duplicated application-directory resolution and make persistence findable in one module. CLI settings memory remains opt-in for scripting determinism; GUI settings memory is automatic after successful builds.

Writes use a sibling temporary file, flush/fsync, and `os.replace()`. This does not provide cross-process locking, transactional multi-file updates, or automatic recovery. PID-based temporary names can collide between concurrent writes in one process. Hard termination can leave temporary files, and read-modify-write operations can lose concurrent updates.

Some convenience operations suppress errors. Named-profile writes and some history operations can propagate failures. Preference loading assumes a JSON object and truth-coerces values; valid JSON of the wrong shape can still fail, and a string such as `"false"` is truthy.

## Completeness and preservation boundaries

Completeness checks cover configured eligible source/text files, not every project file. Blocking reasons are `file_too_large`, `total_size_limit`, `size_unavailable`, and `read_unavailable`.

Intentional exclusions and unsupported extensions do not fail completeness. A PASS does not establish program correctness, test success, secret removal, immutable snapshot consistency, or full repository preservation. Failed optional hash/line-count reads can leave null metadata without failing completeness.

The tree is rendered separately using exclusions, not inclusion eligibility or byte budgets. It can show files absent from the index. Scanning traverses excluded descendants before rejecting files rather than pruning excluded directories at entry.

## Security and output limitations

- Redaction is heuristic and affects rendered text only. ZIP members retain original source bytes.
- Hashes describe original source bytes, not redacted Markdown.
- Root membership checks do not provide general resolved-path containment guarantees for symlinks.
- Absolute or parent-traversing output paths are not rejected by the builder.
- Custom output directory names are not automatically added to exclusions.
- Fixed triple-backtick source fences can be disrupted by embedded triple-backtick text.

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

Builds and network/update work run synchronously on the GUI thread. `update_idletasks()` refreshes pending display work but does not provide background execution or cancellation. Global mouse-wheel bindings in `scroll_frame.py` can interfere with other components.

## Validation and maintainer handoff

The included unittest suite covers extension normalization, redaction examples, unredacted reads, hashing, and root validation. It does not cover the full export pipeline, persistence, Git parsing, GUI, or updater.

```bash
python -m unittest discover -s tests -v
```

Run from the directory containing `run.py`. Changelog verification narratives are historical records, not substitutes for executable regression coverage. This documentation revision does not report a new test run.

Recommended maintainer checklist:

1. Read the README, this dependency map, and the relevant module headers.
2. Record the Python version and platform used for validation.
3. Run the included tests and record the actual result.
4. Perform the README's suggested smoke test on disposable fixture data.
5. Review skip records, completeness scope, settings, and ZIP contents separately.
6. Validate changed behavior with focused regression tests before claiming support.
7. Update module headers, README, architecture, and changelog together when behavior changes.

Recommended additional regression coverage: settings precedence and hidden-field handling; full export output; completeness failures; persistence corruption/concurrency; partial Git data; and updater failure/verification behavior. These are proposed validation priorities, not existing coverage.
