# Project Context Helper

Project Context Helper is a standard-library Python utility within Brisart Research Archive. It packages a project folder into readable context, a machine-readable manifest, a summary, a settings record, and an optional ZIP containing included source files.

This README describes the supplied v3.1.4 implementation. Local exports work offline; optional legacy release checks and downloads require network access.

## Important boundaries

- **ZIP snapshots are not redacted.** Redaction affects rendered text only; included ZIP source files retain their original bytes.
- **Completeness is scoped.** PASS means no configured blocking skips were recorded for eligible source/text files. It does not mean every project file was preserved or the program was validated.
- **Exports are not immutable filesystem snapshots.** Files can change between scanning, rendering, and ZIP creation.
- **GUI settings memory is limited to exposed controls.** Hidden custom settings can be discarded when the GUI rebuilds settings from a preset.
- **Legacy updater verification is conditional.** Missing or unsupported digests skip verification, despite stronger wording in some interface messages.

Review exports before sharing them, especially when source folders contain credentials or confidential material.

## Requirements

- A Python installation capable of running the supplied source.
- tkinter must be importable even for CLI operations, because the CLI imports the GUI at module load.
- A graphical display is required to launch the desktop GUI.
- Read access to the selected project and write access to the export location.
- Write access beside the application for settings/profile/history persistence; some failed convenience saves are suppressed.

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

The ZIP is optional. `--flat-output` disables timestamped subfolders.

| File | Contents |
|---|---|
| `PROJECT_CONTEXT.md` | Enabled human-readable sections, including optional embedded text. |
| `PROJECT_MANIFEST.json` | Settings, inclusion/skip records, metadata, completeness, and optional Git data. |
| `PROJECT_SUMMARY.txt` | Compact settings/counts/completeness overview. |
| `PROJECT_CONTEXT_SETTINGS.json` | Settings used for the export. |
| `PROJECT_SNAPSHOT.zip` | Generated outputs plus original included files under `project_files/`. |

The manifest retains all skip records even when Markdown skipped details are capped. The folder tree is not an exact inclusion inventory.

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

Intentional exclusions and unsupported extensions do not fail completeness. Archive mode stops when eligible files hit configured blocking size/read failures. Optional hash or line-count failures can leave null values without failing completeness.

To increase limits:

```bash
python run.py "/path/to/project" --profile archive --max-file-bytes 4000000 --max-total-bytes 150000000
```

CLI limits are bytes; GUI limits use decimal MB, where 1 MB is 1000000 bytes.

## Desktop interface

- **Build:** project selection, built-in profile selection, export execution, and last successful session export.
- **Options:** output folder, size limits, output sections, and folder-opening preference.
- **Extras:** optional Git inspection and named custom profiles.
- **About:** application information, recent export history, and legacy update preferences.

Options and Extras are scrollable. Builds and update work run synchronously and can make the interface unresponsive while work is in progress.

### Remembered settings

The GUI loads last-used export settings at startup and saves them after successful builds. Unsaved edits are not automatically persisted as last-used settings. Selecting a built-in profile reapplies its defaults.

The selected project folder is not restored. Custom extension/exclusion sets, custom Git history limits, and other hidden fields are not retained by GUI settings reconstruction.

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

Clearing export history does not delete export folders. Atomic replacement reduces partial-write exposure, but there is no locking, automatic corruption recovery, or transactional multi-file persistence.

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

The suite covers extension normalization, example redaction behavior, exact unredacted reads, hashing, and root validation. It does not validate the full export pipeline, GUI, persistence, Git parser, or updater. This documentation update does not claim a new passing test run.

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
| tkinter import failure during CLI launch | The current CLI imports GUI modules; tkinter must be available. |
| GUI fails to open | tkinter availability and graphical-display access. |
| Archive export stops | Blocking skip reasons, configured limits, and file readability. |
| A file is missing despite PASS | Extension eligibility and intentional exclusions; PASS is scoped. |
| Tree and index differ | Tree rendering does not apply inclusion eligibility or byte limits. |
| Settings appear to reset | Built-in profile resets, successful-build-only memory, and hidden-field reconstruction. |
| Git metadata is missing | `.git` at the selected root and parser warnings/limitations. |
| Interface pauses | Builds and update operations are synchronous. |
| Partial outputs remain | Export files are written sequentially, not transactionally. |

Recommended practice: keep the default export directory name. Custom names are not automatically excluded from later scans. The builder does not reject absolute or parent-traversing output paths. Avoid changing source files during an export and inspect results before relying on them.

## Maintainer documentation

- [Architecture](ARCHITECTURE.md): actual dependencies, lifecycle, settings, persistence, and implementation boundaries.
- [Changelog](CHANGELOG.md): historical changes and verification narratives.
- Module headers: file-specific responsibilities, relationships, parameters, edge cases, limitations, and examples.

Keep these documents aligned when implementation behavior changes. Documentation and historical verification narratives do not replace executable regression tests.
