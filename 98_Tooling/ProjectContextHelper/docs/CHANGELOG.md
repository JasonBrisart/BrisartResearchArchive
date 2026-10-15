# Changelog

All notable changes to Project Context Helper are documented here.

---

## [4.0.1] - 2026-10-15

Attribution update. Everything the application shows or exports now credits Jason Brisart and Brisart Research Archive, and the GitHub repository link has been removed. No export, scanning, or GUI behavior changed otherwise.

### Changed
- **The GitHub link is replaced with Brisart Research Archive.** The window subheader now reads `v4.0.1 • Jason Brisart • Brisart Research Archive`. The About tab shows `Author: Jason Brisart` followed by `Brisart Research Archive`. `PROJECT_CONTEXT.md` writes `Affiliation: **Brisart Research Archive**` and `PROJECT_SUMMARY.txt` writes `Affiliation: Brisart Research Archive`, where both previously wrote the GitHub repository location.
- **Manifest attribution field.** `PROJECT_MANIFEST.json` writes `"affiliation": "Brisart Research Archive"` instead of `repository_name` and `repository_url`. `author` is unchanged.
- **Constants.** `core/constants.py` replaces `REPOSITORY_NAME` and `REPOSITORY_URL` with `AFFILIATION`. `core/exporters.py`, `gui/about_tab.py`, and `gui/main_gui.py` use `AUTHOR` and `AFFILIATION` for attribution.
- `APP_VERSION` is now `4.0.1`.

### Removed
- **Open Releases Page button** on the About tab. It only opened the GitHub releases page.

### Notes
- **Manifest consumers:** anything that reads `repository_name` or `repository_url` from `PROJECT_MANIFEST.json` should read `affiliation` instead. No other output or state format changed.
- **Updater unchanged:** `services/updater.py` still checks the BrisartDevTools GitHub releases, and `--open-releases` still opens that page during an update check. The link is no longer shown in the interface or written into exports.
- **Docs and tests:** `docs/README.md` and `docs/ARCHITECTURE.md` describe the new attribution. Tests verify the new author/affiliation metadata, absence of the GitHub link from exports, and removal of the About-tab releases button.

---

## [4.0.0] - 2026-10-15

A rebuild of the export engine underneath an unchanged desktop interface. The v3.1.4 folder layout, file names, four tabs, controls, dialogs, presets, output file names, and state file names are all kept. What changed is how an export runs: in the background, with each file read exactly once by a configurable number of threads, assembled in a hidden staging folder, and published only when complete. This release also fixes a set of persistence and output-safety problems found while reworking those paths.

Major version because existing setups can behave differently: symlinked files are no longer followed, output folder names that are absolute or contain `..` are now rejected, excluded folders produce one skip record instead of one per file, and `create_context(root)` without settings now uses the archive preset instead of empty raw settings.

### Added
- **Background builds in the GUI.** New `gui/jobs.py` runs each export on a worker thread. The window stays responsive, the status bar shows the current phase and file count, and **Build Project Context** is disabled until the build finishes. The worker never touches tkinter; it reports through a queue that the Build tab polls every 80 ms. Layout, labels, and dialogs are unchanged.
- **Safe close during a build.** Closing the window while a build runs asks for confirmation, cancels the build, and closes once the staging folder has been cleaned up.
- **Parallel single-read capture.** `core/scanner.py` reads every included file exactly once with a thread pool (`workers`, default 4, 1–32) in bounded batches. The SHA256, line count, embedded Markdown text, and ZIP member all come from those same bytes. In v3.1.4 a file was read up to four separate times, so a file edited mid-export could have a hash that matched neither the Markdown nor the ZIP.
- **Staged publication.** `core/builder.py` writes everything into a hidden `.pch-build-*` folder inside the output folder and renames it into place only when finished. A completeness stop, cancellation, or error leaves no partial export behind.
- **Cancellation and progress.** New `core/events.py` (`Progress`, `BuildCancelled`, `checkpoint`). `create_context()` accepts an optional cancellation `Event` and progress callback.
- **`workers` setting.** New `ScanSettings.workers` field, saved in profiles and last-used settings. Files saved by v3.x load with the default of 4. Not shown in the GUI.
- **CLI `--workers N` and `--progress`.** `--progress` prints phases to stderr so stdout output is unchanged.
- **`PCH_STATE_DIR` environment variable** to keep the four state files in another folder.
- **New skip reasons.** `source_changed` and `directory_unavailable` (both completeness failures); `symlink_not_followed`, `not_a_regular_file`, `export_output_directory`, and `internal_tool_file` (intentional exclusions).
- **Tests.** `tests/test_v4_engine.py` (34 tests: engine, persistence, CLI, worker) and `tests/test_gui_wiring.py` (6 tests driving the real GUI modules through the recording tkinter stand-in `tests/fake_tk.py`).

### Changed
- **Excluded folders are pruned instead of walked.** v3.1.4's `root.rglob("*")` visited every file under `node_modules`, `.venv`, `PROJECT_CONTEXT_EXPORTS`, and so on, then rejected each one. The new walk records the folder once and never enters it. On this project's own 2026-10-15 snapshot, the 59 per-file skip records for `__pycache__` and `PROJECT_CONTEXT_EXPORTS` become 5 folder-level records (confirmed by the first v4.0.0 export on Windows: 62 total skips down to 8).
- **The GUI keeps settings it does not display.** v3.1.4 rebuilt settings from the built-in preset on every build and every profile save, silently dropping custom extension/exclusion sets, the Git history limit, and anything else loaded from a CLI-saved profile. `gui/builders.py` now starts from the last fully loaded settings when the profile matches the dropdown. Picking a different built-in profile still resets everything, as before.
- **Recent Exports refreshes after each successful build.**
- **Export folder names are unique.** A second export in the same second gets `_2`, `_3`, … instead of writing into the first one's folder.
- **The CLI no longer imports tkinter for exports.** The GUI is imported only when no project folder is given.
- **CLI errors.** Any `OSError` during a build now prints `Build failed: …` and exits 1 instead of a traceback. Ctrl+C exits 130 with no partial export. A failed `--save-profile` is reported without failing the finished export.
- **`create_context(root)` without settings uses the archive preset.** v3.1.4 used raw `ScanSettings()`, whose empty extension list produced an empty export.
- **State temp files use a `.pch-` prefix,** which the scanner always skips.
- `APP_VERSION` is now `4.0.0`.

### Fixed
- **Output folder names could point outside the project.** `output_dir_name` was joined onto the root without checks, so an absolute path or `..\elsewhere` (from the Options tab, `--output-dir`, or a hand-edited profile) wrote exports anywhere on disk. Names must now be relative paths that resolve inside the project.
- **Custom output folders were swept into later exports.** Only the default `PROJECT_CONTEXT_EXPORTS` name was excluded, so with a custom name every later archive export re-included all earlier exports. The configured output folder is now always excluded from the scan, the folder tree, and Git State, whatever it is called.
- **Embedded Markdown fences broke `PROJECT_CONTEXT.md`.** Contents used a fixed ```` ``` ```` fence, so any embedded file containing ```` ``` ```` (this project's own README and ARCHITECTURE both do) closed the block early and corrupted rendering for the rest of the document. Fences are now longer than the longest backtick run in the file. File headings in that section are also escaped like table cells.
- **Concurrent profile/history saves lost updates.** Two saves at the same time (two windows, GUI plus CLI, or the new worker plus a profile save) could each read the old file, and the second write discarded the first one's change. Profile and history read-modify-write operations now run under `state_lock()` (in-process lock plus an `O_EXCL` lock file; 5 s wait; a lock older than 30 s is treated as abandoned).
- **Temp file names could collide.** `_atomic_write()` used `.<name>.tmp<PID>`, identical for two threads in one process. It now uses `tempfile.mkstemp`.
- **A corrupted `custom_profiles.json` was overwritten.** It loaded as empty, so the next save replaced the file with only the new profile, losing every other profile. Saves and deletes now refuse to touch an unreadable file and report the problem.
- **`app_settings.json` parsing.** A JSON list or `null` raised instead of falling back to defaults, and a string such as `"false"` was treated as `True`. Only real JSON booleans are accepted now.
- **`build_history.json` with the wrong shape** (an object, or non-object items) could raise; it now loads as empty or skips bad items.
- **`"--5"` in a saved integer field crashed settings loading** with `ValueError` from `int()`. Malformed values are now discarded like other invalid fields.
- **Clearing history, saving a profile, or deleting a profile could raise an unhandled error in the GUI** on a filesystem or lock failure. Each now shows an error dialog.

### Notes
- **GUI unchanged.** Same four tabs, controls, wording, decimal-MB fields, profile-reset behavior, and dialogs. There is no Cancel button, to keep the layout; closing the window cancels a running build.
- **Output and state formats are compatible.** Same output and state file names. The manifest keeps the v3.1.4 shape; it gains a `workers` setting and two more entries in `failure_reasons`. Folder-level skip records replace per-file ones for excluded folders.
- **Symlinks are no longer followed.** v3.1.4 included symlinked files; they are now skipped as an intentional exclusion. Copy the real files into the project if they need to be exported.
- **Flat output** still overwrites the generated files in the output folder, as in v3.1.4. With ZIP disabled, an older `PROJECT_SNAPSHOT.zip` there is left untouched.
- **Not changed:** `core/git_state.py`, `services/updater.py` (still pointed at BrisartDevTools GitHub releases), redaction behavior, and presets. Update checks and downloads still run on the interface thread.
- **Not an atomic snapshot.** Each file is read once, but different files are read at slightly different moments. A hard kill or power loss can leave a `.pch-build-*` folder; later scans skip it and it can be deleted.
- **Validation.** 48 tests pass on Python 3.12 Linux (8 original, 34 engine/persistence/CLI/worker, 6 GUI wiring). The GUI tests use a tkinter stand-in, not a real display. The first v4.0.0 archive export of this project on Windows completed with source completeness PASS (29 files included, 4 workers, no leftover staging).
- No new external dependencies were introduced.

---

## [3.1.4] - 2026-09-03

A single, targeted edge-case fix in Git State detection, found while
auditing the codebase for the same class of bug already caught and
fixed elsewhere in v3.1.2. No CLI flag, GUI control, file format, or
public function signature changed.

### Fixed

- **Directory and file exclusion matching inside Git State's dirty-tree comparison was case-sensitive, independently of the identical bug already fixed in `core/scanner.py` back in v3.1.2.** `core/git_state.py`'s `compute_working_tree_status()` compared directory names (`part in exclude_dirs`) and file names (`relative_parts[-1] in exclude_files`) with exact, case-sensitive matching. This function is a separate, independent implementation from `core/scanner.py`'s `exclusion_reason()` — it has to be, since it's comparing the working tree against git's tracked blob shas rather than deciding what belongs in an export — so the v3.1.2 fix to `exclusion_reason()` never touched this one. On a case-preserving-but-case-insensitive filesystem (the Windows default, and optionally macOS), a folder actually named `Build`, `Node_Modules`, or `Venv` was not recognized as excluded here, even though `core/scanner.py` already correctly excludes such a folder from the export itself. Every file inside a mismatched-case folder like this — frequently hundreds or thousands of build artifacts or dependency files — was walked anyway, and since such files are normally gitignored (absent from `tracked_blobs`), each one was reported as **"untracked"** in the Git State section, while the same folder's contents were correctly absent from the File Index and Included File Contents sections earlier in the same document.

### Changed

- `compute_working_tree_status()` now compares directory-name and file-name exclusions case-insensitively, using the same `.lower()` normalization already applied to suffix/extension matching in `core/scanner.py`.

### Notes

- Backward compatible: no change to any JSON file's schema, any CLI flag's name or meaning, or any function's public signature.
- Verified with a real `Node_Modules/` folder (populated with several files) alongside a genuinely modified tracked file in the same repository: before the fix, every file under `Node_Modules/` appeared in the "Untracked" list; after the fix, they're correctly excluded from the walk entirely, while the real modified tracked file still correctly appears in "Modified or deleted since HEAD."
- No new external dependencies were introduced.

---

## [3.1.3] - 2026-08-26

### Fixed
- Removed unused imports left behind in several Project Context Helper modules.
- Eliminated dead code references that were no longer used by the application.

### Code Cleanup
The following unused imports were removed:

- `ProjectContextHelper/core/exporters.py`
  - Removed: `SkipRecord`

- `ProjectContextHelper/gui/build_tab.py`
  - Removed: `from pathlib import Path`

- `ProjectContextHelper/gui/dialogs.py`
  - Removed: `import tkinter as tk`

### Maintenance
- Reduced lint warnings caused by unused imports.
- Improved overall code cleanliness and maintainability.
- No functional changes were made to export generation, GUI behavior, scanning workflows, archive creation, or project analysis features.

### Notes
- This is a hotfix maintenance release focused exclusively on dead code removal and housekeeping.
- No user-facing behavior changes are expected.
- Existing exports, manifests, snapshots, and GUI workflows remain unchanged.
``

---

## [3.1.2] - 2026-08-22

A second dedicated edge-case bug-fixing pass — seven more issues
found and fixed in one cycle, each verified with a concrete
reproduction before and after the fix. No CLI flag, GUI control,
file format, or public function signature changed; every fix is
either purely internal or adds a new, previously-missing validation
error message.

### Fixed
- **Git branch names containing a slash were silently truncated, breaking HEAD-commit resolution entirely.** `core/git_state.py`'s `read_head_ref()` previously extracted the branch name by taking only the last path segment of the ref (`ref_path.rsplit("/", 1)[-1]`) — wrong for any branch following the extremely common `type/name` convention (`feature/login-page`, `bugfix/null-check`, `release/1.0`, `users/name/experiment`). For a HEAD pointing at `refs/heads/feature/test`, this previously returned `"test"` instead of `"feature/test"` — not just a cosmetically wrong branch name shown to the user, but a value that `resolve_branch_sha()` then used to look up a ref file that doesn't exist (`refs/heads/test` instead of the real `refs/heads/feature/test`), causing Git State detection to silently fail to resolve a HEAD commit, dirty status, or commit history at all for any such branch, with no error or warning anywhere. The branch name is now derived by stripping the known `refs/heads/` prefix instead of guessing at path segments, so the full branch name — slashes and all — is preserved correctly. Verified end-to-end against a real repository checked out on `feature/login-page`: branch name, HEAD commit, dirty status, and recent commit history all now resolve correctly, where every one of them previously silently failed; a plain single-segment branch name (`master`/`main`) was re-confirmed to still work exactly as before.
- **Markdown backtick-escaping was missing, and the existing pipe/newline escaping was never applied to Git State's file paths or commit messages at all.** `core/exporters.py`'s `escape_table_cell()` already escaped `|` and collapsed embedded newlines, but every call site wraps its result in a single pair of backticks to render it as inline code — so a value containing a literal backtick (a valid filename character on Linux/macOS, e.g. `weird`file.py`, and an extremely ordinary thing to find in a real git commit message, e.g. `` Fix `foo()` bug ``) prematurely closed the intended code span, corrupting the rendered line and undoing the protection already in place against pipe characters. Separately, the modified/untracked file paths and recent commit summaries rendered in the Git State markdown section were never passed through `escape_table_cell()` at all — not even for pipes or newlines — despite being wrapped in backticks the same way every table cell is. Backticks are now replaced with a single quote (consistent with this function's existing philosophy of prioritizing rendered output correctness over exact character fidelity for values that were always adversarial edge cases), and `escape_table_cell()` is now applied to Git State's modified/untracked file paths and commit lines as well. Verified with a real file named with an embedded backtick (File Index table renders correctly, no corrupted columns) and a simulated commit message containing backticks (`` Fix `foo()` bug `` renders as `Fix 'foo()' bug`, correctly neutralized instead of breaking the bullet list).
- **A corrupted or maliciously crafted `packed-refs` file could cause a filesystem path to be built from unvalidated, attacker-influenced text.** `core/git_state.py`'s `read_loose_object()` builds a path directly from whatever sha-like string it's given (`git_dir / "objects" / sha[:2] / sha[2:]`), with no check that the string is actually a plausible hex object id. Since `packed-refs` is a plain, hand-editable text file, a corrupted or crafted entry could supply something like `../../../../etc/passwd` as the "sha," which `Path`'s join semantics would happily follow outside the repository's `objects/` directory. New `is_valid_sha()` validates that any value is a plausible-length, pure-hex string before it's ever used to construct a path, applied both in `read_loose_object()` directly and in `resolve_branch_sha()` before a value read from a loose ref or `packed-refs` is trusted. Verified with a simulated `packed-refs` entry containing a `../../../../etc/passwd`-style payload in place of a real sha: confirmed it's now rejected outright rather than used to build a path, while real repositories with legitimate 40-character hex shas continue to resolve exactly as before.
- **Directory and file exclusion matching was case-sensitive, inconsistent with suffix and extension matching in the very same function, which already normalized case.** `core/scanner.py`'s `exclusion_reason()` compared directory names (`part in settings.exclude_dirs`) and file names (`path.name in settings.exclude_files`) with exact, case-sensitive matching, while two lines later it already lowercases the suffix before comparing it against `exclude_suffixes` — and `is_configured_source_file()` elsewhere in the same file already matches include-extensions case-insensitively by construction. On a case-preserving-but-case-insensitive filesystem (the Windows default, and optionally macOS), a folder actually named `Build`, `Node_Modules`, or `Venv` would silently not be excluded by the default lowercase `"build"` / `"node_modules"` / `"venv"` entries, even though the OS itself treats those names as identical to their default-cased counterparts. Directory-name and file-name exclusion now compare case-insensitively too. Verified with real folders named `Build/` and `Node_Modules/` in a test project: both are now correctly excluded, where the prior case-sensitive comparison demonstrably would have let them through.
- **A crash or power loss partway through an atomic settings write left its own temporary file behind permanently.** `services/storage.py`'s `_atomic_write()` (introduced in v3.1.1 specifically to prevent partially-written state files) writes to a sibling temp file before swapping it into place — but if anything failed between creating that temp file and the swap completing (disk full, a permissions error, an interrupted `fsync`), the temp file itself was left sitting in the application folder forever, with no cleanup attempted. This is more than clutter: this folder is the same folder this tool is commonly pointed at to export itself, and a dynamically-named leftover like `.custom_profiles.json.tmp12345` doesn't match any exact entry in the static `DEFAULT_EXCLUDE_FILES` list, so it could silently appear in a later export's skip list, or worse, get swept in as an included file. The write is now wrapped so any failure removes its own temp file before the original exception is re-raised. Verified by simulating an `os.replace()` failure directly: confirmed the exception still propagates as expected, and confirmed zero temp files are left behind afterward, where they previously would have been.
- **A corrupted or truncated update download was silently treated as a successful no-op instead of a failure.** `services/updater.py`'s `download_update()` caught `zipfile.BadZipFile` during extraction and simply ignored it (`except zipfile.BadZipFile: pass`), then returned the destination folder as if extraction had succeeded. Downstream, `apply_staged_update()` would find nothing in that folder but the raw, invalid `download.zip` itself — which is explicitly skipped by name during the apply step — meaning the entire update flow would complete "successfully" having applied exactly zero files, with both the CLI and GUI reporting a normal-looking "Files updated: 0" instead of any indication that the download itself had failed. `download_update()` now raises a clear, descriptive error when the downloaded data isn't a valid zip archive. Verified with simulated corrupted download bytes: confirmed a clear `ValueError` is now raised instead of silently returning a directory containing nothing usable.
- **The CLI's update-check flow had no exception handling at all around downloading and applying an update, unlike the equivalent GUI flow and unlike this file's own main build flow.** `cli/cli.py`'s `run_update_check()` called `download_update()`/`apply_staged_update()`/`stage_exe_update()`/`apply_exe_update()` directly with no surrounding try/except, so any failure from those functions (including the newly-raised `BadZipFile` error above, or a checksum mismatch, or a filesystem error while backing up files) would crash the command with a raw Python traceback — inconsistent with every other error path in this file, all of which print a clean one-line message. The download/apply portion of the update-check flow is now wrapped identically to the main build flow, printing `Update failed: ...` and exiting with status 1 instead of crashing. Verified with a simulated `download_update()` failure: confirmed the CLI now prints a clean error message and exits 1, instead of an unhandled traceback.

### Notes
- All seven fixes are backward compatible: no change to any JSON file's schema, any CLI flag's name or meaning, or any function's public signature.
- The branch-name fix (first item above) is the highest-impact fix in this round: it silently broke Git State detection for any branch following an extremely common, everyday naming convention, with zero indication anything was wrong — a build would simply show no branch, no HEAD commit, and no dirty status, which could easily be mistaken for "this isn't a git repository" rather than "the branch name was parsed incorrectly."
- Every fix above was verified with an actual reproduction of the bug both before and after the change, not merely inferred from reading the code, including a real git repository checked out on a slash-containing branch, a real file with an embedded backtick, a simulated malicious `packed-refs` entry, real differently-cased folders, a simulated failed atomic write, and simulated corrupted update-download bytes.
- No new external dependencies were introduced.

---

## [3.1.1] - 2026-08-22

A dedicated edge-case bug-fixing pass across the whole codebase — ten
issues found and fixed in one cycle, each verified with a concrete
reproduction before and after the fix (not just read-through). No
CLI flag, GUI control, file format, or public function signature
changed; every fix is either purely internal or adds a new,
previously-missing validation error message.

### Fixed
- **Markdown tables broke on filenames containing a pipe character.** `core/exporters.py`'s File Index, Skipped File Details, and Source Completeness Failures tables placed raw file paths and skip-reason strings directly between `|` delimiters with no escaping. A filename containing a literal `|` — perfectly valid on Linux/macOS (e.g. `notes|draft.txt`) — silently corrupted the rendered table (columns shifted or a row split in two), with no error anywhere. New `escape_table_cell()` escapes `|` to `\|` and collapses embedded newlines/carriage-returns to a single space before any value is placed in a table cell. Verified with a real file named `weird|file.py`: confirmed the File Index row now renders as `` | `weird\|file.py` | 12 | `` — three real column delimiters, the embedded pipe correctly neutralized.
- **The folder-tree renderer could produce corrupted output — or, on some filesystems, crash — on a cyclical symlink.** `core/scanner.py`'s `build_tree()` walks directories manually via `iterdir()` with no protection against a symlinked directory that loops back to one of its own ancestors (e.g. a stray `ln -s .. loop`). `collect_included_files()` is unaffected (`Path.rglob()` doesn't descend into symlinked directories), but the tree renderer had no equivalent guard. Verified directly against a real cyclical symlink: the unfixed code produced a nonsensically duplicated tree (the same subdirectory nested inside itself dozens of times, 124 lines for a 2-file project) that only stopped because the accumulating path eventually exceeded the OS path-length limit and `iterdir()` raised an `OSError` — already caught elsewhere in the function, so the corrupted output was returned with no warning at all. On a filesystem/OS combination with a more generous path-length allowance, the same cycle would instead exhaust Python's call-stack limit and crash with a `RecursionError`. Each directory's resolved real path is now tracked during the walk; revisiting one already on the current path is reported directly in the tree as `(symlink loop, not expanded)` instead of being descended into again.
- **The CLI crashed with a raw Python traceback instead of a clean error message on several expected failure conditions.** `run_cli()` in `cli/cli.py` had no error handling around building settings or running the export at all. A nonexistent project folder (`validate_root()` raises `FileNotFoundError`/`NotADirectoryError`), an archive-mode source-completeness failure (`collect_included_files()` raises `ValueError`), or an invalid size-limit flag (see below) would previously exit with a full traceback — inconsistent with every other error path in the file, which prints a one-line message. These three exception types are now caught, printed cleanly, and the process exits with status 1 — the behavior a shell script or CI pipeline invoking this tool would expect from a real, reportable failure. Verified against a nonexistent folder and a real archive-mode "file too large" failure: both now print a clean `Build failed: ...` line and exit 1, no traceback.
- **`--max-file-bytes` / `--max-total-bytes` (CLI) and the Max File MB / Max Total MB fields (GUI) silently accepted zero or negative values.** A non-positive size limit makes every real file look "too large" during scanning, silently producing an empty export in `standard` profile or a wall of source-completeness failures in `archive` profile — with nothing anywhere indicating that an unusable size limit was the actual root cause. Both interfaces now reject non-positive values immediately with a clear message (`--max-file-bytes must be a positive integer (got -100).` / `Max File MB must be greater than zero.`). Verified with `--max-file-bytes -100` and `--max-total-bytes 0` on the CLI, and directly against `gui/builders.py`'s `parse_mb_to_bytes()`.
- **The GUI's Max File MB / Max Total MB fields could crash with an uncaught `OverflowError` on an absurdly large input.** `parse_mb_to_bytes()` only caught `ValueError` around `int(float(value) * 1_000_000)`. Typing something like `1e400` makes `float(value)` return `inf` (a valid float, no exception), and `int(inf)` then raises `OverflowError` — a different exception class the original code never caught, crashing the GUI instead of showing "must be numeric." Also affected: `nan` was previously accepted as a "valid" float before failing later in an uncontrolled way. Both `inf`/`-inf` and `nan` are now explicitly rejected up front with a clear message, and the final `int()` conversion catches both `ValueError` and `OverflowError`. Verified with `"1e400"` and `"nan"` as input: both now raise a clean `ValueError` with a friendly message instead of an uncaught `OverflowError`; a normal valid value (`"2.5"` → `2500000`) still works exactly as before.
- **A crash or power loss mid-write to any persisted state file could silently and permanently destroy it.** Every write in `services/storage.py` (`app_settings.json`, `last_export_settings.json`, `custom_profiles.json`, `build_history.json`) previously used a plain `path.write_text(...)`, which is not atomic. If the process was killed at exactly the wrong moment, the file was left truncated — and since every loader in this module already treats "file exists but isn't valid JSON" identically to "no file was ever saved," a truncated `custom_profiles.json` would silently and permanently look like every saved Custom Profile had simply never existed, with no error or warning anywhere. New `_atomic_write()` helper writes to a sibling temp file, flushes and `fsync`s it, then swaps it into place with `os.replace()` — atomic on both POSIX and Windows, so a reader can never observe a partially-written file. Verified by simulating a truncated write directly (confirmed it fails to parse, reproducing the exact silent-data-loss scenario) and then stress-testing 20 rapid `save_profile()` calls through the new atomic path: zero leftover temp files, all 21 profiles present and correct afterward.
- **A settings file with a field of the wrong type (e.g. `max_file_bytes` saved as the string `"350000"` instead of the integer `350000`) crashed the build with an unhandled `TypeError` far from the actual cause.** `ScanSettings.from_jsonable()` previously accepted any dict shape without checking field types, so a hand-edited or corrupted `custom_profiles.json`/`last_export_settings.json` could produce a `ScanSettings` that looked fine at load time but crashed deep inside `core/scanner.py` the first time that field was compared against a real file's integer size (`'>' not supported between instances of 'int' and 'str'`). Numeric fields are now coerced from compatible strings/floats or discarded (falling back to the field's normal default) if they can't be coerced; boolean fields, `profile`, and `output_dir_name` are validated similarly; set-like fields (`include_extensions`, etc.) now filter out any non-string entries instead of accepting them as-is. Verified end-to-end: a settings dict with `max_file_bytes` as the string `"350000"` now loads as the integer `350000` and a real scan using it completes successfully — confirmed this exact input would have raised an uncaught `TypeError` inside `collect_included_files()` prior to the fix.
- **A malformed/truncated git tree object could raise an unhandled `ValueError` inside Git State detection.** `core/git_state.py`'s `parse_tree_object()` used `content.index(b" ", i)` / `content.index(b"\x00", ...)` with no bounds checking; a corrupted or truncated tree object (e.g. from a partially copied `.git` folder) previously crashed with a `ValueError` that only avoided taking down the whole build because `build_git_state()`'s outer wrapper happens to catch bare `Exception` — meaning a single malformed tree turned off Git State entirely with a vague "detection failed unexpectedly" message instead of degrading gracefully for just that one sub-tree, the way this module already does for packed/missing objects elsewhere. Malformed entries are now skipped and the walk stops cleanly for that tree instead of raising. Verified directly against a deliberately truncated tree object (missing bytes in the trailing sha): confirmed it now returns an empty entry list instead of raising.
- **A corrupted git repository with a cyclical commit parent chain could cause the recent-commits walk to behave unpredictably.** `core/git_state.py`'s `collect_recent_commits()` had no protection against a commit graph corruption where a parent pointer loops back to an earlier commit already visited in the same walk. Bounded by the `limit` parameter so this could never be a true infinite loop, but it could silently repeat commits in the output with no indication anything was wrong. A set of seen commit shas is now tracked; a repeat is detected and reported as a warning, and the walk stops at that point instead of continuing to cycle. Verified with a synthetic two-commit cycle (`A`'s parent is `B`, `B`'s parent is `A`): confirmed the walk correctly stops after 2 commits with a `"detected a repeated commit sha"` warning, instead of only being saved by the unrelated `limit` parameter.
- **A literal `%` character in an installation path could corrupt the Windows self-update batch script.** `services/updater.py`'s `build_apply_batch_script()` interpolated raw file paths directly into `set "VAR=..."` lines. Windows batch files treat `%` as the start of a variable reference even inside quotes, so an install path containing a percent sign (a valid Windows filename character — e.g. a folder someone named "50% Done") would have part of the path silently substituted by `cmd.exe` at update time, potentially corrupting the exe-swap step of a self-update. New `_escape_batch_path()` doubles every `%` (the standard batch-escaping rule) before a path is embedded in the script. Verified with a path containing `50% Done`: confirmed the generated script now contains `50%% Done` (correctly escaped) instead of the raw, exploitable `50% Done`.

### Notes
- All ten fixes are backward compatible: no change to any JSON file's schema, any CLI flag's name or meaning, or any function's public signature. A `last_export_settings.json` or `custom_profiles.json` written by v3.1.0 loads identically under v3.1.1.
- Every fix above was verified with an actual reproduction of the bug (a real cyclical symlink, a real truncated write, a real oversized/negative CLI flag, a real corrupted git object, etc.) both before and after the change, not merely inferred from reading the code.
- No new external dependencies were introduced; `_atomic_write()` uses only `os.replace()` and `os.fsync()` from the standard library, both already available on every platform this tool targets.

---

## [3.1.0] - 2026-08-22

### Changed — Consolidated All Settings/Profile/History Persistence Into One File
- **All saving and loading logic for App Preferences, Last Used Settings, Custom Profiles, and Build History is now in a single module: `services/storage.py`.** Previously this same functionality was spread across four separate files:
  - `services/app_settings.py` → App Preferences (`app_settings.json`)
  - `services/settings_memory.py` → Last Used Settings (`last_export_settings.json`)
  - `services/profile_manager.py` → Custom Profiles (`custom_profiles.json`)
  - `services/history.py` → Build History (`build_history.json`)
  
  All four of these files have been **removed**. Every function they exposed (`AppPreferences`, `load_preferences()`, `save_preferences()`, `save_last_settings()`, `load_last_settings()`, `clear_last_settings()`, `is_reserved_name()`, `save_profile()`, `load_profile()`, `delete_profile()`, `profile_exists()`, `list_profiles()`, `HistoryEntry`, `append_history_entry()`, `recent_entries()`, `clear_history()`) now lives in `services/storage.py`, organized into four clearly-labeled sections behind one shared `application_dir()` helper.
- **Every other module that reads or writes any of this state now imports exclusively from `services.storage`.** No other file in the codebase performs direct file I/O against any of the four state files. Updated importers:
  - `core/builder.py` — imports `HistoryEntry`, `append_history_entry`
  - `cli/cli.py` — imports the module as `storage` and calls `storage.load_last_settings()`, `storage.save_profile()`, `storage.list_profiles()`, `storage.delete_profile()`, etc.
  - `gui/builders.py` — imports `AppPreferences`, `load_preferences`, `save_preferences`, `load_last_settings`, `save_last_settings`
  - `gui/profiles_section.py` — imports the module as `storage` and calls `storage.save_profile()`, `storage.load_profile()`, `storage.delete_profile()`, `storage.list_profiles()`, `storage.is_reserved_name()`
  - `gui/about_tab.py` — imports `HistoryEntry`, `application_dir`, `clear_history`, `recent_entries`
- **`services/updater.py` now also imports `application_dir()` from `services.storage`** instead of maintaining its own separate copy of the same resolution logic. Updater-specific concerns (checking for releases, staging downloads, backing up and swapping application files) remain in `updater.py`, since those are a genuinely different responsibility (updating the application itself, not persisting user settings) — but the one piece of logic the two modules had been duplicating (where does this app's data live) is now shared from a single source.
- **Root motivation:** four modules each independently re-implementing the same `application_dir()` frozen-vs-source resolution helper is exactly the kind of duplication that lets small inconsistencies creep in silently — a fix or behavior change applied to one copy has no guarantee of reaching the other three. Consolidating into one file removes that entire class of risk going forward, and makes "where does saving happen" a single, findable answer instead of a four-way guessing game.

### Notes
- **This is a pure internal refactor with zero behavior change.** Every file format, every JSON key, every CLI flag, every GUI control, and every function's signature and return value are identical to before. `custom_profiles.json`, `last_export_settings.json`, `app_settings.json`, and `build_history.json` are read and written in the exact same shape as previously; a file saved by the pre-refactor version loads correctly under this version and vice versa.
- The whitespace-stripping fix for Custom Profile names (`v3.0.0`) carried over unchanged into the consolidated `save_profile()` / `load_profile()` / `delete_profile()` / `profile_exists()` in `storage.py` — re-verified as part of this refactor, not silently dropped.
- Verified end-to-end after the consolidation: a full CLI build with `--git-state` completed correctly (confirming `core/builder.py`'s new import path for `HistoryEntry`/`append_history_entry` works); the complete Custom Profiles lifecycle (save → list → load-with-trailing-whitespace → delete → confirm gone) was re-run against the consolidated module with identical results to before; and a full two-launch GUI cycle confirmed both the always-on Last Used Settings memory and the App Preferences autosave (`open_after_build`, etc.) persist correctly across a simulated restart, all now flowing through the single `services/storage.py` module.
- Searched the entire codebase after the refactor for any remaining reference to the four removed module names (`app_settings`, `settings_memory`, `profile_manager`, a standalone `services.history` import) — none found outside of comments/docstrings explaining the change and the filename constants themselves (which still live in `core/constants.py`, unchanged).

---

## [3.0.0] - 2026-08-22

This release consolidated a full architecture overhaul plus every
feature and fix built on top of it in the same development cycle: a
complete project restructure, opt-in Git State detection, an
Extras/Custom Profiles system, a GUI tab split with scroll support,
always-on settings memory, and two bug fixes. It replaced the prior
flat-file-layout version (v2.3.5) in one step.

### Added — Project Restructure (Architecture Foundation)
- Reorganized the entire codebase from a flat file layout into purpose-built subfolders (`core/`, `services/`, `cli/`, `gui/`, `docs/`), with a single entry point (`run.py`).
- Every internal import updated to fully package-qualified paths.
- Removed the old root-level `__init__.py`.

### Fixed — Project Restructure
- Fixed an `application_dir()` regression introduced by the move itself, so app-data files continued landing next to `run.py` rather than nested inside `services/`.

### Added — Git State Detection (Extras, opt-in)
- New `core/git_state.py` module: reads a project's `.git` directory directly (HEAD, refs, loose commit/tree objects), pure Python, no external `git` binary invoked.
- New "Git State" section in `PROJECT_CONTEXT.md`, `PROJECT_MANIFEST.json`, and `PROJECT_SUMMARY.txt`.
- Recent Exports history records branch + short commit. Build Complete dialog and CLI output show a one-line git summary.
- CLI `--git-state` / `--no-git-state` / `--git-state-commit-limit` flags.
- Off by default in both `standard` and `archive` profiles, including archive/maximum-preservation mode — lives in the Extras (Optional) category, never enabled by a profile preset.

### Added — Extras (Optional) Category
- New "Extras (Optional)" section (later split onto its own tab): a dedicated category for niche add-ons never enabled by a profile preset.

### Added — Custom Profiles
- Named, user-managed settings snapshots with explicit Save / Load / Delete actions, distinct from both built-in presets and the automatic Last Used Settings.
- CLI: `--save-profile NAME`, `--load-profile NAME`, `--delete-profile NAME`, `--list-profiles`.
- `ScanSettings.from_jsonable()` classmethod added, the counterpart to the existing `to_jsonable()`.
- `apply_settings_to_state()` fixed to also set the Output Folder field (a pre-existing gap).
- New `apply_custom_profile_to_state()` helper, ensuring loaded profile values correctly win over base-profile defaults.

### Changed — GUI Restructure (3 tabs → 4 tabs; Options split into Options + Extras)
- Options tab no longer requires maximizing the window to see everything — split into "Options" and "Extras" tabs.
- Both tabs made scrollable via new `gui/scroll_frame.py`.

### Changed — Settings Are Always Remembered (GUI)
- "Remember Last Used Settings" made always-on, unconditional GUI behavior — no toggle, no way to disable.
- The profile dropdown became the explicit "reset to defaults" path.
- Scoped to the GUI only, by design: the CLI's `--remember-settings` / `--use-last-settings` flags remain separate and explicit opt-in.

### Fixed — Bug Fixes
- Update messages displayed the full internal release tag instead of a clean version number — fixed with `strip_release_tag_prefix()`.
- Custom Profile names with leading/trailing whitespace could silently fail to be found via the CLI's `--load-profile` flag — fixed by stripping names before lookup in all relevant functions.

### Notes
- This release established the folder architecture as the permanent foundation the project builds on going forward.

---

## [2.3.5] - 2026-08-17

### Fixed
- **A source file could be silently skipped if it matched a compound extension by name only, not by suffix.** `is_configured_source_file()` in `scanner.py` matched files against `settings.include_extensions` using `Path.suffix` (the file's last dot-segment) plus an exact `name_lower` match. This works for ordinary single-dot extensions, but `Path.suffix` only ever returns the *last* dot-segment of a filename — so for a genuinely compound profile extension like `.env.example` (present in the archive profile by default), only a file literally named `.env.example` (nothing before the leading dot) was ever matched. A file named `config.env.example` or `backend/api.env.example` — an extremely common real-world naming pattern for example-env files — resolved to a suffix of `.example` (not in the list) and a `name_lower` of `config.env.example` (also not in the list), and was silently dropped from every export.
- **This went undetected by the archive-mode source completeness check**, for the same reason as the v2.3.3 fix: the resulting skip reason, `extension_not_included`, is an intentional-exclusion reason and was never part of `SOURCE_COMPLETENESS_FAILURE_REASONS`, so a build hitting this exact naming pattern still reported `Status: PASS` in `PROJECT_MANIFEST.json` while quietly missing a real, eligible source file.

### Changed
- **`is_configured_source_file()` now also matches by filename ending, for compound extensions only.** After the existing suffix and exact-name checks, it additionally matches when a filename ends with any configured extension that itself contains more than one dot (currently just `.env.example`). Ordinary single-dot extensions (`.py`, `.md`, `.sample`, `.template`, `.lock`, etc.) are untouched and continue to be matched exactly as before — this only changes behavior for genuinely compound extension entries.

### Notes
- Scope is narrow by design: only extension entries containing more than one dot are eligible for the new ending-match check, so there is no risk of a single-dot extension like `.m` or `.r` unexpectedly matching an unrelated file.
- No manifest, settings, or export format changes. No migration step required.
- Verified with a fixture project containing `.env.example` at the root and `backend/config.env.example` nested one level down, using the real `collect_included_files()` scan path: before the fix, only the root `.env.example` was included and `backend/config.env.example` was skipped as `extension_not_included` with the archive build still reporting `PASS`; after the fix, both files are included and correctly hashed/line-counted like any other source file.

---

## [2.3.4] - 2026-08-11

### Fixed
- **The updater could fall back to downloading the entire BrisartDevTools monorepo instead of just this tool.** `resolve_asset()` in `updater.py` previously fell back to `payload.get("zipball_url")` whenever no matching `.exe` or `.zip` release asset was found on a release. GitHub's `zipball_url` (and `tarball_url`) always packages the full repository source at that commit — every tool in the monorepo, not just Project Context Helper — so a release published without the expected asset attached would cause the updater to silently download, and (if auto-install was enabled) extract the whole repository over the application's own files.

### Changed
- **`resolve_asset()` no longer falls back to a repository-wide source archive.** It now only returns a `.exe` asset (when running as a frozen executable) or a `.zip` asset (when running from source). If neither is attached to the matched release, it returns a new `asset_kind` of `"none"` with an empty download URL, so nothing is ever downloaded.
- **`check_for_updates()` reports `asset_kind == "none"` explicitly.** `update_available` can still be `True` in this case (so the UI can tell the user a newer release exists), but `download_url` is empty and the message states plainly that no compatible asset was found for the current run mode.
- **CLI and GUI update flows both stop cleanly on `asset_kind == "none"`.** `run_update_check()` in `cli.py` prints the release page and returns without downloading. `perform_auto_update()` in `gui/about_tab.py` shows an info dialog and returns without downloading.

### Notes
- A correctly packaged release (with a `.zip` or `.exe` asset attached, per the project's normal release process) is unaffected by this change and updates exactly as before.
- No manifest, settings, or export format changes. No migration step required.
- Verified with a simulated release payload containing no `.exe` or `.zip` assets: before the fix, `resolve_asset()` returned the repository `zipball_url`; after the fix, it returns `("", "none", "")` and both the CLI and GUI update paths stop without downloading anything.

---

## [2.3.3] - 2026-08-11

### Fixed
- **A source file could be silently and incorrectly skipped if its filename matched an excluded directory name.** `exclusion_reason()` in `scanner.py` checked every component of a file's relative path against `exclude_dirs`, including the file's own filename. A file literally named `build`, `dist`, `env`, `venv`, or `updates` (all default excluded directory names, per `DEFAULT_EXCLUDE_DIRS` in `constants.py`) anywhere in the project — most commonly an extensionless build/config script at the project root — was reported as `excluded_directory:<name>` and dropped from the export, even though it was a file, not a directory.
- **This went undetected by the archive-mode source completeness check.** `excluded_directory:*` is an intentional-exclusion reason and was never part of `SOURCE_COMPLETENESS_FAILURE_REASONS`, so a build hitting this bug still reported `Status: PASS` in `PROJECT_MANIFEST.json` and claimed every eligible source file was captured, while actually missing a real file with no warning anywhere in the output.

### Changed
- `exclusion_reason()` now only checks directory-name exclusions against a path's actual directory components. When the candidate path is a file, its own final path segment (the filename) is excluded from that check; when it is a directory, the full path is checked as before. File-name and suffix exclusion checks (`exclude_files`, `exclude_suffixes`) are unaffected.

### Notes
- Genuine excluded directories (e.g. an actual `build/` or `dist/` folder and everything inside it) continue to be excluded exactly as before — this fix only stops same-named *files* from being misclassified as directories.
- No manifest, settings, or export format changes. No migration step required.
- Verified by adding a zero-byte file named `build` (no extension) at a project root that also contains a genuine `dist/` directory: before the fix, the file was skipped with `excluded_directory:build` and the archive-mode build still reported `PASS`; after the fix, the file is scanned normally against the configured extension list, while the real `dist/` directory is still fully excluded.

---

## [2.3.2] - 2026-08-11

### Fixed
- **App-level preference toggles did not persist across restarts.** "Automatically check for and download updates on startup," "Automatically install downloaded updates," and "Open export folder after build" all reset to unchecked every time the application was reopened, including the compiled `.exe`, regardless of what the user had previously selected. Root cause: `make_gui_state()` hardcoded all three toggles to `False` on every call — there was no save or load step for them at all.

### Added
- **`app_settings.py`.** New module that persists the three app-level preference toggles to `app_settings.json`, written next to the application itself (using the same frozen-aware `application_dir()` pattern as `updater.py` and `history.py`, so it resolves correctly whether running from source or as a compiled `.exe`).
- **Write-through autosave for preference toggles.** `gui/builders.py` gained `wire_preference_autosave()`, which attaches a `trace_add("write", ...)` callback to each of the three toggles so a change is written to disk immediately when the checkbox is clicked — no explicit "save" action or clean shutdown required.
- **`APP_SETTINGS_FILENAME` constant.** Added to `constants.py` and included in `DEFAULT_EXCLUDE_FILES`, so `app_settings.json` is never accidentally swept into a project export.

### Notes
- Per-export scan settings (profile, extensions, size limits, etc.) are unrelated to this fix and continue to reset to the selected profile's defaults on every launch, as before. Only the three app-level preference toggles are persisted.
- Verified with a full save/reload roundtrip test: fresh install defaults to unchecked, toggling a checkbox writes to `app_settings.json` immediately, and a simulated restart correctly restores the prior checkbox states — including confirming `app_settings.py` resolves to the identical folder as `updater.py`/`history.py` when running as a compiled exe.

---

## [2.2.1] - 2026-08-11

### Fixed
- **Update check could select another tool's release in the BrisartDevTools monorepo.** `check_for_updates()` previously queried GitHub's `/releases/latest` endpoint, which returns the newest release for the entire `BrisartDevTools` repository rather than the newest Project Context Helper release specifically. Since the repo also contains independently versioned tools (CanonSync, AutoExeBuilder, ReadmeBuilder, ReleaseNoteBuilder), publishing a release for any other tool after the latest Project Context Helper release would cause the updater to detect, download, and apply that other tool's release instead.
- **Update checks now filter the full releases list by tag prefix.** `constants.py` replaces `UPDATE_CHECK_URL` with `RELEASES_LIST_URL` (the full `/releases` list) and a new `RELEASE_TAG_PREFIX = "project-context-helper-v"`. `updater.py` gained `find_latest_release_payload()`, which walks the list and returns the first release whose tag actually starts with that prefix, ignoring newer releases belonging to other tools in the repo.
### Notes
- If no release matching the tag prefix is found (e.g. the prefix convention changes, or no Project Context Helper release exists yet), `check_for_updates()` now reports this explicitly instead of silently falling back to an unrelated release.
- Verified with a simulated monorepo releases list (`canonsync-v1.2.0` listed as newest, `project-context-helper-v2.2.0` and `-v2.1.5` behind it): confirmed the old `/releases/latest`-style logic would have selected the CanonSync release, and confirmed the fixed filtering logic correctly selects the matching Project Context Helper release instead.

---

## [2.2.0] - 2026-08-11

### Added
- **Real in-place auto-updater.** `updater.py` gained `find_release_root()`, `backup_application()`, `apply_extracted_update()`, `apply_staged_update()`, and `install_update()`. Together these extract a downloaded release and overwrite the running application's own files, rather than only staging the download as before.
- **Every in-place update is backed up first.** `backup_application()` copies the current application files into `updates/backups/v<version>_<timestamp>/` before `apply_extracted_update()` overwrites anything, so a bad update can be reversed manually.
- **CLI `--install-updates` flag.** Downloads, backs up, and applies an available update from the command line in one step (implies `--check-updates`).

### Changed
- **Auto-install is a separate, opt-in toggle.** Added `GuiState.auto_install_var`, defaulting to off. The existing "check for updates on startup" toggle still only downloads and stages by default; auto-install must be enabled separately before a staged update is applied over the running files.
- **Updater never touches its own staging or export folders.** Introduced a shared `PROTECTED_NAMES` set (`updates/`, `PROJECT_CONTEXT_EXPORTS/`, `__pycache__`, `.git`, `download.zip`) that both the backup step and the apply step exclude.

### Notes
- In-place updates are overwrite-only: files present in the application directory but absent from the release are left untouched, never deleted.
- Verified functionally before shipping: GitHub zipball wrapper unwrapping, flat packaged-release layout, backup content correctness, and `PROTECTED_NAMES` exclusion were each tested directly.

---

## [2.1.5] - 2026-07-26

### Added
- **Automatic update check and download on startup.** `updater.py` gained `resolve_download_url()` and `download_update()`; the About tab runs the check ~500ms after launch when the startup toggle is enabled.

### Changed
- **Combined the About and Updates tabs into one.** Removed `gui/updates_tab.py` and moved its controls into `gui/about_tab.py`; `main_gui.py` no longer creates a separate Updates tab.
- **Updates are staged, not silently applied.** `download_update()` extracts the release into `updates/v<version>/` (an excluded directory) and prompts for a restart instead of overwriting the running process.
- **Reduced updates settings to a single startup toggle.** Removed the manual "Check for Updates" and "Open Releases Page" buttons; only "check on startup" remains.

---

## [2.1.4] - 2026-07-26

### Changed
- **Made 'archive' the default profile.** Added `DEFAULT_PROFILE = PROFILE_ARCHIVE` in `constants.py`; the GUI Quick Export and the CLI `--profile` default now resolve to archive.
- **Folded expanded-only extensions into archive.** The extra extensions (.rst, .log, .env.example, .sample, .template, .lock) were merged into `ARCHIVE_EXTENSIONS` so no coverage was lost.

### Removed
- **Removed the 'expanded' profile.** Dropped `PROFILE_EXPANDED`, `apply_expanded_preset()`, and the `EXPANDED_*` constants; `VALID_PROFILES` is now `{standard, archive}`.

---

## [2.1.3] - 2026-07-26

### Changed
- **Centralized profile settings.** The GUI now reads per-profile values from `settings_for_profile()` instead of duplicating them, removing drift between `constants.py` and `gui/builders.py`.
- **Cleaned up the File Index table.** `build_context_markdown()` now builds columns dynamically so 'Lines' and 'SHA256' only appear when their settings are enabled.
- **Hardened scan records and metadata.** Made `FileRecord`, `SkipRecord`, `ScanResult`, and `BuildResult` frozen; added a cached `FileMeta` and skip-reason constants in `scanner.py`.

