# Testing

From `Offline_AI`, with Python, pytest and the five external Brisart Native APIs available:

```text
python scripts/run_tests.py -q
python scripts/debug_offline_replay.py
```

The runner configures external imports before collecting co-located tests. Pass a test path after `run_tests.py` for a focused run. Test state is temporary. During this pass, **281 tests, 5 subtests and all 4 offline replay cases passed** using the supplied Brisart hash, inflate, JSON, markup and URL implementations staged outside the project, with no stand-ins. This does not validate a newer or different copy of the Official folder. The lower count reflects removal of presentation constant-shape checks; the Tk-free dependency boundary remains tested.

**Windows smoke test before distribution:** With your real Official folder, run the headless suite and start `run.py`. Browse and drop files onto the import queue; import them, attach an excerpt to a note, search, and remove the indexed source. Confirm the original file and separate note remain. Check the busy state, closing during a query, and keyboard shortcuts. This pass did not exercise live Tk or Explorer drag-and-drop.

The measurements below are preserved 1.4.0 release evidence, not reruns from this documentation pass.

## 1.6.0 benchmark (2026-11-26)

This is a **new execution on the packaged 1.6.0 source**, not a copy of the 1.4.0 results below. The environment was Linux with temporary SQLite indexes and local standard-library substitutes for the unavailable first-party Brisart hash, JSON, URL and inflate modules. Those substitutes were injected only into the test process and are **not included in the release**. The official Native API integration and live Windows desktop remain unverified.

### Judged retrieval relevance and latency

The fixed `knowledge/tests/test_search_quality.py` corpus contains 12 curated files and 14 judged queries spanning mechanism explanations, comparisons, permit facts, and filter behavior. Each query's correct file was labeled before ranking. Three independent insertion orders were tested with the production `ranker.search` function, limit 3 and file-only scope. Elapsed time measures the Python search call after indexing, not import, GUI, or answer rendering.

| Index insertion order | Correct top-1 | Top-1 accuracy | Median search latency | Observed p95 search latency |
|---|---:|---:|---:|---:|
| Original | 14/14 | 100% | 0.673 ms | 1.663 ms |
| Reversed | 14/14 | 100% | 0.653 ms | 0.987 ms |
| Seeded shuffle (17) | 14/14 | 100% | 0.626 ms | 0.914 ms |
| **Combined** | **42/42** | **100%** | Not pooled | Not pooled |

These are 42 repeated judgments over **14 unique questions**, not 42 independent examples. Each p95 is the sorted observation at index `int(0.95*(14-1))`, rather than a statistically stable production percentile. The corpus is tiny and curated, so the timing is not comparable to the historical 1.4.0 benchmark's 124-file, 270-query corpus. No new competitor benchmark was executed.

### Automated test executions

| Execution | Observed outcome | Interpretation |
|---|---|---|
| Direct `pytest` collection without external APIs | 19 collection errors, 1 skipped | Missing Brisart helper imports; not a code correctness verdict. |
| Focused search, intent and answer tests with local substitutes | **42 tests passed, 183 subtests passed** | Includes judged ranking and adversarial evidence checks. |
| Broader intent, knowledge and conversation tests with local substitutes | **174 passed, 189 subtests passed** | All selected tests passed after correcting the temporary runner bootstrap. |

The initial broader execution reported 173 passed, 1 failed, and 189 subtests passed because the temporary harness launched pytest at module import time, which is unsafe for spawned child processes. The traceback explicitly reported Python's multiprocessing bootstrapping error. The harness was corrected to call pytest only under `if __name__ == "__main__":`, and the **same selected tests were rerun successfully: 174 passed and 189 subtests passed in 19.81 seconds**. This was a harness-only correction outside the distributed project, not a change to BrisartAI's importer. The stand-ins remain process-local test substitutes rather than official Native APIs.

**Release gate:** Run `python scripts/run_tests.py -q` and `python scripts/debug_offline_replay.py` with the official Native API stack on the target Windows system, then smoke-test import cancellation, search, citations and the Tk workspace before publication. Do not represent this local benchmark as proof of production throughput or superiority over other retrieval systems.

## Historical 1.4.0 benchmark


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

## Development regression history

The following entries record earlier failures and follow-up tests. They are historical engineering evidence, not new 1.6.0 benchmark results.

### Reported framework-question regressions

Run from `Offline_AI` with the official Native API stack and the development test runner:

```text
python scripts/run_tests.py brisart_ai/core/tests/test_answer_quality_reports.py -q
```

The tests replay `how does tfl work?` and `how does riet compare to sst?` through the real conversation, ranking and excerpt code with a temporary SQLite index. The small curated corpus uses reported excerpts as distractors and paraphrased framework notes as positive evidence. It does not import the full archive or touch the live index. The permit-fee control checks that an answer citation resolves to the corresponding indexed source.

BrisartAI 1.5.0 baseline: all five quality scenarios exposed a gap; the citation control passed. For TFL, the engine returned name-only excerpts without warning and omitted the carry-forward step even when a mechanism source was indexed. For RIET versus SST, it accepted co-mentions as evidence, did not flag the missing side, and omitted both role passages when good definitions were indexed separately. The baseline used local standard-library stand-ins for the unavailable Brisart hash, URL, and JSON helpers; it was not an official Native API or full-library integration run. This baseline predates the answer-quality fix.

### Answer-quality follow-up

The same test command reruns both reported questions. The matrix varies mechanism phrasing, ingest order, comparison order and phrasing, and availability of both roles, one role, or neither. Additional controls cover paragraph boundaries, an unrelated transportation comparison and citation integrity. Fixtures are curated excerpts and paraphrases, not a full-archive benchmark.

The focused follow-up passed 95 tests and 32 subtests across the replay, conversation, synthesizer, ranker, relevance engine and SQLite index suites using the same local-only helper stand-ins. They are not shipped. The full official Native API run and a replay on the real archive remain outstanding.

### Raw search relevance gate

Run from `Offline_AI` using the official Native API stack and development test runner:

```text
python scripts/run_tests.py brisart_ai/knowledge/tests/test_search_quality.py brisart_ai/core/tests/test_answer_quality_reports.py -q
```

The raw gate calls the production ranker over a temporary SQLite index, independent of excerpt selection. Fourteen judged queries run against the same corpus in original, reversed, and seeded shuffled insertion orders, plus warm repeats interleaved with unrelated searches. Target passages must rank first, not merely appear somewhere. Separate cases test whether both evidence sources survive a top-eight comparison under duplicate-export pressure, whether out-of-scope material stays out, and whether unrelated questions return no results.

Baseline: 27 of 42 first-place checks passed. Both role sources failed to survive in all three duplicate-export comparison variants. Combined with the retained answer-quality suite, pytest reported 22 failing subtests, 15 passing test methods, and 72 passing subtests. The 22 failures include repeated observations of the same defects. They remain strict rather than being marked expected failures; installing this overlay can make the development suite fail on the current ranker. This is a curated relevance test, not a representative accuracy measurement for the full Archive. The local run used standard-library helper stand-ins, not the official Native API stack. No product code or data was changed.

### Intent-aware follow-up

The same judged matrix now passes all 42 first-place checks, up from 27 on the unchanged fixtures. Both role sources survive all three duplicate-export comparison variants. An answer regression checks that a renewal date is not reported as an expiry date. The focused run passed 101 tests and 94 subtests with local stand-ins for the unavailable Brisart helpers. The official Native API and full-archive run remain outstanding.

### Query-intent classification

Run `python scripts/run_tests.py brisart_ai/knowledge/tests/test_query_intent.py -q` from `Offline_AI`. The table checks both the broad classifier label and the evidence route chosen using production topic extraction. Three temporary-index cases verify that the intended route affects public ranking rather than just setting a label.

The adversarial cases in the same intent test module cover competing cues, explicit negation, agenda-only co-mentions and negated expiry dates. Temporary SQLite tests exercise the normal conversation path and verify that ranking and answer selection reuse one classification.

## What the 1.6.0 results establish

The 1.6.0 judged-query benchmark measures the rank of a known relevant file on a small fixed corpus. Its three insertion orders test whether the same questions return the same first-ranked target despite different import order. The latency figures measure the search call after indexing and should not be extrapolated to large corpora or the complete desktop workflow.

The focused automated suite checks many more behaviors than first-place retrieval, including evidence selection, citations, dependency direction, conflicting claims, and input boundaries. The reported run used local substitutes for unavailable first-party helpers; it is not equivalent to installing the official Native API stack in a Windows environment.

## Interpreting historical evidence

Earlier development entries below document defects, their reproductions, and the tests introduced to prevent recurrence. A failed baseline is useful evidence of why a change was made, but it is not the result of the current release. The newest executed results are presented above the historical sections.

A benchmark is comparable to another only when corpus, queries, relevance judgments, source scope, hardware, environment, and measurement method are sufficiently aligned. The 1.4.0 historical comparison and the 1.6.0 small judged-query benchmark have different workloads and must remain separate.

## Remaining integration checks

Before public distribution, run the full project test runner with the official Native API installation available to spawned workers. On Windows, verify the Tk workspace, file browsing and drag-and-drop fallback, multicore import progress, cancellation, state persistence, and cited answer display.

These checks are still outstanding unless a later entry records their execution. Documentation of an intended test is not evidence that the test passed.
