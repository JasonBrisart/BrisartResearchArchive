# Architecture

## Runtime ownership

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

## Dependency direction

The entry points bootstrap the environment and delegate to core services. The core coordinates operations but does not own extraction or relevance scoring. IO produces text for ingestion; knowledge persists that text and supplies ranked, cited evidence. UI components consume service results and return user actions to the service.

The retrieval pipeline deliberately has one owner for each decision. Intent rules identify supported query forms; the ranker constructs the query plan and retrieves candidates; the relevance engine assesses whether passages support the requested claim; and the synthesizer renders the selected evidence. Duplicating these decisions in the UI or conversation layer would allow the same question to receive inconsistent interpretations.

## Concurrency and persistence

Bulk file preparation can use spawned processes, but SQLite writes are performed by the caller. The desktop polls progress on the Tk thread rather than allowing workers to update widgets. Cooperative cancellation prevents new work from being indexed while already dispatched preparation and selected writes finish safely.

The application stores index records, research notes, conversation memory and settings under their respective owners. The default Windows state path is separate from the program directory. Native API discovery is an environment concern, not an alternate retrieval implementation.

## Evidence lifecycle

A question is scoped to enabled source types before candidate retrieval. The engine can identify direct evidence, limited evidence, inferred dependency chains, and conflicts. A chain is not reported as complete unless every required link can be cited within the available budget. Date and version qualifiers apply to the cited claims rather than being inferred from import order.

This architecture does not include an independently maintained knowledge graph, online search service, or third-party ranking engine. Bounded candidate pools and supported English patterns are practical implementation limits and must be considered when interpreting results.

