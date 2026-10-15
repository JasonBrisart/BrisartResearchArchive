# Project Context Helper

Project Context Helper is a standard-library Python utility within Brisart Research Archive. It packages a project folder into readable context, a machine-readable manifest, a summary, a settings record, and an optional ZIP containing included source files.

This README describes v4.0.0. The desktop interface is unchanged from v3.1.4; the export engine underneath was rebuilt to run in the background, read each file once with a configurable number of threads, and publish an export only when it is complete. Local exports work offline; optional legacy release checks and downloads require network access.

## Important boundaries

- **ZIP snapshots are not redacted.** Redaction affects rendered text only; included ZIP source files retain their original bytes.
- **Completeness is scoped.** PASS means no configured blocking skips were recorded for eligible source/text files. It does not mean every project file was preserved or the program was validated.
- **Exports are not immutable filesystem snapshots.** Each included file is read exactly once, so its hash, Markdown text, and ZIP copy always agree, but different files are read at slightly different moments.
- **Choosing a built-in profile resets hidden settings.** Settings the GUI does not display (custom extension/exclusion sets, worker count, Git history limit) are kept across builds and profile saves, until a different built-in profile is selected.
- **Legacy updater verification is conditional.** Missing or unsupported digests skip verification, despite stronger wording in some interface messages.

Review exports before sharing them, especially when source folders contain credentials or confidential material.

## Requirements

- A Python installation capable of running the supplied source.
- tkinter and a graphical display are required only to launch the desktop GUI; command-line exports do not import tkinter.
- Read access to the selected project and write access to the export location.
- Write access beside the application (or to `PCH_STATE_DIR`, see Persistence locations) for settings/profile/history persistence; some failed convenience saves are suppressed.

No third-party Python packages are imported by the supplied application. The supplied materials do not establish a tested Python-version or platform-support matrix; do not treat this README as certification of compatibility across environments.

## Quick start

Run commands from the directory containing `run.py`.

Launch the desktop interface:

```bash
python run.py
```

Export a project with the default archive preset:

```bash
python run.py "/path/to/project" --profile archive
```

Export without creating a ZIP:

```bash
python run.py "/path/to/project" --profile archive --no-zip
```

Use more capture threads and print progress to stderr:

```bash
python run.py "/path/to/project" --workers 8 --progress
```

Display available CLI flags:

```bash
python run.py --help
```

Use `run.py` as the supported source entry point rather than running individual component files.

## Generated files

By default, exports are written beneath the selected project:

```text
PROJECT_CONTEXT_EXPORTS/
`-- project_context_YYYYMMDD_HHMMSS/
    |-- PROJECT_CONTEXT.md
    |-- PROJECT_MANIFEST.json
    |-- PROJECT_SUMMARY.txt
    |-- PROJECT_CONTEXT_SETTINGS.json
    `-- PROJECT_SNAPSHOT.zip
```

The ZIP is optional. `--flat-output` disables timestamped subfolders and overwrites the generated files in the output folder, as in v3.1.4. A second export in the same second gets a `_2` (then `_3`, ...) suffix instead of sharing a folder.

While an export runs it is assembled in a hidden `.pch-build-*` folder inside the output folder and only moved into place when finished. A failed, stopped, or cancelled export leaves no partial folder behind. The output folder name must be a relative path inside the project; it is always left out of later scans and folder trees, whatever it is called.

| File | Contents |
|---|---|
| `PROJECT_CONTEXT.md` | Enabled human-readable sections, including optional embedded text. |
| `PROJECT_MANIFEST.json` | Settings, inclusion/skip records, metadata, completeness, and optional Git data. |
| `PROJECT_SUMMARY.txt` | Compact settings/counts/completeness overview. |
| `PROJECT_CONTEXT_SETTINGS.json` | Settings used for the export. |
| `PROJECT_SNAPSHOT.zip` | Generated outputs plus the captured original bytes of included files under `project_files/`. |

The manifest retains all skip records even when Markdown skipped details are capped. The folder tree is not an exact inclusion inventory. An excluded folder (for example `node_modules`) appears once in the skip records rather than once per file inside it, because excluded folders are no longer walked.

## Built-in profiles

| Behavior | standard | archive (default) |
|---|---|---|
| Maximum file size | 350000 bytes | 2000000 bytes |
| Maximum total size | 5000000 bytes | 100000000 bytes |
| ZIP and Markdown redaction | Enabled | Enabled |
| Folder tree and index | Enabled | Enabled |
| Embedded contents, hashes, line counts, skipped details | Disabled | Enabled |
| Required eligible-source completeness | Disabled | Enabled |
| Git inspection | Disabled | Disabled |
| Capture threads (`workers`) | 4 | 4 |

Intentional exclusions, unsupported extensions, and symlinks (which are never followed) do not fail completeness. Archive mode stops when eligible files hit configured blocking size/read failures, or when a file changes size between discovery and capture (`source_changed`).

To increase limits:

```bash
python run.py "/path/to/project" --profile archive --max-file-bytes 4000000 --max-total-bytes 150000000
```

CLI limits are bytes; GUI limits use decimal MB, where 1 MB is 1000000 bytes. `--workers` accepts 1 to 32; the worker count does not change which files are included, only how quickly they are read.

## Desktop interface

- **Build:** project selection, built-in profile selection, export execution, and last successful session export.
- **Options:** output folder, size limits, output sections, and folder-opening preference.
- **Extras:** optional Git inspection and named custom profiles.
- **About:** application information, recent export history, and legacy update preferences.

Options and Extras are scrollable. The tabs, controls, and dialogs are the same as v3.1.4.

Builds run in the background: the window stays responsive, the status bar shows the current phase and file count, and **Build Project Context** is disabled until the build finishes. Recent Exports on the About tab refreshes automatically after each successful build. There is no separate Cancel button; closing the window during a build asks for confirmation, cancels the build, and closes once cleanup is done. Update checks and downloads still run on the interface thread.

### Remembered settings

The GUI loads last-used export settings at startup and saves them after successful builds. Unsaved edits are not automatically persisted as last-used settings. Selecting a built-in profile reapplies its defaults.

The selected project folder is not restored. Settings the GUI does not display are kept from the last loaded settings (startup memory, a custom profile, or a preset) until a different built-in profile is selected.

The folder-opening and update preferences are stored separately and autosaved when changed. Some persistence failures are silently suppressed.

## CLI settings memory and named profiles

The CLI does not automatically remember or reload settings.

```bash
python run.py "/path/to/project" --remember-settings
python run.py "/path/to/project" --use-last-settings
python run.py "/path/to/project" --save-profile "Review"
python run.py "/path/to/project" --load-profile "Review"
python run.py --list-profiles
python run.py --delete-profile "Review"
```

Precedence is built-in preset, optional remembered settings, optional named profile, then explicit overrides. Missing named profiles produce a warning and leave the otherwise applicable settings in place.

Custom names are trimmed and remain case-sensitive. Built-in names are reserved case-insensitively. CLI saving overwrites an existing exact name; GUI saving asks for overwrite confirmation.

`--save-profile` requires an export root to save through the CLI flow. Without a root, it falls through to GUI launch. Standalone list/delete actions can return before later actions are reached.

## Optional Git context

```bash
python run.py "/path/to/repository" --git-state
```

Git inspection reads local metadata without an external Git executable. It checks `.git` at the selected root, not parent directories. Exporting a monorepo subfolder can therefore report that no repository was detected.

Packed objects, linked worktrees, index semantics, Git filters, and SHA-256 repositories are not fully supported. Warnings can coexist with clean/dirty output. Treat this section as supplementary context, not authoritative repository verification.

## Redaction and sharing

Both presets enable heuristic rendered-text redaction. It can miss secrets or redact benign lines. Hashes describe original bytes, not redacted text.

```bash
python run.py "/path/to/project" --profile archive --no-zip
```

Disabling ZIP creation avoids bundling original source files, but does not make the Markdown safe to share automatically. Review all outputs manually. `--no-redact` deliberately disables rendered-text redaction.

## Persistence locations

State files live beside `run.py` in source mode or beside the executable in frozen mode:

- `app_settings.json`
- `last_export_settings.json`
- `custom_profiles.json`
- `build_history.json`

Set the `PCH_STATE_DIR` environment variable to keep these files in another folder (the test suite uses this so it never touches real settings).

Clearing export history does not delete export folders. Writes use unique temporary files and atomic replacement, and profile/history updates are serialized with a short-lived `.pch-state.lock` file so simultaneous saves from several windows or processes do not overwrite each other. A lock left behind by a crashed process is ignored after 30 seconds. An unreadable `custom_profiles.json` is reported and left untouched instead of being overwritten. There is still no automatic corruption repair or multi-file transaction.

## Legacy updates

The current implementation retains legacy BrisartDevTools GitHub release endpoints. It does not implement archive-hosted update distribution.

Check without exporting:

```bash
python run.py --check-updates
```

Update checks/downloads require network access. Installation modifies application files and should be reviewed separately from export testing. Source updates back up and overwrite files but do not remove obsolete files or automatically roll back partial failures. Executable replacement is Windows-specific.

A supported supplied SHA256 digest is checked; absent or unsupported digests are skipped. Do not interpret an interface message as proof that verification occurred. Restarting alone does not apply an already-staged source ZIP.

For offline use, leave startup update checking and automatic installation disabled.

## Tests and suggested smoke test

Run the included utility regression tests:

```bash
python -m unittest discover -s tests -v
```

The suite has three parts:

- `test_export_safety_utilities.py`: the original v3.1.4 utility tests.
- `test_v4_engine.py`: full exports, ZIP/manifest hash agreement, sequential vs parallel capture, cancellation and failure cleanup, output-folder safety, pruning, symlinks, Markdown fences, settings parsing, locked persistence, CLI behavior, and Git State.
- `test_gui_wiring.py`: drives the real GUI modules against a recording tkinter stand-in (`fake_tk.py`) to check controls, background builds, dialogs, history refresh, hidden-setting retention, profiles, and closing mid-build.

The GUI tests do not open a real window; check the interface manually on your platform. The updater is not covered.

Suggested manual smoke test, not an existing automated test:

1. Prepare a disposable folder containing a small, nonsensitive `.py` or `.txt` file.
2. Run an archive export against that folder with `--no-zip`.
3. Confirm the four non-ZIP output files exist.
4. Inspect the manifest's included paths, skip reasons, settings, and completeness report.
5. Confirm the fixture content appears in the Markdown output.
6. If testing ZIP behavior, run a separate export with ZIP enabled and inspect its original source members.

Record the Python version, platform, command, and observed result. Do not extrapolate a successful fixture export into full security or platform validation.

## Troubleshooting

| Symptom | Check |
|---|---|
| GUI fails to open | tkinter availability and graphical-display access. |
| Archive export stops | Blocking skip reasons, configured limits, and file readability. |
| A file is missing despite PASS | Extension eligibility and intentional exclusions; PASS is scoped. |
| Tree and index differ | Tree rendering does not apply inclusion eligibility or byte limits. |
| Settings appear to reset | Built-in profile resets, successful-build-only memory, and hidden-field reconstruction. |
| Git metadata is missing | `.git` at the selected root and parser warnings/limitations. |
| Interface pauses | Builds run in the background; update checks and downloads still run on the interface thread. |
| A `.pch-build-*` folder remains | The process was killed or lost power mid-export; it is safe to delete when no export is running. |
| "Settings folder is busy" | Another Project Context Helper process is saving; retry. A stale lock clears itself after 30 seconds. |

Recommended practice: avoid changing source files during an export and inspect results before relying on them.

## Maintainer documentation

- [Architecture](ARCHITECTURE.md): actual dependencies, lifecycle, settings, persistence, and implementation boundaries.
- [Changelog](CHANGELOG.md): historical changes and verification narratives.
- Module headers: file-specific responsibilities, relationships, parameters, edge cases, limitations, and examples.