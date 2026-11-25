# Testing

From the Offline_AI directory, run:

```text
python scripts/run_tests.py -q
python scripts/debug_offline_replay.py
```

The test runner installs the external Native API path before collecting the co-located `unittest` tests through pytest. Set `BRISART_NATIVE_API` when the Archive's `94_Native_API's/Official` folder is not in the usual parent layout.

The tests cover local ingestion, ranking, citations, notes, settings, state migration, module resolution, layout and the absence of public-web runtime routes. The offline replay uses fixed fixtures and does not contact providers. Web provider, crawler and fetch tests are removed with their implementation.

No desktop GUI or Windows-specific file-locking behavior is exercised in this headless environment. Existing historical web rows are retained but are not eligible for answers.

On Windows, open Add Sources and drop a file and a folder from Explorer into the list. Verify that import begins only after clicking Import Sources. Then open Add Note, select the imported file, attach a highlighted passage, and verify that the note includes the excerpt and its original path. These desktop steps are not covered by the headless run.

## 1.4.0 benchmark


| Retrieval method | Top 1 | Top 5 | Top 10 | Typo top 1 | Median query ms |
|---|---:|---:|---:|---:|---:|
| Attached Brisart baseline | 220/270 | 233/270 | 235/270 | 0/30 | 214.63 |
| BrisartAI 1.4.0 | 244/270 | 260/270 | 263/270 | 24/30 | 96.35 |
| SQLite FTS5 BM25 | 208/270 | 228/270 | 234/270 | 0/30 | 0.15 |
| SQLite FTS5 BM25 + Porter | 201/270 | 225/270 | 230/270 | 0/30 | 0.18 |
| scikit-learn TF-IDF | 219/270 | 232/270 | 236/270 | 0/30 | 1.15 |
| ripgrep + match-count sort | 114/270 | 174/270 | 212/270 | 0/30 | 19.61 |

## Method and limits

- 124 installed Python standard-library source files. The 270 queries cover 120 symbol lookups, 120 exact docstring-derived descriptions and 30 deliberately transposed spellings. AST extracted the first 120 eligible declarations in filename order. The target is the declaration's file, not a human-judged set of every relevant result. Descriptions are not independent paraphrases, and this is not an end-to-end comparison of research assistants.
- Target at first rank improved on 24 queries and regressed on 0 relative to the attached Brisart snapshot. The snapshot was restored against its manifest; it identifies as 1.3.0 but already contains previously unreleased retrieval work.
- Every system searched the same local corpus and query strings. SQLite FTS5 used BM25 with a title weight of 2; scikit-learn 1.5.1 used word and bigram TF-IDF; ripgrep used case-insensitive whole-word matches sorted by count. Only Brisart uses its own spelling recovery. Competitors are benchmark-only, not runtime components.
- One timed pass after index construction, sequential queries in pinned order. Medians exclude indexing and answer rendering, but ripgrep includes process startup. Do not treat the timings as independent speed ratings.
- Linux Python 3.12.16, SQLite 3.44.0. Seccomp denied socket creation and connections; IPv4 and IPv6 probes confirmed the restriction. Corpus SHA-256: `2d20bf0a3812f99c541558cb5b861d3cc6056e31b7488ec1a454b9d19f6efbf4`.
- Brisart ran with the supplied URL helper and temporary test-only substitutes for missing Official Native APIs. The benchmark does not cover Windows GUI or non-code research quality.

Raw ranks and per-query timings are in `scripts/benchmark_data/`. On Linux, stage the original source as `baseline/` and the updated `Offline_AI/` side by side. Copy `scripts/benchmark_retrieval.py` and the pinned `queries.json` into their common parent, then set `BRISART_NATIVE_API` to the real external APIs. Run `python benchmark_retrieval.py MODE` for `baseline`, `Offline_AI`, `unicode`, `porter`, `tfidf` or `ripgrep`. Requires libseccomp; the competitor runs also require the corresponding benchmark dependencies. Reuse the same Python build and standard library to reproduce the corpus.
