# Testing

From `Offline_AI`, with Python, pytest and the five external Brisart Native APIs available:

```text
python scripts/run_tests.py -q
python scripts/debug_offline_replay.py
```

The runner configures external imports before collecting co-located tests. Pass a test path after `run_tests.py` for a focused run. Test state is temporary. During this pass, **281 tests, 5 subtests and all 4 offline replay cases passed** using the supplied Brisart hash, inflate, JSON, markup and URL implementations staged outside the project, with no stand-ins. This does not validate a newer or different copy of the Official folder. The lower count reflects removal of presentation constant-shape checks; the Tk-free dependency boundary remains tested.

**Windows smoke test before distribution:** With your real Official folder, run the headless suite and start `run.py`. Browse and drop files onto the import queue; import them, attach an excerpt to a note, search, and remove the indexed source. Confirm the original file and separate note remain. Check the busy state, closing during a query, and keyboard shortcuts. This pass did not exercise live Tk or Explorer drag-and-drop.

The measurements below are preserved 1.4.0 release evidence, not reruns from this documentation pass.

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
