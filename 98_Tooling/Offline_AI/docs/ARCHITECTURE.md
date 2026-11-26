# Architecture

The desktop (`run.py`) and headless CLI (`cli.py`) share `core/service.py`. Both bootstrap external Native APIs before importing their consumers, then migrate eligible legacy state before opening the index. Neither launcher owns ranking, storage, or file-format handling.

| Responsibility | Owner | Boundary |
|---|---|---|
| Application operations | `core/service.py`, `core/conversation.py` | Open handles, apply question scope, compose cited answers, and coordinate mutations. UI and CLI do not duplicate these operations. |
| Local input | `io/readers.py`, `binary_readers.py`, `extractor.py` | Discover paths and extract text. No index or network ownership. |
| Persistence | `knowledge/index.py`, `knowledge/vault.py`, `core/session_memory.py`, `core/settings.py` | The index stores source records and postings; the vault owns notes and collections; memory and settings own their own state. |
| Retrieval and excerpts | `knowledge/ranker.py`, `relevance_engine.py`, `synthesizer.py`, `intent.py` | Brisart implements candidate selection, ranking and excerpt choice; SQLite is not a ranking engine. |
| Desktop | `ui/app.py`, `sidebar.py`, `chat_panel.py`, `dialogs.py`, `import_progress.py`, `theme.py` | Tk owns presentation. Search and import run on background threads, one operation at a time. Tk consumes results and the latest import counts; the ingest caller remains the sole SQLite writer during import. |
| Environment and platform boundaries | `state.py`, `native_path.py`, `ui/windows_drop.py` | State paths and migration, external API discovery, and Windows drop handling stay independently owned. |

## Data flows

**Import:** File discovery and extraction → ingestion → indexed text and token postings. Relevance code never reads arbitrary files to answer a search.

**Question:** Enabled file and note types → Brisart query groups and lexical shortlist → passage coverage and tie-breakers → cited excerpts. Unique supported spelling recovery uses the eligible indexed vocabulary. Both toggles off means no lookup. Historical web rows can remain in the database but are excluded from answer and vault content lookups. Filename filters in Manage Sources are metadata filters, not content ranking.

**Note:** Attach an excerpt from indexed file text → validate it against the source → save a note snapshot. Removing a file entry leaves the disk source and independent saved notes intact.

Review file-specific details in the six-section source headers. Keep Linux benchmark tooling and its comparator dependencies under `scripts/`, outside the application entry points.
