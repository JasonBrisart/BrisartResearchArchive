# Knowledge and evidence

`index.py` owns the SQLite index, file previews and transactional source removal. `ingest.py` imports local files; `ranker.py` and `relevance_engine.py` rank by how much of the question occurs together in an indexed passage; `synthesizer.py` uses the same query concepts to select cited excerpts and label partial matches; `vault.py` stores and retrieves notes and related metadata. `tests/` covers indexing, ranking and synthesis. The database schema can retain historical `web` records without searching or deleting them; the conversation layer searches only `file` and `note` records.

Retrieval and excerpts share the passage matcher. Short document profiles are cached in memory, exact Python declarations rank ahead of mentions for code-style identifier queries, and compact labels retain the value on the next line when it starts with a number or yes/no. No rebuild of the SQLite index is required.

Brisart owns query concepts, token postings, candidate selection, ranking and passage scoring. Notes share the document ranker. Collection matching and timelines use the same token postings without relevance sorting. File pickers retain a separate title/path filter for source management; it does not rank content. SQLite is storage, not a ranking engine.
