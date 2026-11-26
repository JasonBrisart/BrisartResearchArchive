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

## Index and import lifecycle

The index holds local source records and token postings. Ingestion may prepare independent files in spawned workers, but writes are performed by the caller in discovery order. Workers do not open the index as competing writers. This preserves a straightforward mutation boundary even when preparation is parallel.

The vault manages research notes and their source relationships. Notes may remain meaningful after an indexed file entry is removed, so the two kinds of records are not interchangeable. Source-management filters operate on metadata such as title and path; they are not evidence-ranking rules.

## From question to cited answer

The ranker builds a query plan containing the interpreted question and its eligible topic groups. It retrieves candidate sources within the enabled scope. The relevance engine then examines passages for the requested evidence shape, including explanatory mechanisms, comparisons, dates, and direct or inferred relationships.

The synthesizer renders the selected passages and references. It must not silently resolve conflicts or upgrade a tentative claim to a fact. An evidence-quality grade describes how directly a passage addresses the question; it is not a calibrated probability that the source is true.

## Relationship and temporal boundaries

Relationship claims preserve ordered endpoints. Explicit aliases can connect names, but ambiguous aliases cannot establish an inferred chain. Dependency chains are bounded, and each link needed for an inference must fit the citation budget. Opposing claims are shown together when possible; insufficient citation space is reported rather than used to hide one side.

Date and release qualifiers are applied to the evidence actually cited. The engine recognizes supported wording and formats, but does not infer the current release from a filename or resolve every natural-language paraphrase. A benchmark showing the correct file first does not by itself prove that the answer is complete or historically correct.

## Regression coverage

Tests use temporary SQLite indexes to exercise ranking, source scope, distractors, duplicate records, conflicting dates, and citation completeness. Historical benchmark results and current measured outcomes are recorded in `docs/TESTING.md`, with limitations kept next to the corresponding result.

