# Changelog

All notable changes to Entitle are documented in this file.

Entitle is pure Python with no external packages, takes its encryption from
97_Encryption in the same archive, and is designed for local-first, offline,
and air-gapped environments.

---

## [0.6.1] - 2026-11-11

A usability release. `python run.py` with no arguments now opens the desktop window. In 0.6.0 it printed the usage text and exited with status 0, so the window could only be reached by typing `python run.py gui`, a command nothing on screen mentions. `run.py` is now the one front door to both interfaces: no arguments opens the window, and a command runs that command. The window also sizes itself to its content. No entitlement, record or command behavior changed, and no file format changed.

The 77 tests in `tests/test_cli.py`, `tests/test_gui.py` and `tests/test_common.py` pass on Python 3.12 (Linux), including the whole command-line lifecycle and the window's workflow. They ran against the test copy of `97_Encryption/Official` described under 0.6.0, not the real library. The suite is now 292 tests (282 in 0.6.0, ten added); the other 215 test files this release does not touch and were not re-run. Five deliberate breakages were applied to the finished code and reverted, and each was caught by the test written for it: no command printing the usage and exiting 0 again, the usage no longer shown when the window cannot open, the reason swallowed, the window measured before its tabs exist, and the size no longer capped to the screen. The window itself was not opened on a real display; the limits of this verification are listed under Compatibility.

### Changed
- **`python run.py` with no arguments opens the window** (`cli.py`). `main()` now handles "no command" by calling `_open_window()`, the function the `gui` command already used: it imports `gui.window` only then (so every other command still never loads tkinter), reports a missing tkinter as one clear error, and calls `launch()`. The `gui` command and the no-command route are the same code. When the window cannot open (no tkinter, or the `tk.TclError` that `launch()` turns into an `EntitleError`, such as no display), `_open_window_or_show_usage()` prints the usage on stdout, then the error on stderr, and the exit status is 1. Before, no command printed the usage and exited 0, which hid the window from anyone who did not already know the `gui` command. `--help` is unchanged: it prints the usage, exits 0, and never tries to open a window.
- **`run.py` header** now describes both uses (no arguments opens the window; a command runs it), including that double-clicking `run.py` on Windows runs it with no arguments when `.py` files are associated with Python, and that from a double-click the console closes at once if the window cannot open, so the message is only readable from a terminal. No code in `run.py` changed.
- **The window measures itself once every tab exists** (`gui/window.py`). It used to be a fixed 880x640. The notebook is as tall as its tallest tab (the Issue tab has sixteen rows of fields and then its button row, and a row's height depends on the platform's fonts and display scaling), and when the contents need more than the window gives, Tk's packer squeezes the widget packed last, which is the output pane. The window now calls `update_idletasks()` after the last tab is added, reads `winfo_reqwidth()` and `winfo_reqheight()`, and opens at the larger of 880x640 and that size, never more than the screen minus 60 px across and 120 px down (room for the title bar and the taskbar). The minimum stays 760x560, or the starting size on a screen smaller than that. This is a precaution: how the Issue tab looked at 880x640, and whether anything was ever cut off, were not observed on a real display.
- **The output pane is 8 lines high instead of 10** (`gui/window.py`), giving the form the room.
- **README**: Open the window now starts with `python run.py`, says what to do if it does not open (run it from a terminal to read the usage and the reason; the usual causes are no tkinter or no display), and the Tools intro and the Project Layout comment for `run.py` describe the two uses.
- **Source headers** of `cli.py`, `run.py`, `gui/window.py`, `tests/fake_tk.py`, `tests/test_cli.py` and `tests/test_gui.py` state the new behavior and were checked again against the real imports (the six sections in order, no line over 100 columns, every import and importer named).
- `__version__` is now `0.6.1`.

### Added
- **Tests of opening the window** (`tests/test_gui.py`, `TestOpeningTheWindow`, four tests): `cli.main([])` and `cli.main(["gui"])` each build the six-tab window and return 0; `run.py` run as a script with no arguments (through `runpy`) ends with exit status 0 and a window; and with a Tk that cannot open a display, no command shows the usage on stdout, then `Error: Could not open a window: ...` on stderr, and returns 1.
- **Tests of the window's size** (`tests/test_gui.py`, `TestWindowSize`, four tests): content that fits opens at 880x640 with a 760x560 minimum; a taller or wider tab makes the window that size; the window is measured only after all six tabs exist; and a 1366x768 screen caps the height to 648 and an 800x600 screen caps it to 740x480 with the minimum following.
- **Tests of no-command behavior** (`tests/test_cli.py`, three tests, one of which replaces `test_no_arguments_prints_help_with_every_command`): no command with no tkinter shows the usage with every command, then the reason, and exits 1, in this process and in a real process; and `--help` prints the usage and exits 0 even with tkinter unavailable.
- **`tests/fake_tk.py`** records `geometry()` and `minsize()`, records how many tabs existed when `update_idletasks()` was called, and reports `Tk.request_size` and `Tk.screen_size` from `winfo_reqwidth/reqheight` and `winfo_screenwidth/screenheight`, so the sizing arithmetic can be tested without a display.

### Notes
- **`cli.py` stays beside `run.py`.** A `cli/` folder to mirror `gui/` was considered and not done: it would hold one file, the one-file package that was removed in the 0.4 and 0.5 reorganizations, and `gui/` is a folder because it is two modules. If the command line grows past one file, split it then.

### Compatibility
- **Unchanged:** every command and flag, exit statuses (including `verify` exiting 1 when denied and `track deploy` and `report` exiting 0 in the cases listed under 0.6.0), the entitlement and record formats, the encryption link, `python run.py gui`, and `python run.py --help`.
- **Behavior that changed:** running `python run.py` with no arguments. It opens the window where it used to print the usage and exit 0. A script that ran it bare to get the usage should run `python run.py --help`. On a machine where the window cannot open it still prints the usage, but now also writes the reason on stderr and exits 1.
- **Not verified here:**
  - A real display. The tests use the tkinter stand-in, which checks the sizing arithmetic and the wiring but not appearance. The 880x640 starting size, the 8-line pane and whether the Issue tab fits were not seen.
  - Double-clicking `run.py` on Windows. It is described from how Windows starts `.py` files; it was not tried.
  - The real `97_Encryption/Official`, Windows and macOS, as under 0.6.0.
- No new external dependencies.

---

## [0.6.0] - 2026-11-11

An architecture release that also fixes eight defects, found by reading, running and fuzzing the code, and documents one behavior that surprised. Every `__init__.py` is gone: `entitle/__init__.py`, which 0.5.0 had brought back to hold the helpers every module shares, is replaced by `entitle/common.py`, so `entitle/` and `gui/` are implicit namespace packages again, as in 0.4.1 and as in the rest of the Brisart tooling. The entry point is renamed from `main.py` to `run.py`, the name every Brisart tool uses. The entitlement format, the encryption context, the record log format and hash chain, and every command and flag are unchanged; `python main.py ...` becomes `python run.py ...`, and Python code that imported `EntitleError`, `canonical_json`, `utc_now`, `utc_now_iso` or `require_text` from `entitle` imports them from `entitle.common`.

The suite has 282 tests (215 in 0.5.0) and passes on Python 3.12 on Linux. That run used a test copy of `97_Encryption/Official`, not the real library: the previous-format modules (`primitives`, `entropy`, `drbg`, `envelope`) were rewritten from the BSR2 Alpha 3 source in an earlier export and authenticate the real `tests/fixtures/legacy_alpha3_entitlement.json` (a wrong key, a wrong context and a tampered tag are refused), while the sealed-v3 format (`aead`), `sponge` and `version` were stand-ins that only check Entitle's wiring. Nothing here says anything about BSR2-S64-SIV itself, so run `python -m pytest tests` against the real archive; `tests/test_end_to_end.py` is the one that drives the whole workflow through real `run.py` processes with the encryption that sits beside Entitle. Each fix below was reproduced by putting the 0.5.0 behavior back into the new code and watching its test fail (the 0.5.0 files themselves were not on disk in the environment that built this release). Two fuzz runs were made: 300 seeds across 13 kinds of record-log damage, which found the invalid-UTF-8 defect below that reading had missed, and 425 damaged entitlement files (400 current format, 25 previous format), which found nothing but clean denials and errors. The limits of this verification are listed under Compatibility.

### Fixed
- **A damaged record log could not be audited at all** (`entitle/records.py`). The log was read as strict UTF-8, so any damage that left invalid UTF-8 made `verify_chain()`, the report and `python run.py report` raise `UnicodeDecodeError` instead of reporting `BROKEN`. A power failure in the middle of a record containing a multi-byte character (a host such as `узел-1` or `实验室`) leaves exactly that, as does a stray byte from an editor. Found by fuzzing: before the fix, 6 of the 13 damage kinds raised (three of them on every seed, the others on some). Bytes that are not UTF-8 are now read as replacement characters, so only that line is reported as damaged (`unparseable_record` at its index) and the rest of the log is still counted. `append()` still refuses to extend a damaged log.
- **A record could be written and the command reported as failed** (`cli.py`). The command wrote the record and then printed it; on an output that cannot encode the text (a redirected Windows console on a legacy code page, any ASCII-only stream) the print raised `UnicodeEncodeError`, the command printed `Error: 'ascii' codec can't encode characters...` and exited 1, and an operator who retried got a duplicate in a log whose records can never be removed. Reproduced with `PYTHONIOENCODING=ascii python run.py track fork --fork-name 实验室 --maintainer узел`: before, exit 1 with the record already written; after, exit 0. `main()` now sets `errors="backslashreplace"` on stdout and stderr, so unencodable characters print as escapes (`\u5b9e\u9a8c\u5ba4`) and the stored record is untouched. The same applies to error messages that quote a path.
- **Verifying a large previous-format file could take minutes** (`entitle/entitlements.py`). Only the current format had a payload cap; a previous-format file (BSR2 Alpha 3) was decrypted whatever its size, and its MAC runs over every byte before it can fail. With the cap removed, verifying a file with a 450 KB ciphertext had not finished after 50 seconds. A previous-format file whose ciphertext is over twice `MAX_PAYLOAD_BYTES` hex characters is now refused before any decryption (denied as `bsr_verification_failed`), and `read_entitlement_file` refuses any file over `MAX_FILE_BYTES` (1 MiB) by name. Real entitlements are about 1.4 KB (previous format) and 1.3 KB (current), so neither limit is anywhere near them.
- **Files that passed through Windows tools were rejected or misread** (`entitle/entitlements.py`, `entitle/records.py`). A UTF-8 byte-order mark (added by older versions of Notepad and some other editors) made an `.entitle` file "not a protected Entitle entitlement file" and made the first record of a log unparseable. A file written by Windows PowerShell's `>` or `Out-File` is UTF-16 and failed with a codec error. Both files now read with `utf-8-sig`, Windows line endings are accepted for both formats, and a UTF-16 file is named as such with the fix (`Copy-Item`, or save as UTF-8). Files are still written as plain UTF-8 without a byte-order mark.
- **The example application crashed on an unusable entitlement file** (`examples/protected_app_example.py`). It promises that anything short of a verified entitlement leaves every governed feature locked, but only `EntitleError` was caught, so a file that was garbage, empty, UTF-16, oversized or unreadable ended in a traceback before the base program started. It now catches `ValueError` and `OSError` as well: the reason is printed, the base program runs, and nothing governed unlocks.
- **A shallow install crashed at import instead of saying "Encryption not found"** (`entitle/encryption.py`). `ARCHIVE_ROOT` was `Path(__file__).resolve().parents[3]`, which raises `IndexError` when there is no folder three levels above the file, as for an Entitle folder directly under a drive root (`C:\Entitle` has three parents), so every command ended in a traceback although the design is a one-line message. `_archive_root()` now returns the top of the drive in that case, and the existing "was not found" message follows. Reproduced with `parents[3]` put back (`IndexError: 3` on `C:\Entitle`, `/Entitle` and the like). An install at a drive root could not be created in the test environment, so this is covered through the root calculation, not an actual install.
- **Windows paths leaked into "Encryption not found" messages** (`entitle/encryption.py`). 0.5.0 removed this machine's archive path from the reason by replacing `str(ARCHIVE_ROOT)`, but a path quoted inside an exception's `repr()` (a `SyntaxError` in a BSR2 module, for example) has every backslash doubled, so on Windows the user name and folders stayed in the text. `_without_location()` now removes the plain, forward-slash and doubled-backslash spellings. Covered with a Windows root, because the Linux test environment has no backslashes to scrub.
- **An entitlement could be issued that could never verify** (`entitle/entitlements.py`). Opening a payload is capped at 64 KiB, but issuing was not: a pasted 70,000-character entitlement ID or support tier was sealed, written and reported as created, then denied as `bsr_verification_failed` on every verification. `issue_entitlement()` now refuses a payload over `MAX_PAYLOAD_BYTES` before sealing, with the size and the fix in the message. This is the same class as the unparseable `--expires` and negative limit that 0.5.0 closed.
- **`--expires` with a date alone expired the entitlement a day early, and nothing said so** (`entitle/rights.py`, `cli.py`, `docs/README.md`). `2026-12-31` is parsed as 00:00 UTC, so the entitlement stops working when that day begins. The behavior is unchanged (changing it would alter when files already issued expire) but it is now stated in the `--expires` help, the README and the headers, and pinned by tests: yesterday's and today's date are expired, tomorrow's is not, and a time on the last day (`T23:59:59Z`) includes the whole day.

### Changed
- **`entitle/common.py` replaces `entitle/__init__.py`.** The five shared names (`EntitleError`, `canonical_json`, `utc_now`, `utc_now_iso`, `require_text`) moved unchanged. 0.5.0 had added `entitle/__init__.py` for them, undoing the 0.4.1 decision to remove every `__init__.py`; they now live in a leaf module whose name says what it holds, and importing `entitle.<module>` runs that module and what it imports and nothing else. Inside `entitle/`, `from . import X` became `from .common import X` (`rights.py`, `encryption.py`, `entitlements.py`, `records.py`, `revoke.py`, `tracking.py`); in `cli.py`, `gui/window.py` and `examples/protected_app_example.py`, `from entitle import EntitleError` became `from entitle.common import EntitleError`. The dependency graph inside `entitle/` is unchanged and has no cycles: `common` is at the bottom, `entitlements` builds on `rights` and `encryption`, `tracking`, `revoke` and `report` build on `records`, and only `tracking` joins the two.
- **`run.py` replaces `main.py`.** Same contents and behavior: the entry point that calls `cli.main()`. The parser's program name is now `run.py` (so `usage:` lines and `--help` say `run.py`), the migration note says `python run.py migrate`, and the example application's "issue one first" help prints `python run.py issue`. Every command in the README, the examples and the source headers was updated, and `tests/support.py`'s `run_main()` became `run_entitle(*args, cwd=None, env=None, root=None)`, which also takes extra environment variables and an alternative Entitle folder.
- **`tests/test_rights.py` was split along the module boundary.** It also tested the shared helpers, which were not in `rights.py`. Those tests (canonical JSON, `require_text`, the clock) are now `tests/test_common.py`, so `test_<name>.py` covers `<name>.py` again, and `test_rights.py` covers only the rights rules.
- **`--version`, errors and `report` are unchanged in content**; only the program name in `usage:` lines changed. `entitle/records.py` reads the log with `encoding="utf-8-sig", errors="replace"`, `entitle/entitlements.py` reads an entitlement file as bytes (size check, UTF-16 check, `utf-8-sig`, line endings normalised) instead of `Path.read_text`, and `cli.main()` calls `_make_output_safe()` first.
- **Source headers.** All Python files were checked again: the six-section order, every Communication section against the real imports in both directions, and the runnable example in each `entitle/` header. Headers for `entitle/revoke.py` (IDs are matched exactly as typed), `entitle/rights.py` and `entitle/entitlements.py` (date-only expiry, the new limits, Windows files), `entitle/records.py` (byte-order mark, invalid UTF-8) and `entitle/encryption.py` (drive-root installs, escaped paths) state the new behavior.
- `__version__` is now `0.6.0`.

### Removed
- `entitle/__init__.py` and `main.py` (see above). There are no `__init__.py` files anywhere in the project; `tests/test_common.py` fails if one is added.

### Added
- **`tests/test_end_to_end.py`: the check to run with your encryption.** It installs a copy of Entitle and of the linked `97_Encryption/Official` into a fresh archive layout and runs the whole workflow through real `run.py` processes: version and encryption link, issue, verify with the right and a wrong key, a previous-format file flagged, migrated and left unchanged, deployments up to and past the limit, a deployment from the migrated file, fork, provenance, revoke, a refused deployment, reinstate, the JSON audit report, a tampered record reported as broken, and the example application. A second test starts six `run.py` processes at once against a limit of 2 and expects exactly two recorded, four refused and an intact chain.
- **`tests/test_common.py`**: pins the exact bytes of canonical JSON (hashes and sealed files depend on them); checks that every module imports in a fresh interpreter from another folder with `entitle.__file__` equal to `None` and a single path entry (a second `entitle` folder on the path would merge into it); and that no source file raises a warning when compiled (a Windows path with a bare backslash in a docstring is a `SyntaxWarning` today, which this release's own headers tripped once).
- **Tests for each fix**, 215 to 282 in all. `tests/test_records.py`: 14 kinds of damage under 10 fixed seeds, all of which must be reported or harmless and never raise, plus a byte-order mark and Windows line endings. `tests/test_report.py`: a character cut in half still gets a report, and readable plus unreadable always equals the lines in the file. `tests/test_entitlements.py`: byte-order mark, CRLF, UTF-16 (three variants), invalid UTF-8, an oversized previous-format ciphertext refused in under 5 seconds, a file over the read limit, a payload too large to verify. `tests/test_encryption.py`: the archive root of Posix and Windows paths of every depth, and scrubbing of Windows, forward-slash and Posix spellings. `tests/test_cli.py`: Chinese and Cyrillic names under `PYTHONIOENCODING=ascii` (exit 0, one record, escapes in the output, the stored record exact), the same for report and error messages, the `--expires` help text, and that `run.py` exists, `main.py` does not and `--help` says `run.py`. `tests/test_example.py`: four kinds of unusable file and a folder in place of a file. `tests/test_rights.py` and `tests/test_revoke.py`: date-only expiry, and exact-as-typed IDs.
- **Mutation checks.** Twelve changes were applied to the finished code and reverted, each putting a 0.5.0 behavior or a guarded structure back, and each was caught by the test written for it: `parents[3]`, no output safety, no previous-format ciphertext cap (the test did not finish within its 50 second limit), no file size limit, plain `utf-8` for entitlement files, plain `utf-8` for the log, strict decoding of the log, the example catching only `EntitleError`, single-spelling path scrubbing, no payload check at issue, an `entitle/__init__.py` added, and a docstring with a bare backslash path added.

### Compatibility
- **Unchanged and checked:** the entitlement payload and `entitle.entitlement.v1`, the encryption context string (pinned by a test), the record format and hash chain, every command and flag, exit statuses (`verify` exits 1 when denied, `track deploy` exits 0 when a deployment is refused, `report` exits 0 when the chain is broken), the window's six tabs, and sealed and previous-format entitlement files and record logs written by earlier releases. The fixtures `tests/fixtures/legacy_alpha3_entitlement.json` and `tests/fixtures/legacy_v0_4_1_records.log` are byte-identical to the ones in 0.5.0 (their SHA-256 values were compared with the manifest of the 0.5.0 export).
- **Changed entry point:** `python main.py ...` no longer exists. Shell scripts, CI steps, shortcuts and documentation that call it must call `python run.py ...`; the arguments are the same.
- **Python API:** `from entitle import EntitleError` (and `canonical_json`, `utc_now`, `utc_now_iso`, `require_text`) must become `from entitle.common import ...`. `import entitle` still works but exposes nothing, because `entitle` is a namespace package. A program protected by Entitle imports `EntitlementDenied` from `entitle.rights` and `verify_entitlement` from `entitle.entitlements`, as before.
- **Namespace packages:** a second folder named `entitle` anywhere on `sys.path` would be merged into the package. `tests/test_common.py` checks that a normal run sees exactly one, but nothing prevents it on another machine.
- **Behavior that changed:** an entitlement over 64 KiB can no longer be issued (it could never have been verified); a file over 1 MiB is refused by name; a previous-format file with an oversized ciphertext is denied without being decrypted; a byte-order mark, Windows line endings and (for logs) invalid UTF-8 are tolerated where they used to fail; a UTF-16 file produces its own message; unencodable output is escaped instead of raising; the example application locks instead of crashing; `usage:` lines say `run.py`.
- **Not changed, still true:** `track deploy` and `report` exit 0 in the cases listed above; a revocation matches the entitlement ID exactly as typed (documented in `entitle/revoke.py` and the README); truncating the end of a log is not detectable by the hash chain; issuing to an existing path replaces the file without asking; replacing a file through a symbolic link replaces the link.
- **Not verified here:**
  - BSR2 itself. The suite ran against the test copy of `97_Encryption/Official` described above, so the sealed-v3 format (BSR2-S64-SIV) was only exercised through a stand-in that has the same interface. Run `python -m pytest tests` on the real archive before publishing; if its `97_Encryption/Official` differs from what Entitle requires (`REQUIRED_MODULES` and `REQUIRED_FORMATS` in `entitle/encryption.py`), `tests/test_encryption.py` and `tests/test_end_to_end.py` fail first.
  - Windows and macOS, and a real display. Several fixes concern Windows (drive-root installs, escaped backslashes, PowerShell's UTF-16, code pages); they are covered through pure-path functions, `PYTHONIOENCODING` and crafted bytes, not by running on Windows. The Windows branch of the record-store lock and the window's appearance are untested.
  - A real entitlement written by Entitle 0.4.1 (the previous-format fixture stands in) and a real power failure (the damaged-log tests reproduce its effect on the file).
  - The 0.5.0 files themselves were not available to diff against when this release was built; review `git diff` before committing.
- No new external dependencies; the application is standard-library Python plus the archive's `97_Encryption`.

---

## [0.5.0] - 2026-11-10

An architecture and encryption release. Every responsibility in the code now has one obvious owner, Entitle takes all of its encryption from `97_Encryption/Official` (BSR2 Alpha 4, 0.4.0-alpha) in the same archive and keeps no copy of it, new `.entitle` files use BSR2's current sealed format while files written by 0.4.1 keep working and can be re-sealed with a new `migrate` command, and a set of defects found by running the code rather than reading it are fixed. This entry is written against 0.4.1, the last published release; it replaces the interim development entries that were never published (an earlier 0.5.0 and its 0.5.1, 0.6.0, 0.7.0 and 5.0.0 successors). The entitlement payload and rights, the BSR2 context that binds a file to its issuer, subject and product, the record log format and hash chain, and every command and flag other than the ones named below are unchanged. Python import paths and function names changed, and so did the `.entitle` file format, so this is a minor version bump while the project is below 1.0.

0.4.1 was rebuilt from its own export before any change (all 41 files matched the manifest hashes) and its 82 tests were run first. The suite now has 215 tests and passes on Python 3.12 on Linux. Twenty-nine deliberate breakages were applied to the code during development and reverted: twenty-eight were caught by the test written for them, and the other (the window storing empty optional fields as empty text instead of `null`) was not, so a test now covers it. Every command in the main workflow of `docs/README.md` was run as written in a clean folder (issue, verify, deploy, migrate, deploy from the migrated file, a deployment refused after revocation, report, and the example application), and the Python example in every `entitle/` source header was run. The limits of this verification are listed under Compatibility.

### Fixed

Found by running 0.4.1 and recorded as reproduced against it:

- **Concurrent writers could fork the hash chain and exceed a deployment limit** (`entitle/records.py`, `entitle/tracking.py`). `RecordStore.append()` read the last hash and then appended with no lock, so two writers (the window and the command line, or two commands) could both chain to the same previous record. With 8 threads appending 15 records each, the chain was broken or records were lost in 12 of 12 trials; with 8 concurrent deployments against a limit of 2, more than 2 were recorded in 2 of 12 trials. Appends now run inside `RecordStore.transaction()`, and `register_deployment()` performs the revocation check, the count and the append inside one transaction. The lock is an operating-system lock (`fcntl.flock` on Linux and macOS, `msvcrt.locking` on Windows) on a `<store>.lock` file beside the store, so a writer that is killed releases it at once and there is no age rule that could let two writers in. The same two measurements on the final code: 0 of 12 and 0 of 12. The entitlement is verified before the lock is taken, so slow cryptography never holds the store. The lock waits up to 5 seconds, and a thread waiting on another thread's transaction in the same process gives up on the same timeout.
- **A damaged record crashed the audit instead of being reported** (`entitle/records.py`, `entitle/report.py`). A record line truncated mid-JSON raised `json.JSONDecodeError` from `python main.py report`, which is the one situation a tamper-evident log should report. `verify_chain()` now returns an invalid status with reason `unparseable_record` and the record index, and `build_report()` still produces a report: it counts every readable record, adds `unreadable_records` to the JSON and an `Unreadable records: N` line to the text, and marks the chain `BROKEN` at the first damaged index. On a three-record log with the last line truncated, the report shows `Total records: 2`, `fork: 2` and `Unreadable records: 1`. `read_all()` and `append()` raise a new `RecordStoreError` naming the record (`read_all(strict=False)` skips damaged lines), and `append()` refuses to extend a damaged log.
- **A mistyped store path reported a verified log** (`entitle/report.py`). `report` on a path that does not exist printed `VERIFIED: hash chain intact across 0 records.` The report now includes `store_exists` and the text says the store file does not exist. An existing empty store is unchanged.
- **BSR2 failures hid their reason, and routine mistakes printed tracebacks** (`entitle/entitlements.py`, `cli.py`). A master key shorter than 32 bytes failed with `BSR envelope encryption failed.` and nothing else, in the command line and the window alike. The message now carries BSR2's reason (for example `BSR2 encryption failed: master key must contain at least 32 bytes`). A short key, seed or personalization, a missing file and a damaged store each printed a 23 to 29 line traceback; they now print one `Error: ...` line on stderr and exit 1.

Found in the development build that followed 0.4.1 and reproduced there. 0.4.1 itself was not re-run for these, so whether it had each of them is unconfirmed:

- **Blank required fields were written into the permanent log** (`entitle/__init__.py`, `entitle/revoke.py`, `entitle/tracking.py`). `track fork --fork-name ""` exited 0 and appended a fork record with an empty name, and the window did the same for an empty entitlement ID on Revoke, an empty host on Deploy, or any empty fork or provenance field. Records can never be edited or removed, so the mistake was permanent. `require_text()` is now called by `revoke()`, `reinstate()`, `register_deployment()`, `record_fork()` and `record_provenance()` before anything is written: an empty or whitespace-only value raises `ValueError` (for example `fork name is required.`).
- **Entitlements that could never verify or deploy were issued** (`entitle/entitlements.py`). `issue --expires "next tuesday"` wrote a file that was then denied as `invalid_expiration_timestamp` on every verification, and `--deployment-limit -1` wrote one that refused every deployment. `issue_entitlement()` now checks before sealing or writing anything: the issuer, subject, product and entitlement ID must not be blank, `expires` must parse as an ISO timestamp, and the deployment limit must be a whole number of 0 or more. A limit of 0 is still accepted on purpose: it verifies, for example to unlock features in a protected application, but permits no tracked deployment.
- **An edited record whose `data` was not an object crashed commands** (`entitle/records.py`). A revocation record whose `data` had been replaced by a list made `revoke check` (and the deployment gate) end in `AttributeError: 'list' object has no attribute 'get'`. Such a record is now unreadable like a non-JSON line: `read_all()` and `append()` raise `RecordStoreError` (`record 0 has no data object.`) and `verify_chain()` reports `unparseable_record` at that index.
- **A payload that decrypted to something other than a JSON object crashed verification** (`entitle/rights.py`). An envelope that authenticated but held `[1,2]` ended `verify` in an `AttributeError` traceback. `load_entitlement_payload()` now refuses anything that is not a JSON object, so the entitlement is denied as `bsr_verification_failed`.
- **Appends could be lost on power failure** (`entitle/records.py`). Each record is now flushed and `fsync`ed before the writer lock is released.

### Changed

- **Encryption comes from `97_Encryption/Official`, and `vendor/` is gone** (`entitle/encryption.py`, which replaces `entitle/bsr_adapter.py`, `entitle/bootstrap.py` and the four vendored BSR2 Alpha 3 files). `entitle/encryption.py` finds `97_Encryption/Official` relative to itself (`98_Tooling/Entitle/entitle/` up to the archive folder, no configuration and no absolute path) and links the seven modules Entitle uses: `aead`, `envelope`, `drbg`, `version`, and the three they import, `primitives`, `sponge` and `entropy`. The link is checked before use: every module must be loaded from that folder (a `brisart_security_*` module already imported from anywhere else is refused rather than run against), and the formats Entitle needs (`BSR2-S64-SIV` format 3, and `BSR2-ARX-SPONGE-ETM` version 2 to read old files) must be present. The release is not pinned, so any BSR2 release that still provides those formats links. Resolution happens on first use, so every Entitle module still imports without `97_Encryption`.
- **New files are BSR2 sealed messages, not JSON envelopes** (`entitle/entitlements.py`). `issue` seals the payload with `BSR2-S64-SIV` (sealed format 3) and writes armored text beginning `-----BEGIN BSR2 SEALED MESSAGE-----` (1,332 bytes for a typical entitlement). This is the format 97_Encryption recommends, and it closes the weakness the archive changelog describes for the Alpha 3 envelope: a repeated nonce in a restored or cloned virtual machine can no longer make two different entitlements share a keystream. Payloads are padded to 256-byte blocks so the file size does not reveal how many rights or what text a payload held. The BSR2 context (system, format, product, issuer and subject) is byte-identical to 0.4.1's, and a test pins it, so a file still only opens for the exact issuer, subject and product it was issued to. The payload's `metadata.protection` text reads `BSR2-S64-SIV sealed message`.
- **The DRBG seed and personalization are optional** (`entitle/entitlements.py`, `cli.py`, `gui/tabs.py`). The new format draws fresh operating-system entropy for every file, so a caller-supplied generator adds nothing that is needed; `issue` no longer requires `--drbg-seed` and `--drbg-personalization`, and the Issue tab's fields say optional. Commands that still pass them work, are validated as before (64 and 16 bytes) and add the generator on top of system entropy. A too-short seed or personalization is wrapped in `EntitleBSRError`; before it escaped as the vendored `BrisartDRBGError`. The master key must be 32 to 1024 bytes; BSR2's sealed format has an upper limit that the old envelope did not state.
- **`--version` names the linked encryption** (`cli.py`). `python main.py --version` prints `Entitle 0.5.0` and a second line, `Encryption: BSR2 Alpha 4 (0.4.0-alpha), from 97_Encryption/Official`, or `Encryption not found: ...`. The link is resolved only when `--version` is asked for.
- **Entitlement files are written in one step** (`entitle/entitlements.py`, `write_entitlement_file`). The file is written beside the target and then replaces it, so a failure can no longer leave a half-written entitlement. A file that is not an Entitle file now says `<name> is not a protected Entitle entitlement file.`
- **`cli.py` holds the whole command line, and `main.py` is only the entry point.** `main.py` was a dispatcher using a `COMMAND_MODULES` table and `importlib`, and five domain modules each carried their own `argparse` parser and `main()` (`entitle/issue.py`, `entitle/verify.py`, `entitle/report.py`, `entitle/revoke.py`, `entitle/tracking/cli.py`). Interface code was mixed into the rights logic, so the logic could not be read without it. All of it now lives in `cli.py` as one parser with the same subcommands, flags, output text and exit statuses; `main()` returns an exit status and catches `EntitleError`, `ValueError` and `OSError` in one place. `track list --type` accepts only the five record types; a misspelled type used to return an empty list silently and is now a usage error (exit 2).
- **`entitle/` is organized by owner.**
  - `entitle/__init__.py` holds what every module shares: `EntitleError`, `canonical_json`, `utc_now`, `utc_now_iso` and `require_text`, so `entitle/records.py` no longer imports the entitlement rules to raise an error or hash a record.
  - `entitle/rights.py` holds the entitlement rules (payload, rights, `EntitlementResult`, `EntitlementDenied`, `evaluate_payload`, `ENTITLEMENT_FORMAT`), formerly `entitle/core.py`; `build_rights()` became `make_rights()` beside the rights it defines.
  - `entitle/entitlements.py` owns the `.entitle` file from end to end (context, sealing, opening, reading, writing) and replaces `entitle/issue.py` and `entitle/verify.py`; `verify_entitlement` takes `path` instead of `file`.
  - `entitle/encryption.py` is only the link to 97_Encryption. Only `entitlements.py` uses the linked library.
  - `entitle/records.py` absorbs `entitle/record_types.py` (`ALL_RECORD_TYPES` now backs the `--type` choices), and `utc_now_iso()`, which existed in two modules, exists once.
  - `entitle/tracking.py` replaces the five-file `entitle/tracking/` package. The domain functions now take a `RecordStore` consistently; before, `register_deployment` and `revoke` took a store object while `record_fork`, `record_provenance`, `list_records` and `deploy_from_file` took a path string. `list_records()` and `build_report_for_path()` were one-line wrappers and are removed; call `RecordStore(path).filter()` and `build_report(RecordStore(path))`.
  - `ENTITLEMENT_CONTEXT_FORMAT`, which repeated `ENTITLEMENT_FORMAT`, is gone; the context stays byte-identical.
  - One dependency direction: `entitlements.py` builds on `rights.py` and `encryption.py`; `tracking.py`, `revoke.py` and `report.py` build on `records.py`; only `tracking.py` joins the two. The record log never touches encryption, which is why `report`, `revoke` and the `track` record commands keep working without `97_Encryption`.
- **`gui/` is two files.** `gui/window.py` keeps the window, output pane, error handling and launch. `gui/tabs.py` owns everything inside the notebook: the six workflows, the shared form layout and the pre-filled defaults. These replace `gui/app.py`, `entitle/paths.py`, `gui/widgets.py` and the six `gui/tabs/*_tab.py` modules. Every tab repeated a try/except around its action and its own button layout; `FormFrame.add_buttons()` and `app.run()` now run an action, show text or JSON, and show errors in the pane and a dialog, so a tab holds only its fields and the domain call. The issuer, subject, product, master key, entitlement file and record store are one shared variable across tabs, so a file issued on the Issue tab is what Verify and Deploy read next without retyping (the Issue tab used to write `new.entitle` while Verify and Deploy read `lab_a.entitle`; they now share `lab_a.entitle`). A deployment limit that is not a whole number is reported by name. The Fork / Provenance tab gained the environment and previous-version fields the command line already had, and the Audit Report tab gained List All Records. The window title carries the version, `launch()` raises `EntitleError` when no window can open, and the second launch route `python gui/app.py` is removed (`python main.py gui` is the one way). Tab titles and order are unchanged.
- **`python main.py gui` reports a missing tkinter only when tkinter is what is missing** (`cli.py`). Any other import failure inside the window code surfaces as itself instead of being called an installation problem.
- **`examples/protected_app_example.py` fails closed.** When the check cannot run at all (for example `97_Encryption` is not found) the base program still starts, the reason is printed, and every governed feature stays locked. Its "issue one first" help no longer prints the DRBG options.
- **Exception types:** `EntitleBSRError` and `RecordStoreError` derive from `EntitleError`.
- **Source headers.** All 35 Python files outside `vendor/` carried the generic placeholder header ("Additional edge-case guarantees are not established by this header"). All 27 Python files now have file-specific six-section headers; every Communication section was checked against the real imports in both directions, and none refers to a module that no longer exists. "Repository root" is now "the Entitle folder", because Entitle sits inside the archive and the Git root is the archive folder; the tests' `REPO_ROOT` is `ENTITLE_ROOT`.
- `__version__` is now `0.5.0`.

### Added

- **`python main.py migrate`** and the **Migrate to Current Encryption** button on the Verify tab (`entitle/entitlements.py`: `migrate_entitlement`, `uses_previous_encryption`). It opens a file written before 0.5.0 with the issuer, subject, product and master key given, seals the same payload again, checks that the new file opens to the identical payload, and only then replaces the original. The entitlement ID, rights, limit, issue time and expiry are kept exactly (an expired or revoked entitlement migrates like any other). A file that does not open with the given values, or whose copy does not open to the same payload, is left untouched and reported as an error. A file already in the current format is reported `UNCHANGED`.
- **`verify` points old files at `migrate`.** After `VERIFIED`, a file that still uses the previous encryption prints a note naming `migrate`; the window adds the same note to the Verify result. A denied file gets no note.
- **`Encryption not found` is a first-class failure.** `EncryptionNotFoundError` (an `EntitleError`) is raised, never turned into `DENIED`, when 97_Encryption cannot be linked. Without it, `issue`, `verify`, `migrate` and `track deploy` exit 1 with one `Error: Encryption not found: ...` line, while `report`, `revoke` and `track fork`, `provenance` and `list` still work. This was run as real processes in a copy of Entitle with no `97_Encryption` beside it.
- **A payload size cap.** `open_entitlement` refuses a sealed payload over 64 KiB before decrypting it, so an oversized file cannot make verification run for minutes in pure Python.
- **Tests: 82 to 215.**
  - Command line: `tests/test_cli.py` runs the full lifecycle through `cli.main()` (issue, verify, deploys up to and past the limit, fork, provenance, list, revoke, refused deployment, reinstate, check, report, tamper detection), every failure above, usage errors, migration, and a real-process test that `main.py` works from another working folder and loads no tkinter.
  - Window: `tests/test_gui.py` and `tests/fake_tk.py` drive the window's real modules through a recording tkinter stand-in, pressing the real buttons with nothing retyped between tabs, including the migration flow and `null` handling of empty optional fields.
  - Encryption link: `tests/test_encryption.py` covers a missing folder, a missing module file, a copy outside the archive, a mismatched format, no copy of BSR2 inside Entitle, and every command that needs no encryption working without it.
  - Entitlement file: `tests/test_entitlements.py` covers the pinned context, sealing and opening, issue-time refusals, a failed replacement, and migration, including a copy that does not reopen to the same payload.
  - Records and rules: `tests/test_records.py`, `test_tracking.py`, `test_report.py`, `test_revoke.py` and `test_rights.py` cover the record-store lock under 8 threads and 4 processes, a lock held by another process, a writer killed while holding it, damaged and non-object records, blank required fields, the limit holding under racing deployments, and the shared helpers. `tests/test_example.py` runs the example application.
  - `tests/support.py` holds the shared helpers, including `store_lock_held_elsewhere()`, which holds a store's writer lock from a separate process and kills it on exit.
- `tests/fixtures/legacy_v0_4_1_records.log`: a six-record log written by 0.4.1. Tests assert that it still verifies, reports and can be extended.
- `tests/fixtures/legacy_alpha3_entitlement.json`: an entitlement sealed with BSR2 Alpha 3 by the copy of BSR2 Entitle carried before this release (issuer JasonBrisart, subject ResearchLabA, product EntitleDemo, entitlement `lab-a-demo-001`, modify and fork, limit 2), used to prove the previous format still opens through 97_Encryption's `envelope` module. It stands in for a file issued by a real 0.4.1 install, which the test suite does not have (the project export skips `.entitle` files).

### Removed

- `vendor/` (four BSR2 Alpha 3 files), `entitle/bsr_adapter.py`, `entitle/bootstrap.py` and `tests/test_bsr_integrity.py`. The pinned-hash test checked that a private copy of BSR2 had not drifted; with no copy, the check that matters is that the linked library is the archive's, which `tests/test_encryption.py` covers.
- `entitle/core.py`, `entitle/issue.py`, `entitle/verify.py`, `entitle/paths.py`, `entitle/record_types.py`, the `entitle/tracking/` package, `gui/app.py`, `gui/defaults.py`, `gui/widgets.py` and `gui/tabs/` (six modules), folded into the modules above.
- The requirement that `--drbg-seed` and `--drbg-personalization` be given.
- `tests/test_paths.py`: its tests checked where default paths pointed and that helpers returned strings. The version check moved to `tests/test_cli.py`.
- Stale instructions in `docs/README.md`: the Requirements, Project Layout and Tools sections still described the flat `entitle_*.py` layout and `bsr/`, so none of their commands ran. They now describe the current layout.

### Compatibility

- **Unchanged and checked:** the entitlement payload and `entitle.entitlement.v1`, the BSR2 context string (pinned by a test), the `entitle.record.v1` record format and hash chain, the revocation, deployment-limit, fork, provenance and report behavior, the denial reason `bsr_verification_failed` for a wrong key, issuer, subject, product or a modified file, the window's six tabs and every flag other than the two made optional. A record log written by 0.4.1 still verifies, reports and accepts new records.
- **Exit statuses are kept as they were:** `verify` exits 1 when denied; `track deploy` exits 0 even when the deployment is refused (see `"recorded"` in the JSON); `report` exits 0 even when the chain is broken. A script that wants failure on a refusal or a broken chain must read the output.
- **Files written by 0.4.1** (BSR2 Alpha 3 JSON envelopes) still verify, deploy and migrate. Opening them goes through 97_Encryption's `envelope` module. No removal date is set for reading them; the archive changelog's other migrations name one, so this is a decision still to be made.
- **Files written by 0.5.0 cannot be opened by Entitle 0.4.1.** `migrate` replaces a file in place, so keep a copy first if an older Entitle must still read it.
- **Behavior that changed:** the file format; `issue` no longer requires the DRBG options; `--version` prints a second line; sealing error text starts `BSR2 encryption failed:`; a master key over 1024 bytes is refused; blank required fields, an unparseable `--expires` and a negative `--deployment-limit` exit 1 with an error instead of being written; routine errors print one `Error: ...` line instead of a traceback; `report` JSON gains `store_exists` and `unreadable_records`; a record without a `data` object is reported as `unparseable_record`; `track list --type` rejects unknown types; `verify` may print a note after `VERIFIED`; the `<store>.lock` file stays beside the store between writes (it is safe to delete when nobody is writing); the window's Issue tab writes to the same default path the other tabs read; the example application prints a different message when its check cannot run.
- **Python API** (code that imports Entitle's modules must change; the commands and the window do not):

  | In 0.4.1 | In 0.5.0 |
  | --- | --- |
  | `entitle.issue`, `entitle.verify` | `entitle.entitlements` (`issue_entitlement`; `verify_entitlement(path=...)`, was `file=`) |
  | `entitle.core.EntitleError`, `canonical_json`, `utc_now_iso` | `entitle.EntitleError`, `canonical_json`, `utc_now_iso` |
  | the rest of `entitle.core` (payload, rights, evaluation, `EntitlementResult`, `EntitlementDenied`) | `entitle.rights` (`build_rights()` is `make_rights()`) |
  | `entitle.bsr_adapter.protect_entitlement_payload(...)`, which returned an envelope dictionary | `entitle.entitlements.seal_entitlement(payload, ...)`, which returns the file text |
  | `entitle.bsr_adapter.verify_protected_entitlement(...)` and the adapter's load and save helpers | `entitle.entitlements.verify_entitlement`, `open_entitlement(text, issuer=..., subject=..., product=...)` (returns `(payload, previous_encryption)`), `read_entitlement_file`, `write_entitlement_file` |
  | `entitle.bootstrap.ensure_bsr_on_path()` and `vendor/` | `entitle.encryption.require()`, the linked 97_Encryption library |
  | `entitle.record_types` | `entitle.records` |
  | `entitle.tracking.deploy`, `.fork`, `.provenance`, `.query`, `.cli` | `entitle.tracking`; the command line is in `cli.py` |
  | `list_records(path)`, `build_report_for_path(path)` | `RecordStore(path).filter()`, `build_report(RecordStore(path))` |
  | `entitle.paths` | `gui.tabs` |

  Record functions take a `RecordStore`, not a path. `EncryptionNotFoundError`, `migrate_entitlement`, `uses_previous_encryption` and `require_text` are new. A program protected by Entitle, like `examples/protected_app_example.py`, needs `from entitle.rights import EntitlementDenied`.
- **Moving Entitle:** it only works with `97_Encryption` beside `98_Tooling`. A copy of the Entitle folder on its own reports `Encryption not found`, by design.
- **Not verified here:**
  - The final 0.5.0 code was exercised against the real `97_Encryption/Official` (all 215 tests, BSR2 Alpha 4 as exported from the archive) before the version number and the wording of two messages were changed for this release. After that change the suite was re-run against a small stand-in with the same interface, because the real library was not available in that environment; run `python -m pytest tests` against the real archive before publishing.
  - A real entitlement issued by Entitle 0.4.1 (the fixture above stands in), the Windows branch of the record-store lock, the window on a real display (the tests use a tkinter stand-in), macOS and network filesystems.
  - An invocation-by-invocation comparison of the final code against 0.4.1. A comparison of an interim build (19 of 23 invocations byte-identical, the other 4 intended differences) predates the encryption change and is not repeated.
  - BSR2 Alpha 4 itself, which is experimental research cryptography whose own tests live in `97_Encryption/Official/tests` and were not part of this change.
  - The archive snapshot's `.github/workflows` has no workflow for Entitle, so none was updated.
- No new external dependencies; the application is standard-library Python plus the archive's `97_Encryption`.

---

## [0.4.1] - 2026-09-10

An architecture-consistency release. Every `__init__.py` file in the project
has been removed; `entitle`, `entitle/tracking`, `gui`, and `gui/tabs` are now
PEP 420 implicit namespace packages, matching the convention already used
elsewhere in the Brisart ecosystem. No entitlement format, BSR2 protection
logic, or CLI/GUI behavior changed. If you only run `main.py`
`issue`/`verify`/`track`/`revoke`/`report`/`gui`, nothing about how you invoke
Entitle changes in this release.

### Removed

- **`entitle/__init__.py`** — previously re-exported `__version__` (itself
  read from the root `version.py`) and inserted the repository root onto
  `sys.path`. Every real entry point (`main.py`, `gui/app.py`,
  `examples/protected_app_example.py`, `tests/conftest.py`) already performed
  its own `sys.path` setup independently, so the file's only functional
  purpose had become exposing `entitle.__version__` — which nothing besides
  one test relied on. Removed with no functional loss.
- **`entitle/tracking/__init__.py`** — previously re-exported
  `count_deployments`, `register_deployment`, `deploy_from_file`,
  `record_fork`, `record_provenance`, and `list_records` from the tracking
  submodules. `entitle/tracking/cli.py` already imported directly from the
  submodules (`.deploy`, `.fork`, `.provenance`, `.query`); only the GUI's
  Deploy and Fork/Provenance tabs, and two test files, used the package-level
  re-export.
- **`gui/__init__.py`** and **`gui/tabs/__init__.py`** — both contained only a
  module docstring with no functional code; nothing imported from either at
  the package level.

### Changed

- **`gui/tabs/deploy_tab.py`** now imports `deploy_from_file` from
  `entitle.tracking.deploy` directly, instead of from the removed
  `entitle.tracking` package-level re-export.
- **`gui/tabs/fork_provenance_tab.py`** now imports `record_fork` from
  `entitle.tracking.fork` and `record_provenance` from
  `entitle.tracking.provenance` directly, instead of from `entitle.tracking`.
- **`tests/test_report.py`** and **`tests/test_tracking.py`** updated the same
  way: `record_fork`, `register_deployment`, `record_provenance`, and
  `list_records` are now imported from their owning submodules
  (`entitle.tracking.deploy`, `entitle.tracking.fork`,
  `entitle.tracking.provenance`, `entitle.tracking.query`).
- **`tests/test_paths.py`**'s version-parity test no longer does
  `from entitle import __version__`, since that only worked through the now-
  removed `entitle/__init__.py`. It now confirms the root `version.py`'s
  `__version__` is a well-formed string directly — `main.py`, the GUI, and
  this test all already read the version the same way (`from version import
  __version__`), so there was never a second version value to stay in sync
  with.

### Verified

- Confirmed by direct interpreter inspection that `entitle`, `entitle.tracking`,
  `gui`, and `gui.tabs` are genuine PEP 420 namespace packages after removal
  (`__file__` is `None`; `__path__` correctly resolves to each directory).
- Full test suite re-run with zero `__init__.py` files anywhere in the tree:
  82 tests pass, unchanged from 0.4.1.
- Full CLI lifecycle (issue, verify, track deploy, revoke, report) re-run
  end-to-end through `main.py` with identical results to 0.4.1.
- `tests/test_bsr_integrity.py` re-confirmed: the four vendored BSR2 files are
  untouched by this change and still match their pinned SHA-256 values.

### Notes

- This release contains no changes to the entitlement payload format, the
  BSR2 envelope protocol, the tamper-evident record format, or any CLI/GUI
  command or workflow behavior.
- If you have code that does `from entitle import __version__` or
  `from entitle.tracking import <function>` directly, update it to
  `from version import __version__` and
  `from entitle.tracking.<deploy|fork|provenance|query> import <function>`
  respectively. All function signatures and behavior are unchanged.
- No new external dependencies were introduced; the project remains pure
  Python, standard-library only.

---

## [0.4.0] - 2026-09-10

An architecture and consistency release, not a behavior release. This entry
covers a full internal reorganization of the project layout, naming, and
runtime-data hygiene brought up to parity with the rest of the Brisart
ecosystem. No entitlement format changed, no BSR2 protection logic changed,
and every existing CLI command still does exactly what it did in 0.3.x. If
you only use `main.py issue/verify/track/revoke/report`, nothing about how
you invoke Entitle changes in this release.

### Changed

- **Renamed `bsr/` to `vendor/`.** This is the same directory containing the
  four unmodified BrisartSecurityResearch (BSR2) modules; only the folder
  name changed, to match the naming convention used across the rest of the
  Brisart ecosystem. `entitle/bootstrap.py`'s `VENDOR_DIR` now points at the
  renamed directory.
- **Moved the version string to a root-level `version.py`.** Previously
  `__version__` lived inside `entitle/__init__.py`. It now lives in a
  standalone `version.py` at the repository root, which `entitle/__init__.py`
  and `main.py --version` both import from, so the package, the CLI, and any
  future packaging or release tooling read the version from exactly one
  place.
- **Renamed `entitle/constants.py` to `entitle/record_types.py`.** The module
  only ever held the five `record_type` string constants; the new name
  documents that directly.
- **Split `entitle/track.py` into an `entitle/tracking/` package.** The
  276-line module previously mixed governed deployment recording (which
  checks entitlement rights, deployment limits, and revocation status)
  together with purely documentary fork and provenance recording. It is now:
  - `tracking/deploy.py` — `register_deployment()`, `deploy_from_file()`,
    `count_deployments()`
  - `tracking/fork.py` — `record_fork()`
  - `tracking/provenance.py` — `record_provenance()`
  - `tracking/query.py` — `list_records()`
  - `tracking/cli.py` — the `track` subcommand group (`deploy`, `fork`,
    `provenance`, `list`), dispatched from `main.py`

  `tracking/__init__.py` re-exports every public function, so existing code
  only needs to change `from entitle.track import ...` to
  `from entitle.tracking import ...` — no function signatures changed.
- **Added `entitle/paths.py`** as the single source of truth for default
  runtime-data locations (`entitlements/`, `records/`, `reports/`) used to
  pre-populate GUI fields. These defaults were previously duplicated as
  literal path strings across several `gui/tabs/*.py` modules; a change to
  one no longer risks drifting from the others. The CLI is unaffected: it
  still requires an explicit `--store` on every command, by design.
- **`gui/` and `gui/tabs/` are now explicit packages** (added `__init__.py`
  to each), matching the rest of the project instead of relying on implicit
  namespace-package behavior.

### Fixed

- **`.gitignore` did not exclude Entitle's own runtime-data directories.**
  `entitlements/`, `records/`, and `reports/` — which hold issued entitlement
  envelopes and the tamper-evident deployment/fork/provenance/revocation log
  — were previously stageable and could have been committed the first time
  the tool was run inside the repository. All three directories are now
  explicitly ignored.
- **Nothing enforced the "BSR2 is vendored byte-for-byte unmodified" claim.**
  The changelog and documentation have always asserted this, but no test
  verified it. Added `tests/test_bsr_integrity.py`, which pins the SHA-256 of
  each of the four `vendor/brisart_security_*.py` files and fails CI if any
  of them drift from the pinned hash, and fails if an unexpected fifth
  `brisart_security_*.py` file appears in `vendor/` without a corresponding
  pinned entry.
- **Record entries had no schema version marker.** The entitlement *payload*
  already carried `"format": "entitle.entitlement.v1"`, but individual
  entries appended to the tamper-evident record log had no equivalent field.
  Every record written by `RecordStore.append()` now includes
  `"format": "entitle.record.v1"` inside the hashed region, so the on-disk
  record schema can be evolved in the future while still being able to
  recognize records written by this release.

### Added

- **CI matrix expanded to `ubuntu-latest`, `windows-latest`, and
  `macos-latest`** (previously Ubuntu only), each against Python 3.10-3.12.
  CI now also runs a full CLI lifecycle smoke test — issue, verify, track
  deploy, revoke, report — against a live entitlement on every run, not just
  the unit test suite.
- **`tests/test_paths.py`** covering the new `entitle/paths.py` defaults and
  confirming `entitle.__version__` matches the root `version.py` value.
- 11 new regression tests overall (71 → 82), covering the record format
  marker, the vendor integrity pins, and the new paths module.

### Notes

- This release contains no changes to the entitlement payload format
  (`entitle.entitlement.v1`), the BSR2 envelope protocol, or any encryption,
  authentication, or context-binding logic. Entitlements issued under 0.3.x
  verify unchanged under 0.4.0.
- If you have existing scripts or code importing `entitle.track` or
  `entitle.constants` directly, update those imports to `entitle.tracking`
  and `entitle.record_types` respectively; the functions and constants
  themselves are unchanged.
- No new external dependencies were introduced; the project remains pure
  Python, standard-library only.

---

## [0.3.2] - 2026-08-26

### Changed

- Removed the unused `from pathlib import Path` import from `gui/tabs/issue_tab.py`.

### Notes

- This is a cosmetic code cleanup release only.
- No functional behavior, entitlement processing, licensing logic, CLI commands, GUI workflows, file formats, or outputs were changed.
- Improves code cleanliness and reduces dead imports in the Issue tab implementation.

---

## [0.3.1] - 2026-08-18

This release is a follow-up architecture cleanup pass on top of 0.3.0's
package restructure. No governance logic, record-store semantics, or
entitlement behavior changed.

### Added

- `entitle/constants.py` — single source of truth for the five
  `record_type` strings (`deployment`, `fork`, `provenance`, `revocation`,
  `reinstatement`) used throughout the tamper-evident record store. These
  were previously duplicated as plain string literals across
  `entitle/track.py`, `entitle/revoke.py`, and `entitle/report.py`.
- `gui/widgets.py` — the shared `FormFrame` label/entry/checkbox helper used
  by every GUI tab, extracted out of the former single-file GUI.
- `gui/tabs/` — the GUI's six tabs (Issue, Verify, Deploy, Fork /
  Provenance, Revoke / Reinstate, Audit Report) are now individual plug-in
  modules (`gui/tabs/issue_tab.py`, `verify_tab.py`, `deploy_tab.py`,
  `fork_provenance_tab.py`, `revoke_tab.py`, `report_tab.py`), each exposing
  a `TAB_TITLE` string and a `build(parent, app)` function. `gui/app.py`
  now only builds the main window and loads tabs from an explicit
  `TAB_MODULES` registry — it has no per-tab logic of its own. Adding a new
  tab means adding one new file plus one line in `TAB_MODULES`; no other
  file needs to change.

### Changed

- `gui/app.py` reduced from a single 407-line file containing all six tabs
  to a 110-line core engine that only builds the window, the shared output
  pane, and the tab registry.
- `entitle/track.py`, `entitle/revoke.py`, and `entitle/report.py` now
  import their `record_type` strings from `entitle/constants.py` instead of
  repeating literal strings, so a typo in a record type now fails at import
  time (`ImportError`/`NameError`) instead of silently matching nothing.
- `main.py`'s command dispatch replaced an `if`/`elif` chain with a
  `COMMAND_MODULES` dict mapping command name to dotted module path. Adding
  a new top-level CLI command (beyond `issue`/`verify`/`track`/`revoke`/
  `report`/`gui`) now means adding one dict entry instead of another
  `elif` branch.

### Verified

- The full CLI lifecycle (issue, verify, deploy with `deployment_limit`
  enforcement and refusal, fork, provenance, revoke, deploy-while-revoked
  refusal, reinstate, check, audit report) was re-run end-to-end through
  `main.py` after the constants and dispatch-table changes, with identical
  results to 0.3.0.
- The modularized GUI was re-verified with the same headless test harness
  used for 0.3.0: instantiate the real `EntitleApp`, confirm all six
  registered tab plug-ins appear in the notebook, and click through every
  tab's button (issue → verify → deploy ×2 → 3rd deploy refused → fork →
  provenance → revoke → deploy-while-revoked refused → reinstate → check →
  report). All 11 assertions passed against the real backend. As before,
  actual on-screen rendering should be confirmed on a machine with a
  working Tkinter/Tk installation.

---

## [0.3.0] - 2026-08-18

This release restructures Entitle from a flat collection of scripts into a
proper package with a single command-line entry point, and adds a first
Tkinter GUI covering every core workflow. No governance logic, record-store
semantics, or entitlement behavior changed — this is an architecture and
usability release, not a behavior release.

### Added

- `main.py` — single CLI entry point. Replaces running each `entitle_*.py`
  script directly. Dispatches to `issue`, `verify`, `track`, `revoke`,
  `report`, and `gui` subcommands, e.g. `python main.py issue ...`,
  `python main.py track deploy ...`.
- `entitle/` — Entitle's own logic, reorganized into a proper Python
  package (`core.py`, `records.py`, `bsr_adapter.py`, `issue.py`,
  `verify.py`, `track.py`, `revoke.py`, `report.py`, `bootstrap.py`).
  Internal imports were converted from flat (`from entitle_core import ...`)
  to package-relative (`from .core import ...`).
- `entitle/bootstrap.py` — adds the sibling `bsr/` directory to `sys.path`
  so BrisartSecurityResearch's flat, top-level imports
  (`from brisart_security_primitives import ...`) resolve correctly from
  its new subdirectory location, without modifying a single line of BSR2.
  Every entry point (CLI, GUI, example) calls this before importing
  `entitle.bsr_adapter`.
- `bsr/` — BrisartSecurityResearch (BSR2) now lives in its own directory.
  The four `.py` files are byte-for-byte unchanged from the flat layout;
  only their location moved.
- Business logic extracted from CLI argument parsing in every `entitle/`
  module, e.g. `issue_entitlement(...)`, `verify_entitlement(...)`,
  `deploy_from_file(...)`, `record_fork(...)`, `record_provenance(...)`,
  `build_report_for_path(...)`. Each CLI subcommand is now a thin wrapper
  around a plain function with the same name and keyword arguments the GUI
  calls directly — the CLI and GUI can never drift out of sync with each
  other because they share one implementation.
- `gui/app.py` — a first Tkinter GUI. Tabs for Issue, Verify, Deploy,
  Fork / Provenance, Revoke / Reinstate / Check, and Audit Report. Every
  button calls directly into the same `entitle.*` functions used by the
  CLI. Requires only the Python standard library. Launch with
  `python main.py gui` or `python gui/app.py`.
- `examples/protected_app_example.py` — moved into its own directory,
  updated for the new package layout, and hardened to print a friendly
  message with a working example command when the demo entitlement file is
  missing, instead of crashing with an uncaught `FileNotFoundError`.

### Changed

- `protected_app_example.py` → `examples/protected_app_example.py`.
- Running an Entitle module directly as a script (e.g.
  `python entitle/issue.py`) is no longer supported, because its imports
  are now package-relative. Use `python main.py issue ...` (or
  `python -m entitle.issue ...`) instead.

### Verified

- The full lifecycle (issue, verify, deploy with `deployment_limit`
  enforcement and refusal, fork, provenance, revoke, deploy-while-revoked
  refusal, reinstate, check, audit report, hash-chain tamper detection) was
  re-run end-to-end through `main.py` in a clean directory with identical
  results to the pre-restructure flat layout.
- Every function the GUI calls was cross-checked against the real
  `entitle.*` function signatures with `inspect.signature`, and the GUI's
  button callbacks were exercised end-to-end against the real backend
  (issue → verify → deploy ×2 → 3rd deploy refused → fork → provenance →
  revoke → deploy-while-revoked refused → reinstate → check → report) using
  a headless test harness, since this development environment has no
  `_tkinter` extension available to open a real window. The GUI's actual
  on-screen rendering should be confirmed on a machine with a working
  Tkinter/Tk installation (standard on Windows, macOS, and most Linux
  desktop distributions) before relying on it day-to-day.
- BSR2's four `.py` files were confirmed byte-for-byte identical (SHA-256)
  before and after the move into `bsr/`.

### Notes

- No changes were made to any BrisartSecurityResearch (BSR2) source file.
  BSR2 remains an independent, experimental research dependency and should
  continue to be treated as controlled-environment protection unless
  independently reviewed.
- Runtime data directories (`entitlements/`, `records/`, `reports/`) keep
  their previous meaning and location at the repository root; no default
  store path was introduced, preserving the existing "operator always
  specifies `--store` explicitly" design principle.

---

## [0.2.1] - 2026-08-18

This release fixes integration bugs between `entitle_bsr_adapter.py` and the
real BrisartSecurityResearch (BSR2) module that prevented `entitle_issue.py`
from running at all against an unmodified BSR2 checkout. No governance logic,
record-store behavior, or entitlement semantics changed; every fix is
isolated to the BSR2 adapter wiring layer.

### Fixed

- `entitle_bsr_adapter.py` imported `BrisartSecurityDRBG`, `encrypt_envelope`,
  and `decrypt_envelope`, but the real BSR2 module exports `BrisartDRBG`,
  `encrypt`, and `decrypt`. Import aliasing was added so BSR2 source files
  can be used completely unmodified.
- `protect_entitlement_payload()` called BSR2's `encrypt()` with a `drbg=`
  keyword argument, but BSR2 names that parameter `rng`. Calls were updated
  to `rng=drbg`.
- `make_context()` returned `bytes`, but BSR2's `encrypt()` and `decrypt()`
  both require `context` to be a `str`. `make_context()` now returns a
  string.
- Confirmed the README's suggested `bsr/` subfolder layout does not work as
  written: BSR2's own modules (`brisart_security_drbg.py`,
  `brisart_security_envelope.py`) use flat imports
  (`from brisart_security_primitives import ...`) that cannot resolve from
  inside a subpackage without modifying BSR2 itself. Documented that BSR2
  source files must be placed flat, beside the Entitle source files,
  completely unmodified. (Superseded in 0.3.0 by
  `entitle.bootstrap.ensure_bsr_on_path()`, which adds `bsr/` to `sys.path`
  directly so the flat layout can live in its own subdirectory.)

### Verified

- Every known-answer vector shipped with BrisartSecurityResearch (hash, MAC,
  stream, DRBG output, envelope decrypt, and a deterministic envelope
  re-encrypt) was reproduced byte-for-byte against the unmodified BSR2
  source, confirming the cryptographic primitive layer was untouched and
  correct throughout.
- The full lifecycle was exercised end-to-end in a clean environment:
  issue, verify, governed deploy (including `deployment_limit` enforcement
  and refusal), fork, provenance, revoke, reinstate, and audit reporting.
- Hash-chain tamper detection was confirmed directly: a manually corrupted
  historical record was correctly flagged by `verify_chain()`, with the
  exact broken index reported.

### Notes

- No changes were required to `entitle_core.py`, `entitle_records.py`,
  `entitle_track.py`, `entitle_revoke.py`, or `entitle_report.py`; all
  governance and tamper-evidence logic in those modules was already correct.
- BrisartSecurityResearch (BSR2) source itself was not modified in any way.
  BSR2 remains an independent, experimental research dependency and should
  continue to be treated as controlled-environment protection unless
  independently reviewed.

---

## [0.2.0] - 2026-08-04

This release brings the implementation in line with the README by adding the
deployment, fork, provenance, revocation, and audit capabilities that were
previously described but not yet built. All new tooling is pure standard
library and writes to a single local, tamper-evident record store.

### Added

- `entitle_records.py` — append-only, hash-chained record store. Each entry is
  linked to the previous one through a SHA-256 chain, so any edit, deletion, or
  reordering of earlier records is detectable via `verify_chain()`.
- `entitle_track.py` — record deployments, internal forks, and provenance /
  ownership to the shared store. Includes `deploy`, `fork`, `provenance`, and
  `list` subcommands.
- Governed deployments: `register_deployment` only records a deployment when the
  entitlement verifies, grants `can_run`, is not revoked, and its
  `deployment_limit` has not been reached.
- `entitle_revoke.py` — offline revocation with `revoke`, `reinstate`, and
  `check` subcommands. Revocation status is derived from the record log, so an
  entitlement can be revoked and later reinstated while preserving full history.
- `entitle_report.py` — audit and reporting over the record store, with text or
  JSON output. Summarizes records by type and deployments by product, and
  verifies the tamper-evident hash chain across the whole store.

### Changed

- `entitle_track.py` deployment gate now consults `entitle_revoke.is_revoked`
  before recording, so revoked entitlements are refused for new deployments.
- `README.md` rewritten to document the actual tools with runnable CLI examples,
  and to add Requirements, Project Layout, Deployment Tracking rules, Revocation
  & Reinstatement, and the Tamper-Evident Record Store.

### Removed

- Dropped the unimplemented **License Management** feature section from the
  README so documentation matches shipped functionality.

### Notes

- The record store path is always explicit (`--store`); there is no default
  location by design, keeping record placement fully under operator control.
- Entitlement protection continues to rely on the experimental
  BrisartSecurityResearch (BSR) modules via `entitle_bsr_adapter.py`. Treat as
  controlled-environment protection unless reviewed.
