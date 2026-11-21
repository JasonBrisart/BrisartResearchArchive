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
`-- PROJECT_SNAPSHOT.zip          optional: the four files above plus project_files/... (each file keeps its original modification time)
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

`auto` (the default) uses one thread per logical CPU core the system reports, up to 32, both to read and hash files and to compress the ZIP. An explicit count (`--workers 1` to `32`, or **Extras → Performance → CPU Cores**) is limited to the cores the current computer has. The thread count never changes which files are included. Settings files store what was requested. Each export reports what was used, for example `Capture workers: 8 (auto)` or `4 (requested 16, limited to available CPU cores)`, and as `summary.capture_workers` in the manifest.

## Desktop window

- **Build:** choose the project and profile, build, and open the last export. Builds run in the background with progress in the status bar. Closing the window during a build cancels it after asking first.
- **Options:** output folder, size limits, output sections, opening the folder after a build, and **Advanced Filters**: included extensions, excluded folders, files, and suffixes (comma- or line-separated), whether to stop when an eligible file cannot be captured, and the Git history limit. Every export setting now has a control, on Build, Options, or Extras.
- **Extras:** opt-in Git State, **Performance** (a CPU Cores selector listing Auto plus only the counts this computer can run, with a core meter and a readout such as *Using 3 of 8 cores*), named custom profiles, and Recent Exports.
- **View:** *What do you want to see?* Unselect any optional section (profile description, list of generated files, option descriptions, Advanced Filters, or any Extras section) to remove it: everything below it moves up to fill the space, and a tab only shows a scrollbar while its content is taller than the window. If you hide all four Extras sections, the Extras tab itself disappears; it returns between Options and View as soon as you show one. Selecting a section again puts it back in place. Hiding never changes a setting, and the choice is remembered. The window keeps the size you gave it.
- **About:** attribution.

The window remembers the settings from your last successful build. Picking `standard` or `archive` resets every export setting to that preset, including the Advanced Filters lists and CPU Cores (back to Auto).

### Custom profiles

A custom profile (Extras tab) saves **everything**: every export setting on all three tabs, the Advanced Filters lists, Open Export Folder After Build, which sections the View tab shows, and, if *Include the project folder when saving* is ticked (it is by default), the project folder. Loading a profile sets the whole window, so on a computer several people share, each person can keep a profile and load it instead of changing settings one by one. Untick the folder box for a profile meant to be shared across projects.

- A profile saved by the command line, or by v4.2.0 or earlier, has no window half. Loading it changes the export settings and leaves the View choices and Open Export Folder After Build as they are, and says so.
- A stored project folder that does not exist on the computer loading the profile is skipped, with a note.
- Saving over a profile from the command line replaces its settings and keeps the window half the window stored.
- Removing an entry from Excluded files or Excluded folders removes its protection: clearing `.env` from the files list exports it.

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

`app_settings.json`, `last_export_settings.json`, `custom_profiles.json`, and `build_history.json` live in a per-user folder shared with other Brisart Research Archive tools: `%APPDATA%\Brisart Research Archive\Project Context Helper` on Windows, `~/Library/Application Support/Brisart Research Archive/Project Context Helper` on macOS, and `~/.config/Brisart Research Archive/Project Context Helper` (or under `$XDG_CONFIG_HOME`) elsewhere. Set `PCH_STATE_DIR` to use any other folder, for example one beside the program on a USB drive. Releases up to v4.2.0 kept these files beside `run.py`; the first run of a newer release moves them (see below). Writes are atomic and locked, so several windows or processes can save at once. A lock left by a crashed process clears after 30 seconds. An unreadable `custom_profiles.json` is reported and left untouched. Clearing history never deletes export folders.

## Updates

The program has no built-in updater and makes no network connections. To update, replace the application folder with the new release. Your settings, profiles, and history are not in the application folder, so replacing it never touches them. Replace the folder rather than copying new files over it, so files a release removed do not linger and end up in exports of the tool's own folder. The first run after upgrading from v4.2.0 or earlier moves any state files from beside `run.py` into the per-user folder; if that cannot be done, a warning names both folders and the originals stay put. If a file already exists in the new folder, the older copy is left alone for you to delete.

## Tests

```bash
python -m unittest discover -s tests -v
```

| File | Covers |
|---|---|
| `test_export.py` | The engine end to end (outputs, hash agreement, thread-count parity, worker resolution, cleanup, output safety, redaction, Git), the parallel ZIP writer (including forced ZIP64 records), the fast line count and redaction against their reference rules, settings rules, and that `export/` loads without storage, the GUI, tkinter, or `urllib.request` |
| `test_storage.py` | Concurrent saves, corruption protection, preferences parsing, stale locks, history, the window half of custom profiles, the per-user folder on each platform, the one-time move from beside `run.py` (including four processes racing), and that `application/storage.py` does not load the scanner, renderer, or pipeline |
| `test_cli.py` | Real `run.py` runs (which hand off to `cli.py`), including history recording, `--workers` handling, the first-run move of saved settings from an older release, a window-saved profile loading from the command line, and that the command line loads no GUI or network module |
| `test_gui.py` | The real window modules against a recording tkinter stand-in (`fake_tk.py`), including the CPU Cores selector on 1-, 4-, and 64-core machines, which tab owns each section, the View tab hiding and restoring sections, every setting having a control (Advanced Filters), profiles saving and restoring the whole window, layout reflow, scrollbars that exist only when needed, the Extras tab disappearing when empty, plus the background job runner |

`support.py` holds the setup the test files share. The GUI tests do not draw a window, so check the interface by eye on your platform.

## Troubleshooting

| Symptom | Check |
|---|---|
| Window does not open | tkinter is installed and a display is available |
| Archive export stops | The blocking files listed, the size limits, and file permissions |
| A file is missing despite PASS | Its extension and the exclusions; PASS covers eligible files only |
| Folder tree shows files not in the index | The tree applies exclusions only, not extensions or size limits |
| "Build failed: ... must be a single name" or "include_extensions is empty" | Exclusions are bare folder or file names (not paths), extensions start with a dot, and at least one extension must be included; these used to be accepted and silently do nothing |
| Settings reset | Picking a built-in profile resets everything; last-used settings save only after a successful build |
| CPU Cores shows "4 cores" after upgrading | Settings saved by v4.0.x store 4; pick Auto once |
| A `.pch-build-*` folder remains | A process was killed mid-export; delete it when no export is running |
| "Settings folder is busy" | Another copy is saving; retry |
