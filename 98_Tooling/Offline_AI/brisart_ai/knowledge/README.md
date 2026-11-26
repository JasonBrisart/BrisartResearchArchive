# Knowledge

This folder owns BrisartAI's local research library and evidence pipeline. It stores indexed sources and notes, prepares imported files, retrieves relevant records and selects cited excerpts.

## Storage and ingestion

- `index.py`: Owns the SQLite source records, token postings and source removal.
- `vault.py`: Manages research notes and their related metadata.
- `ingest.py`: Discovers and prepares files, then commits them through the caller-owned SQLite writer. Bulk preparation may use spawned processes.

## Retrieval and answers

- `ranker.py`: Builds the shared query plan, retrieves eligible candidates and ranks them.
- `relevance_engine.py`: Assesses passage evidence, dependency relationships, uncertainty, conflicts and citation completeness.
- `synthesizer.py`: Presents the engine-selected excerpts with source references and support labels.
- `tests/`: Exercises indexing, import, ranking, evidence selection and citation regressions.

## Operational boundaries

SQLite persists the library; Brisart's own code determines relevance. Source-management title/path filtering is not answer ranking. The application answers from enabled local files and notes, not live internet searches. An indexed copy may be older than the original file on disk.

Relationship inference is bounded and is not an exhaustive knowledge graph. Duplicate-source handling, release/date qualifiers and confidence labels describe evidence support, not independently verified truth. See [Testing](../../docs/TESTING.md) for the limits of measured retrieval accuracy.
