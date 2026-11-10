# Project Context Helper

Project Context Helper is a Brisart Research Archive tool that packages a project folder into a readable context file, a machine-readable manifest, a summary, a settings record, and an optional ZIP of the included source files. It is pure Python with no third-party packages, never connects to the network, and runs from the command line or a desktop window, so it suits offline and air-gapped machines.

## Before you share an export

- **The ZIP is not redacted.** Redaction only affects the rendered text. ZIP members and hashes are the original bytes.
- **Completeness is scoped.** PASS means every *eligible* file (matching extension, not excluded) was captured. It does not mean every file in the folder was preserved, or that the program works.
- **An export is not an atomic snapshot.** Each file is read once, so its hash, text, and ZIP copy always agree, but different files are read at slightly different moments.

## Requirements

- Python 3 with the standard library. tkinter and a display are needed only for the desktop window; command-line exports never load tkinter.
- Read access to the project, and write access to it (exports go inside it) and to the application folder (or `PCH_STATE_DIR`) for remembered settings and history.

## Quick start

Run from the folder containing `run.py`:

```bash
python run.py                                   # open the desktop window
python run.py "/path/to/project"                # export with the archive profile
python run.py "/path/to/project" --no-zip       # export without the ZIP
python run.py "/path/to/project" --workers 4 --progress
python run.py --help
```

## Output

```text
<project>/PROJECT_CONTEXT_EXPORTS/project_context_YYYYMMDD_HHMMSS/
|-- PROJECT_CONTEXT.md            readable context, optionally with file contents
|-- PROJECT_MANIFEST.json         settings, every included and skipped file, completeness, Git
|-- PROJECT_SUMMARY.txt           short overview
|-- PROJECT_CONTEXT_SETTINGS.json the settings used
`-- PROJECT_SNAPSHOT.zip          optional: the four files above plus project_files/...
```

Each export is assembled in a hidden `.pch-build-*` folder and moved into place only when finished, so a failed or cancelled export leaves nothing half-written. A second export in the same second gets a `_2` suffix. `--flat-output` writes straight into the output folder, overwriting the previous files. The output folder must be inside the project, and it is always left out of later exports.

## Profiles

| | standard | archive (default) |
|---|---|---|
| Max file / total size | 350000 / 5000000 bytes | 2000000 / 100000000 bytes |
| Hashes, line counts, file contents, skipped details | off | on |
| Required completeness (stop if an eligible file is missing) | off | on |
| ZIP, redaction, folder tree, file index | on | on |
| Git State | off | off |
| CPU cores (`workers`) | auto | auto |

Command-line limits are bytes. The window uses decimal MB (1 MB = 1000000 bytes). Intentional exclusions, other extensions, and symlinks (never followed) do not fail completeness.

### CPU cores

`auto` (the default) reads files with one thread per logical CPU core the system reports, up to 32. An explicit count (`--workers 1` to `32`, or **Options → Performance → CPU Cores**) is limited to the cores the current computer has. The thread count never changes which files are included. Settings files store what was requested. Each export reports what was used, for example `Capture workers: 8 (auto)` or `4 (requested 16, limited to available CPU cores)`, and as `summary.capture_workers` in the manifest.

## Desktop window

- **Build:** choose the project and profile, build, and open the last export. Builds run in the background with progress in the status bar. Closing the window during a build cancels it after asking first.
- **Options:** output folder, size limits, **Performance** (a CPU Cores selector listing Auto plus only the counts this computer can run, with a core meter and a readout such as *Using 3 of 8 cores*), output sections, and opening the folder after a build.
- **Extras:** opt-in Git State and named custom profiles.
- **About:** attribution and Recent Exports.

The window remembers the settings from your last successful build. Picking `standard` or `archive` resets everything, including values the window does not show (custom extension and exclusion sets) and CPU Cores (back to Auto). Custom profiles save the complete settings.

## Command-line settings and profiles

```bash
python run.py "/path/to/project" --remember-settings      # store these settings as last-used
python run.py "/path/to/project" --use-last-settings
python run.py "/path/to/project" --save-profile "Review"
python run.py "/path/to/project" --load-profile "Review"
python run.py --list-profiles
python run.py --delete-profile "Review"
python run.py "/path/to/repository" --git-state
```

Later sources win: preset, then last-used, then named profile, then explicit flags. The command line never loads remembered settings unless asked to. Every successful export, from either interface, is added to Recent Exports.

## Remembered state

`app_settings.json`, `last_export_settings.json`, `custom_profiles.json`, and `build_history.json` live beside `run.py` (or the executable), or in `PCH_STATE_DIR` when that is set. Writes are atomic and locked, so several windows or processes can save at once. A lock left by a crashed process clears after 30 seconds. An unreadable `custom_profiles.json` is reported and left untouched. Clearing history never deletes export folders.

## Updates

The program has no built-in updater and makes no network connections. To update, replace the application folder with the new release. Your settings, profiles, and history files can stay beside `run.py`, or live in `PCH_STATE_DIR`. Replace the folder rather than copying new files over it, so files a release removed do not linger and end up in exports of the tool's own folder.

## Tests

```bash
python -m unittest discover -s tests -v
```

| File | Covers |
|---|---|
| `test_export.py` | The engine end to end (outputs, hash agreement, thread-count parity, worker resolution, cleanup, output safety, redaction, Git), settings rules, and that `export/` loads without storage, the GUI, tkinter, or `urllib.request` |
| `test_storage.py` | Concurrent saves, corruption protection, preferences parsing, stale locks, history, and that `storage` does not load the scanner, renderer, or pipeline |
| `test_cli.py` | Real `run.py` runs (which hand off to `cli.py`), including history recording, `--workers` handling, and that the command line loads no GUI or network module |
| `test_gui.py` | The real window modules against a recording tkinter stand-in (`fake_tk.py`), including the CPU Cores selector on 1-, 4-, and 64-core machines, plus the background job runner |

`support.py` holds the setup the test files share. The GUI tests do not draw a window, so check the interface by eye on your platform.

## Troubleshooting

| Symptom | Check |
|---|---|
| Window does not open | tkinter is installed and a display is available |
| Archive export stops | The blocking files listed, the size limits, and file permissions |
| A file is missing despite PASS | Its extension and the exclusions; PASS covers eligible files only |
| Folder tree shows files not in the index | The tree applies exclusions only, not extensions or size limits |
| Settings reset | Picking a built-in profile resets everything; last-used settings save only after a successful build |
| CPU Cores shows "4 cores" after upgrading | Settings saved by v4.0.x store 4; pick Auto once |
| A `.pch-build-*` folder remains | A process was killed mid-export; delete it when no export is running |
| "Settings folder is busy" | Another copy is saving; retry |
