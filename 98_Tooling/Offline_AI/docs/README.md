# BrisartAI

BrisartAI is a local-only, source-grounded research assistant. It imports files, stores notes and answers questions using indexed local evidence. It does not generate unsupported answers or search the internet.

## Start

From `98_Tooling/Offline_AI`:

```text
python run.py
python cli.py counts
python cli.py import PATH [PATH ...]
python cli.py note "Title" "Body"
python cli.py notes
python cli.py ask "question"
```

## Sources and notes
The sidebar groups library and preference actions. Ctrl+L focuses the question field and F1 opens Help. The workspace header shows which sources are enabled.

- **Add Sources:** Browse for multiple files or select a folder. On Windows, you can also drop files and folders from Explorer into the list. Review the queue, then click **Import Sources**. Folder imports include supported files in subfolders. On other platforms use the Browse buttons.
- **Add Note:** Find an imported source, highlight text in its indexed preview, and click **Attach Highlighted Text**. Add a title and your own observations, then save. You can also save a standalone note. A saved excerpt keeps its original title and path and remains in the note after the source is removed.
- **Manage sources:** Search by title, path or type. Ctrl/Shift-click multiple rows, or press Ctrl+A to select all visible rows. Removal never deletes original files. Delete a saved note separately to remove its stored excerpt.

The CLI has no `research` command or `--web` option.

## Dependencies and data

The application loads seven native modules from the Archive's external `94_Native_API's/Official` folder. A detached checkout can point `BRISART_NATIVE_API` at the external directory containing those modules. No API implementation is bundled with Offline_AI.

On Windows, the SQLite index and settings live under `%APPDATA%\Brisart Research Archive\BrisartAI`. The `BRISARTAI_STATE_DIR` override selects another location. Eligible old state is migrated on startup without overwriting existing populated data.

Settings control whether **Local Files** and **Research Notes** participate in answers. Previously indexed web records may remain in an existing database but are excluded from answers and are not fetched or deleted by this update.

## Project layout

- `run.py`, `cli.py`, `version.py`: the only root files.
- `brisart_ai/core/`: shared application service, conversation and settings.
- `brisart_ai/io/`: document readers and text extraction.
- `brisart_ai/knowledge/`: SQLite index, local ingestion, ranking, citations and notes.
- `brisart_ai/ui/`: Tk desktop.
- `brisart_ai/`: state paths, native dependency discovery, shared utilities and intent.
- `scripts/`: headless tests and offline replay.
- `docs/`: architecture, testing, security and release history.

See `ARCHITECTURE.md` for ownership, `TESTING.md` for validation and `SECURITY.md` for local-data protections.
