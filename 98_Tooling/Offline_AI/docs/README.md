# BrisartAI 1.4.0

BrisartAI indexes local files and research notes, then answers questions with excerpts and citations. It does not search the internet. Results reflect the indexed copy, not necessarily the current file on disk.

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

1. **Add sources:** Queue files or folders, then choose **Import Sources**. Folder imports recurse. Windows Explorer drops can add to the queue; use Browse if drops are unavailable. A supported suffix is not a guarantee that text can be extracted. Scanned PDFs need text supplied separately.
2. **Add research note:** Write a standalone note, or highlight indexed text and select **Attach Highlighted Text**. The saved excerpt carries the original title and path as a snapshot.
3. **Ask:** Type a question and press Enter. The workspace shows which source types are active. **Search settings** controls eligibility without deleting data. Ctrl+L focuses the question field and F1 opens Help.
4. **Manage sources:** Filter by title, path or kind. Ctrl/Shift-click selects multiple rows; Ctrl+A selects the visible rows. Removing a file entry never deletes the disk original. Remove a note separately if it contains an excerpt you no longer want indexed.

## State and upgrading

Windows stores the default index and settings in `%APPDATA%\Brisart Research Archive\BrisartAI`. `BRISARTAI_STATE_DIR` overrides this directory and disables automatic legacy migration. With the default path, startup can migrate eligible old state without overwriting populated destination data. Reimport changed files when you need updated evidence. No database rebuild is required for this package.

When replacing an older program folder, preserve any project-local legacy database or settings until migration or backup is confirmed. Close the app before replacing program files. Do not delete the external API folder or per-user state.

- [Architecture and ownership](ARCHITECTURE.md)
- [Testing and benchmark evidence](TESTING.md)
- [Local data and security](SECURITY.md)
- [Release history](CHANGELOG.md)
