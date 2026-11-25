# Knowledge and evidence

`index.py` owns the SQLite index, file previews and transactional source removal. `ingest.py` imports local files; `ranker.py` and `relevance_engine.py` score candidate evidence; `synthesizer.py` selects cited excerpts; `vault.py` stores and retrieves notes and related metadata. `tests/` covers indexing, ranking and synthesis. The database schema can retain historical `web` records without searching or deleting them; the conversation layer searches only `file` and `note` records.
