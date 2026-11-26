# Docs

This folder contains the user-facing BrisartAI guide, versioned engineering changelog, and test and benchmark record. The documents explain how to operate and validate the application; they are not runtime configuration.

`CHANGELOG.md` preserves release history and implementation rationale. `TESTING.md` distinguishes executed tests and measurements from historical benchmarks and integration checks still outstanding.

## Documentation in this folder

- [README.md](README.md): Installation, launch commands, source management and local state.
- [ARCHITECTURE.md](ARCHITECTURE.md): Runtime responsibilities, module ownership and data flow.
- [SECURITY.md](SECURITY.md): Local-data exposure, deletion boundaries and file-parser safeguards.
- [TESTING.md](TESTING.md): Reproduction commands, executed tests, benchmark results and limitations.
- [CHANGELOG.md](CHANGELOG.md): Versioned changes and engineering rationale, newest release first.

## Application overview

BrisartAI indexes local files and research notes, then answers questions using selected excerpts and citations. It does not search the internet. Results reflect the indexed copy and may differ from a source subsequently changed on disk.

## Start here

Keep `Offline_AI` under `98_Tooling` in the Archive, or point `BRISART_NATIVE_API` at an external folder holding `brisart_hash.py`, `brisart_inflate.py`, `brisart_json.py`, `brisart_markup.py` and `brisart_url.py`. In the Archive layout the loader prefers `94_Native_API's/Official`. It does not download or bundle the helpers. A full existing Official installation remains usable.

From `Offline_AI`, run `python run.py` for the desktop (requires Tk) or use the CLI:

```text
python cli.py import "notes.md" "Reference Library"
python cli.py ask "What is the permit fee?"
python cli.py note "Experiment 14" "Check the readings against the baseline."
python cli.py notes --limit 10
python cli.py counts
```

Place `--db PATH` before a subcommand to use another index. This does not change the settings path.

## Work with sources

1. **Add sources:** Queue files or folders, then choose **Import Sources**. After **Import Sources**, the dialog scans for supported files, then shows a progress bar, percentage, files left, indexed count, elapsed time, and an estimated time remaining. The ETA appears after enough files finish and can change as file sizes vary. The dialog keeps the final totals until you close it. Choose **Cancel Import** to stop only the import. **No** continues; **Yes** lets the current file finish, cancels the rest, and keeps BrisartAI open. Already indexed files are kept. The progress bar and ETA disappear while the app waits for the current file and worker cleanup. Once cleanup is done, the dialog reports **Import stopped**. Folder imports recurse. Bulk imports use available logical CPUs automatically; there is no toggle. Windows Explorer drops can add to the queue; use Browse if drops are unavailable. A supported suffix is not a guarantee that text can be extracted. Scanned PDFs need text supplied separately.
2. **Add research note:** Write a standalone note, or highlight indexed text and select **Attach Highlighted Text**. The saved excerpt carries the original title and path as a snapshot.
3. **Ask:** Type a question and press Enter. The status line shows elapsed time while the search runs. The scope strip stays visible while you search. **Results** shows answers and evidence; **Activity** shows imports, note saves and search diagnostics. **Search settings** controls eligibility without deleting data. Ctrl+L focuses the question field and F1 opens Help.
4. **Manage sources:** Filter by title, path or kind. Ctrl/Shift-click selects multiple rows; Ctrl+A selects the visible rows. Removing a file entry never deletes the disk original. Remove a note separately if it contains an excerpt you no longer want indexed.

## State and upgrading

Windows stores the default index and settings in `%APPDATA%\Brisart Research Archive\BrisartAI`. `BRISARTAI_STATE_DIR` overrides this directory and disables automatic legacy migration. With the default path, startup can migrate eligible old state without overwriting populated destination data. Reimport changed files when you need updated evidence. No database rebuild is required for this package.

When replacing an older program folder, preserve any project-local legacy database or settings until migration or backup is confirmed. Close the app before replacing program files. Do not delete the external API folder or per-user state.

- [Architecture and ownership](ARCHITECTURE.md)
- [Testing and benchmark evidence](TESTING.md)
- [Local data and security](SECURITY.md)
- [Release history](CHANGELOG.md)
