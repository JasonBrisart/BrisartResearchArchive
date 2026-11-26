# Knowledge and evidence

`index.py` owns the SQLite index, file previews and transactional source removal. `ingest.py` imports local files; `ranker.py` and `relevance_engine.py` rank by how much of the question occurs together in an indexed passage; `relevance_engine.py` selects evidence and reports support status; `synthesizer.py` formats those excerpts and citations; `vault.py` stores and retrieves notes and related metadata. `tests/` covers indexing, ranking and synthesis. The database schema can retain historical `web` records without searching or deleting them; the conversation layer searches only `file` and `note` records.

Retrieval and excerpts share the passage matcher. Short document profiles are cached in memory, exact Python declarations rank ahead of mentions for code-style identifier queries, and compact labels retain the value on the next line when it starts with a number or yes/no. No rebuild of the SQLite index is required.

Brisart owns query concepts, token postings, candidate selection, ranking and passage scoring. Notes share the document ranker. Collection matching and timelines use the same token postings without relevance sorting. File pickers retain a separate title/path filter for source management; it does not rank content. SQLite is storage, not a ranking engine.

## Automatic multicore import

On desktop and CLI imports, BrisartAI uses spawned processes to read, parse and hash independent files. Capacity follows the available logical CPUs and the number of files, subject to the 61-worker Windows process-pool limit. A single file runs directly. Workers inherit the launcher's external Native API path and do not open SQLite. The caller adds prepared sources in discovery order. If the pool becomes unavailable, the caller finishes the uncommitted files serially. There is no setting to enable this, and query ranking and SQLite writes remain serial. Desktop import cancellation may supply a cooperative stop callback. Discovery stops between entries; the selected file can finish, queued preparation is canceled where possible, and dispatched preparations drain without indexing.

For two-topic comparisons, the ranker admits a bounded set of single-side candidates outside the initial pool and collapses exact duplicate bodies within the same source type before filling result slots. It does not merge or delete indexed sources.

The ranker builds the shared query plan. Conversation uses it for scoped retrieval and passes it through the synthesizer to `relevance_engine.py` for excerpt selection. The synthesizer renders evidence and citations; it does not independently classify the query.

`relevance_engine.py` supplies the passage grade used by both ranking and excerpt selection. Direct expiry evidence ranks above related renewal context; ranking may surface related documents that answer selection declines to cite.
