# Changelog

All notable changes to BrisartAI are documented here, newest release first.

---

## [1.6.0] - 2026-11-26

### Workspace tab selection and library capacity

- `brisart_ai/ui/app.py` now makes the selected Results or Activity tab taller and wider, with the mint accent on its label. The inactive tab uses smaller padding and a muted label. This corrects the visual hierarchy without changing tab content or keyboard navigation.
- `brisart_ai/core/encrypted_library.py` now uses a 5 GiB process-safety ceiling for live encrypted SQLite snapshots and archive reads. The earlier 32 MiB portable backup limit remains separate. The 5 GiB limit is not a promise of low memory use; the current snapshot and archive implementation materializes data in memory.

### Live-library size-limit correction

- Removed the backup subsystem's 32 MiB plaintext snapshot and 40 MiB encrypted-archive caps from the live-library migration path. Those limits were originally defensive bounds for portable backup export and were incorrectly reused by `encrypted_library.py`; they were not a `97_Encryption` failure. Backup verification and recovery retain their existing conservative limits.
- Live migration now passes a separate 5 GiB safety ceiling to SQLite snapshotting and the Official archive reader. The encrypted output is no longer rejected merely for exceeding the old 40 MiB backup cap. A regression test verifies that live migration supplies the live-library limit rather than the legacy 32 MiB backup limit. The currently configured 5 GiB ceiling is a process-safety bound, not an encryption-format limit.

### Encrypted live research library

- `brisart_ai/core/encrypted_library.py` owns migration, automatic unlock, encrypted checkpoints, DPAPI-protected key material and interrupted-migration rollback. The indexed SQLite library, notes and conversation history are encrypted into a `97_Encryption/v4` archive at rest. Original imported files remain unchanged. A private plaintext working copy exists only while BrisartAI is running and is removed on clean shutdown.
- `brisart_ai/ui/app.py` offers migration until accepted, reports an estimate derived from the current database size, shows migration stages, and confirms that future indexed imports are checkpointed into the encrypted container. `BrisartService` invokes the vault checkpoint after questions, imports, note creation and source removal. Existing encrypted libraries are automatically unlocked for the same Windows account through CurrentUser DPAPI.
- Migration publishes and verifies ciphertext before deleting the plaintext database. A marker and recovery copy permit rollback after interruption before the encrypted pair is complete. Two orchestration tests passed with a deterministic authenticated test facade: migration plus a post-migration import survived automatic reopen, and interrupted migration restored the plaintext library. The actual `97_Encryption/v4` implementation, Windows DPAPI, Tk popup and forced-process termination were not executable in this Linux environment and remain release-blocking integration checks.

### Release overview

BrisartAI 1.6.0 advances the Brisart relevance engine beyond the 1.5.0 research workspace and multicore-import baseline. The changes focus on query intent, evidence selection, direct and inferred relationships, date and release scope, citation completeness, contradictions, and honest uncertainty. Recovery remains available for existing experimental encrypted archives. The live index remains unencrypted.

### Manual backup workflow removed

- Removed the startup backup-export prompt and the `backup-create` CLI command. Removed the unused prompt preference from defaults. The archive fixture builder remains used by the recovery regression test; existing `backup-verify` and `backup-restore` commands remain available for previously issued archives.
- The current SQLite library and original files are not changed by this update. Automatic migration, launch unlock and encrypted import persistence are not enabled. Existing imports retain their elapsed-time and remaining-time display.

### Changed modules and rationale

- `brisart_ai/intent.py`: Owns shared intent cues, entity and alias declarations, directional dependency syntax, date normalization, supported paraphrases, and exact release qualifiers. This prevents the ranker and answer formatter from independently interpreting the same question.
- `brisart_ai/knowledge/ranker.py`: Builds a shared query plan, prioritizes passages matching requested evidence, preserves single-side comparison candidates, and deduplicates exact bodies in relevant result sets. Relationship collection admits intermediate links without letting repeated exports monopolize the bounded candidate pool.
- `brisart_ai/knowledge/relevance_engine.py`: Owns evidence grading, answer selection, citation-aware chain assembly, explicit conflicts and uncertainty, calendar-checked date claims, and release-scoped relationship assessment. It distinguishes direct support from inference and declines unsupported conclusions.
- `brisart_ai/knowledge/synthesizer.py` and `brisart_ai/core/conversation.py`: Pass the same query plan through retrieval and format the engine's support statuses, excerpts and citations. The formatter no longer owns independent ranking or claim resolution.
- `brisart_ai/knowledge/tests/`, `brisart_ai/core/tests/`, and `docs/TESTING.md`: Add and document adversarial paraphrases, distractors, ranking judgments, source-scope checks, alias collisions, duplicate-pressure tests, temporal/release conflicts and citation-budget regressions.

### Compatibility and verification

No new third-party runtime package, index schema migration, or reindexing is required. The external Brisart Native API dependency, CLI interface, and per-user saved state remain unchanged. Relationship inference is limited to explicitly evidenced links and a bounded search; support labels are not calibrated probabilities or guarantees of truth. The final focused run passed 174 tests and 189 subtests using local standard-library stand-ins for unavailable Brisart helpers. The full Archive, official Native API stack, and Windows desktop have not been validated end to end.

### Source documentation expansion

- All 60 Python modules, tests and developer utilities received a six-section header review. Each header now contains at least two substantive paragraphs under Purpose; Communication / relationships; Settings / parameters; Edge cases; Known limitations; and Examples. Existing file-specific explanations were retained and supplemented with actual declared entry points, in-tree imports, input ownership, error boundaries and test limitations. This is a documentation-only pass; no executable AST nodes were changed.
- The source tree compiled and the focused retrieval and conversation suite passed 174 tests and 189 subtests with local stand-ins for unavailable Brisart helpers. This does not replace the Windows desktop or official Native API integration checks. No new module, dependency, state format, or index migration was introduced.

### 1.6.0 benchmark follow-up

- `docs/TESTING.md` now records a fresh 1.6.0 judged relevance and search-latency benchmark on 14 curated queries in three index orders (42/42 top-1 judgments), together with the exact local test outcomes and their dependency limits. An initial spawned-worker failure was traced to the temporary test harness invoking pytest during child-process import; after correcting its `__main__` guard, the broader selected suite passed 174 tests and 189 subtests. No runtime files, test expectations, index data or version identifiers changed in this documentation pass.

### Header and folder documentation cleanup

- Replaced unnecessary raw-string prefixes on 37 module docstrings with conventional triple-quoted headers while preserving the exact interpreted documentation text, including escaped backslashes where necessary. The executable AST was unchanged.
- Updated all seven existing folder README headings to match their containing folders: BrisartAI, Core, IO, Knowledge, UI, Docs, and Scripts. Each now begins with a folder-specific responsibility description before existing details. The six-section source headers and 1.6.0 benchmark record remain intact.

### Markdown documentation organization

- Rewrote the five application-package and developer-script folder READMEs around their actual directory responsibilities. Removed the misplaced desktop-module inventory from `brisart_ai/README.md`, removed repeated unheaded retrieval and import notes from the Knowledge README, and organized UI, IO, Core and Scripts documentation by component and boundary. No folder README describes another folder as its own contents.
- `docs/README.md` now separates the documentation inventory, application overview, launch instructions, source workflow and state handling. `docs/ARCHITECTURE.md` labels runtime ownership and data flow; `docs/SECURITY.md` separates confidentiality, retention, parser trust and reporting. `docs/TESTING.md` distinguishes the 1.6.0 benchmark from historical 1.4.0 measurements and development regression history. Detailed release and benchmark evidence was retained rather than relocated into new files.
- The pass changed only Markdown documentation. Python compilation and ZIP integrity were checked; the earlier 1.6.0 test and benchmark results remain historical records, not tests rerun during this edit.

### Expanded documentation and operational guidance

- Expanded the existing folder READMEs with detailed descriptions of the actual modules, dependency direction, runtime boundaries, and practical development workflows. Each folder document remains scoped to its own directory rather than repeating unrelated project history.
- Expanded the user guide, architecture, security, and testing documents with distinct sections on evidence interpretation, import lifecycle, concurrency, state handling, local-data protection, benchmark methodology, and outstanding integration checks. The historical changelog was retained without padding individual release entries with duplicate claims.
- This is a documentation-only pass. It changes no executable code, persisted data, dependencies, or release version. Existing test results remain historical evidence and are not presented as newly executed checks.

### Retrieval-engine engineering history

The entries below are organized by the subsystem or defect addressed during development. They preserve the reasons and test evidence for each change; the release overview above is the concise summary.

#### Detailed engineering changes

#### Answer-quality follow-up

- `knowledge/ranker.py` separates the subject from terminal method framing such as work, operate and function in explicit how-questions. The same shared topic extraction feeds retrieval and excerpt selection.
- `knowledge/synthesizer.py` prefers mechanism evidence and retains one adjacent supporting sentence within the same paragraph. Two-concept comparisons prefer direct contrast; absent that, they surface separate cited role evidence or identify the missing side instead of using name lists as answers. These bounded text heuristics do not validate scientific claims or handle all comparison wordings.
- `core/tests/test_answer_quality_reports.py` replays the reported questions and wording, order, and missing-evidence variations. The focused run passed 95 tests and 32 subtests with standard-library helper stand-ins; the official Native API and real archive were not validated in that run. No dependency, index schema, settings, or data migration changes.

### Raw search relevance tests

- `knowledge/tests/test_search_quality.py` adds judged raw-ranker checks for paraphrases, distractors, ingest-order sensitivity, repeated searches, scope, and comparison evidence crowded out by context exports. `docs/TESTING.md` records how to rerun the strict gate and interpret the baseline. This test-only pass changes no ranking behavior, runtime dependencies, or persisted state.

### Intent-aware evidence

- `brisart_ai/intent.py` owns shared evidence rules for mechanism questions, two-topic comparisons, and explicit deadline or expiry questions. Unrecognized queries keep the existing ranking path.
- `knowledge/ranker.py` prioritizes passages that match the requested evidence shape within the existing bounded candidate pool. Separate role evidence can outrank co-mentions. Adjacent date language can help surface a document without certifying an answer.
- `knowledge/synthesizer.py` uses the same rules, preserves missing-side warnings, and does not substitute renewal deadlines for expiration dates. This is bounded interpretation of wording, not general language understanding.
- The unchanged raw relevance gate went from 27 to 42 first-place checks passing; the focused run passed 101 tests and 94 subtests using local-only helper stand-ins. No index rebuild, runtime dependency, or settings changes.

### Brisart retrieval engine ownership and comparison ranking

- `knowledge/relevance_engine.py` now owns excerpt selection, evidence limits, and support status. `knowledge/synthesizer.py` renders those decisions as citations and evidence warnings rather than independently selecting passages. Query intent stays in `intent.py` and document ranking stays in `knowledge/ranker.py`.
- `knowledge/ranker.py` gives a bounded number of single-side candidates a chance to be graded when co-mentions fill the initial comparison pool. Exact duplicate bodies within the same source type no longer consume multiple comparison result slots. The highest-ranked copy keeps its original citation; no indexed file is changed. Near-duplicates and evidence beyond the bounded pool can still be missed.
- The focused suite passed 103 tests and 94 subtests with local stand-ins for the unavailable Brisart helpers, including the unchanged first-place matrix and new comparison tests with 60 agenda exports and duplicate direct contrasts. Native API and full-archive validation remain outstanding. No UI, import, state, dependency, or schema changes.

### Query-intent classification tests

- `knowledge/tests/test_query_intent.py` adds 22 classification and evidence-route cases plus three real SQLite ranking cases. It checks paraphrases, intent precedence, unsupported comparison shapes and neutral fallback. The ranking cases verify that mechanism, comparison and deadline evidence beat a distractor titled with the full question.
- The focused run passed 47 tests and 119 subtests using local stand-ins for the unavailable Brisart helpers; the official Native API stack was not exercised. This is a test-only change with no new dependencies or index changes.

### Shared retrieval query plan and adversarial intent checks

- `knowledge/ranker.py` prepares one query plan with original text, topic groups, intent, and evidence mode. `core/conversation.py` passes that plan to scoped search and answer rendering. `knowledge/relevance_engine.py` uses it for excerpt selection, including accepted spelling corrections. The synthesizer formats engine decisions and citations rather than independently classifying the question. Direct string search callers still use the same plan builder.
- `intent.py` shares complete how-it-works framing with topic extraction, respects bounded explicit comparison negations, and rejects common agenda and negated-deadline distractors as direct evidence. Short explicit expiry statements remain eligible. These are bounded English rules, not general negation or contradiction resolution.
- `knowledge/tests/test_query_intent.py` adds ten intent cases and two temporary SQLite scenarios. Both scenarios verify insufficient evidence, first-place ranking with real support present, citation selection, and one classifier call through the production conversation path. The focused run passed 158 tests and 137 subtests with local stand-ins for the unavailable Brisart helpers; official Native API and full-archive validation remain outstanding. No new dependencies, settings changes, or index rebuild.

### One owner for ranking and answer evidence

- `knowledge/relevance_engine.py` now owns best-passage selection and the direct-evidence grade reused for answer excerpts. Direct expiry evidence outranks renewal context; a nearby date may still help surface a related document without being quoted as the answer. In the new one-result SQLite replay, the previous build ranked the renewal notice first; the updated build ranks and cites the actual expiry notice.
- `knowledge/ranker.py` retains query planning, candidate retrieval, and document ordering. `knowledge/synthesizer.py` renders evidence and citations; its unused intent wrappers and scoring re-exports were removed after checking in-tree callers. Passage-scoring tests moved to the evidence-engine suite, and redundant wrapper tests were removed. Touched source headers were updated in the six-section format. No new modules or dependencies.
- The focused run passed 155 tests and 137 subtests with local stand-ins for the unavailable Brisart helpers. No CLI, UI, index schema, settings, or state migrations changed. Full Archive and official Native API validation remain outstanding.

### Date evidence by requested event

- `brisart_ai/intent.py` distinguishes expiry, renewal deadlines, and application or submission deadlines. It recognizes day-first, month-first, and ISO-style dates, preserves source wording, and requires a deadline cue for renewal and submission. A related date is not a substitute for the requested event. These English rules recognize date shapes; they do not validate the calendar, infer relative dates, or resolve conflicts between sources.
- `knowledge/relevance_engine.py` assesses direct and contextual deadline evidence in one passage pass and reuses the paragraph splitter for excerpt selection. The intent module owns lexical cues; the engine owns how those cues affect ranking and citation. The adjacent ranker and formatter still delegate evidence decisions; no new module or parallel search path was needed. Touched Python headers use the six-section format.
- Four temporary-SQLite cases in `knowledge/tests/test_query_intent.py` check distractor-only abstention, first-place ranking with a one-result limit, and the final citation. The focused run passed 156 tests and 141 subtests using local stand-ins for the unavailable Brisart helpers; Native API and full-archive validation remain outstanding. No dependency, CLI, settings, or index schema changes.

### Named entities and direct dependency evidence

- `brisart_ai/intent.py` recognizes direct English dependency questions with two named entities, or with one entity left to identify. It matches complete endpoint names (ignoring case, whitespace, and a leading “the”), checks direction in active and passive statements, and allows explicit negative statements only for a named-pair question. It does not resolve aliases, infer links from co-mentions, follow transitive chains, resolve conflicting sources, or provide an exhaustive dependency inventory.
- `knowledge/ranker.py` stores the ordered names in the existing query plan and searches their terms, not question framing. `knowledge/relevance_engine.py` applies the same direct evidence grade for ranking and cited excerpts. Related sources can still appear in search; when no direct statement is available the answer abstains. The formatter and storage retain their existing roles. No new files, graph, runtime dependencies, or index changes; removed an unused query local and refreshed affected source headers.
- `knowledge/tests/test_query_intent.py` covers forward, reverse, and passive wording; co-mentions, reversed dependencies, similar names and speculative statements; source-scope preservation; and explicit negatives. The SQLite replays require direct evidence to win with one result slot and be cited correctly. The focused run passed 158 tests and 145 subtests with standard-library stand-ins for the unavailable Brisart helpers; official Native API and full-archive validation remain outstanding.

### Cited aliases, dependency chains, and disagreements

- `brisart_ai/intent.py` owns explicit alias and directional dependency syntax. It recognizes `aka`, `is also known as`, and `is abbreviated as`, adds `rely on` wording, and reuses the same statement parser for ranking and aggregation. Aliases are never guessed from initials. Recognized forms are bounded English statements, not general entity extraction.
- `knowledge/ranker.py` gathers relationship candidates from existing scoped token postings. Up to 256 cue-bearing documents are considered, with query-name matches prioritized and room for documents that only supply an intermediate link; documents over 262,144 characters are skipped. This is a bounded evidence pool, not an exhaustive audit. Ordinary ranked search retains its existing interface and direct evidence ranking.
- `knowledge/relevance_engine.py` aggregates one representative citation per claim and polarity. It cites the declaration when a unique alias is used and shows competing declarations for an ambiguous queried alias instead of merging entities. Direct support outranks inference; otherwise it can show the shortest supported chain of up to three links. Disputed links cannot support a chain. A direct denial alongside an indirect chain is shown separately from a contradiction between direct claims. Open-ended questions can show multiple direct dependencies without counting copies as votes. No partial proof is rendered for a chain or conflict when citation limits are too small.
- `core/conversation.py` passes one plan and scope into retrieval and no longer fetches unused topic history. `knowledge/synthesizer.py` renders evidence statuses and citations without resolving disagreements. Reviewed the adjacent storage and query boundaries, removed the obsolete boolean-only relationship matcher, and updated the touched six-section headers. No new modules, persisted graph, dependency, schema, settings, or reindexing requirements.
- `knowledge/tests/test_query_intent.py` exercises SQLite evidence assembly with an endpoint-free middle link, missing and disputed links, cycles, direct conflicts, duplicate sources, aliases and alias collisions, scope, and tight citation limits. The focused run passed 159 tests and 155 subtests with standard-library stand-ins for unavailable Brisart helpers; the official Native API stack and full Archive were not exercised.

### Date- and release-scoped relationship evidence

- `brisart_ai/intent.py` parses comma-delimited `As of YYYY-MM-DD,` and `In version 1.2.3,` dependency-query prefixes. Evidence can declare its date with `On YYYY-MM-DD,` or an inclusive `From YYYY-MM-DD through YYYY-MM-DD,` interval and its exact release with `In version 1.2.3,`. Both dimensions may be combined. Dates are calendar-checked; the engine does not infer a release from filenames or a date from import timestamps. Versions are exact labels with optional `v`, not version ranges or latest-release selection.
- `knowledge/relevance_engine.py` applies one qualifier check to relationship ranking and to each cited claim, alias declaration, and inferred link. It compares claims within the same requested scope, not across dates or releases. Unqualified claims are only used for unqualified queries. Existing three-link and citation limits remain in effect. `knowledge/synthesizer.py` renders invalid qualifiers separately from insufficient evidence when evidence documents were retrieved; the unused internal `recent_topics` argument was removed after checking callers.
- `knowledge/ranker.py` deduplicates exact scoped document bodies before taking the bounded 256-candidate set. It still prioritizes endpoint overlap using Brisart postings and leaves originals untouched. SQLite handles storage and grouping, not relevance scoring. The six reviewed retrieval and adjacent support modules imported only standard-library and first-party Brisart code; external ranking comparators remain isolated in optional benchmark tooling and were not part of the engine. Touched source headers were reviewed; no new module, runtime dependency, or index migration.
- `knowledge/tests/test_query_intent.py` adds a temporary-index replay with 800 identical exports, 120 distinct distractors and another 300 duplicate support claims. The previous build missed the three-link chain on that fixture; the updated build cites it, blocks a disputed middle link, and retains both sides of a direct conflict. Additional cases exercise date windows, exact releases, invalid dates and incompatible chain links. The focused run passed 161 tests and 162 subtests using local helper stand-ins. This is not a full-archive throughput benchmark or an official Native API validation.

### Citation-aware dependency proofs

- `knowledge/relevance_engine.py` replaces first-path inference with selection of the shortest complete proof that fits the citation budget among the collected claims. Within the same hop count it prefers fewer sources, then fewer excerpts. Reverse reachability skips branches that cannot reach the requested target within three links. The old forward global visited set is gone; it could discard alternative paths with different citation costs. Ambiguous or unresolved alias declarations cannot bridge an inferred chain. Direct conflicts, scoped claims, and the requirement to cite all parts of an inference are unchanged.
- `knowledge/tests/test_query_intent.py` verifies that a self-contained three-link proof wins when a shorter proof cannot fit, that the shorter path wins when space permits, and that an alias collision cannot fabricate a bridge. Both regressions failed against the incoming build. The focused run passed 163 tests and 162 subtests using local stand-ins for the unavailable Brisart helpers; this is not a competitor benchmark or full Archive/Native API validation.
- Reviewed the neighboring ranker and synthesizer: candidate collection and citation rendering retain distinct runtime roles. Proof policy lives in the existing evidence engine, with refreshed six-section headers and no new modules, compatibility paths, runtime dependencies, or index changes. The search remains bounded to the collected evidence and one representative proof per claim and polarity, so it is not an exhaustive search over all possible citation combinations.

### Dependency lists that preserve disagreements

- `knowledge/relevance_engine.py` replaces the first-dispute early return for open-ended dependency questions with evidence-group selection. It reserves citation space for complete disputes, then adds other supported links that fit. Both polarities of a dispute are indivisible. If a dispute does not fit, the answer can still cite other supported links, with an explicit omission notice. If nothing fits, it reports the limit without presenting a one-sided conclusion. This is a bounded list, not an exhaustive dependency audit.
- `knowledge/synthesizer.py` renders the engine's distinct list statuses without adding its own selection rules. Reviewed the adjacent ranker, formatter, and test roles: candidate collection and rendering remain separate, and SQLite postings and chain inference are unchanged. Removed the obsolete first-conflict-only branch; refreshed touched six-section headers. No new files, dependencies, settings, or index changes.
- `knowledge/tests/test_query_intent.py` exercises forward and reverse dependency lists with real temporary SQLite indexes, both sides of a dispute, a duplicate source, and tight citation limits. Both mixed-list cases failed on the incoming build and pass here. The focused run passed 165 tests and 164 subtests using local stand-ins for the unavailable Brisart helpers; this does not establish full-Archive or official Native API compatibility.

### Evidence quality and answer confidence

- `knowledge/relevance_engine.py` owns the ordinal result grade (0: no matching body evidence; 1: contextual, partial, or tentative; 2: full topical coverage; 3: direct intent evidence) and answer support labels. Neither is a calibrated probability or a measure of source reliability. `knowledge/ranker.py` exposes `evidence_quality` separately from the existing result score. `knowledge/synthesizer.py` renders the labels and citations without grading evidence itself.
- Date answers prefer explicit dates over tentative statements and preserve tentative wording when it is the only support. Otherwise identical explicit statements with different single ISO dates are shown as conflicting, not arbitrarily resolved. `core/conversation.py` separates bounded date candidate retrieval from the visible citation budget; if opposing dates cannot both be shown, neither is presented as settled. The ranker reuses its exact-body result deduplication for date searches within each source type. This does not detect every contradiction, including differently worded claims or evidence outside the candidate pool.
- Missing event-specific evidence is distinguished from a tentative answer. Existing dependency disputes and inferred chains use the same answer confidence labels. The SQLite replay in `knowledge/tests/test_query_intent.py` covers missing and tentative evidence, ordinal grades, duplicate pressure, conflicting dates, and a one-citation budget. The focused run passed 166 tests and 164 subtests with local stand-ins for the unavailable Brisart helpers; official Native API and full-Archive validation were not performed.
- Reviewed touched and adjacent retrieval roles and six-section source headers. Reused the current ranker, evidence selector, formatter, and test fixture; no new module, dependency, settings, or index changes.

### Calendar-checked date evidence and cross-format disagreements

- `brisart_ai/intent.py` now owns date recognition and calendar validation for ISO and English month-name dates. It preserves source spans and leaves missing years unknown. Impossible dates such as February 30 cannot qualify as direct deadline evidence.
- `knowledge/relevance_engine.py` replaces its ISO-only comparison with grouped, normalized date claims across the retrieved evidence. It compares firm single-date statements with matching wording and year scope, quotes both original passages when they disagree, and does not mistake equivalent formats or different explicit years for disagreement. This does not resolve paraphrased claims, ambiguous numeric dates, or conflicts outside the existing candidate budget.
- `knowledge/tests/test_query_intent.py` exercises SQLite answers across formats, disputed statements beyond the first candidate, and impossible dates. Four assertions failed against the incoming build; the updated focused suite passed 169 tests and 169 subtests with local stand-ins for unavailable Brisart helpers. The official Native API stack and full Archive were not exercised.
- Reviewed touched and adjacent retrieval roles and file necessity. Date parsing remains in the existing intent module, evidence grouping remains in the relevance engine, and the ranker and formatter retain their existing roles. Removed the superseded ISO-only matcher, refreshed affected six-section headers, and added no modules, runtime dependencies, settings changes, or index migrations.

### Paraphrase-aware date conflicts

- `brisart_ai/intent.py` normalizes supported full-statement forms for expiry, renewal, and submission deadlines to an event and subject key. Subject modifiers remain significant; unrecognized wording retains the previous literal comparison. It does not infer aliases, remove conditions, or guess years.
- `knowledge/relevance_engine.py` replaces inline wording-key construction with the intent-owned key. The engine retains year scope, firm single-date checks, and citation budgeting. It quotes both original passages when comparable values disagree, and flags disagreement without choosing either date when both cannot be cited. The ranker and formatter still own collection and presentation respectively; neither needs a new path or duplicate parser.
- `knowledge/tests/test_query_intent.py` uses temporary SQLite indexes to check cross-wording disagreement, equivalence, different subjects and events, different years, qualified or tentative notices, and a one-citation budget. The baseline missed all three initially tested paraphrased conflicts. The focused run passed 170 tests and 179 subtests with local stand-ins for unavailable Brisart helpers; official Native API and full-Archive validation remain outstanding.
- Reviewed touched and adjacent file roles and six-section headers. The change replaces duplicated literal-key assembly with one intent-owned implementation without adding files, dependencies, settings, or index changes.

### Paraphrased dependency-date conflicts

- `brisart_ai/intent.py` recognizes explicit dependency start and end questions and matching active and passive claims. It also recognizes positive and negative `is a dependency of` wording for state questions. Relationship qualifiers reuse calendar validation and support ISO and English month-name dates with an explicit year. Removes the redundant ISO-only qualifier matcher.
- `knowledge/ranker.py` carries the requested lifecycle event in the existing query plan and still collects scoped candidates through the existing index. `knowledge/relevance_engine.py` compares firm transition dates for the same ordered pair, event, release and year scope, using existing cited aliases. Different year scopes are shown separately when citations fit. As-of state queries retain inclusive interval checks; lifecycle claims are not inferred from a snapshot, nor used to extrapolate dependency state. Repeated start/end cycles within a year are not distinguished automatically.
- `knowledge/synthesizer.py` reuses date-conflict presentation and distinguishes separate year scopes. Original evidence is preserved, and comparisons that cannot fit all necessary citations do not show one date as settled. The change stays within dependency statements, not arbitrary relation types or unrestricted paraphrases.
- Temporary SQLite cases in `knowledge/tests/test_query_intent.py` cover active/passive conflicts, equivalent dates, separate start/end events, direction, release isolation, yearless and invalid dates, one-citation limits and overlapping intervals across formats. The focused run passed 172 tests and 186 subtests with local stand-ins for the unavailable Brisart helpers; this was not a Native API or full Archive run. Reviewed adjacent conversation and index ownership and retained the existing file boundaries. No new files, dependencies, settings or index changes.

### Paraphrased versioned dependency conflicts

- `brisart_ai/intent.py` accepts explicit `in version` and `for release` qualifiers before or after a relationship statement or question, recognizes passive dependency questions, and maps dependent, independent and no-longer-required wording to the same directed edge and its polarity. `v1.2` and `1.2` share a scope, but `1.2.0` is distinct. As-of date and exact-release checks both still apply. The parser does not resolve latest releases, version ranges or prerelease labels.
- `knowledge/relevance_engine.py` reuses its conflict status policy when evidence exceeds the citation budget. `knowledge/synthesizer.py` renders the conflict without selecting one side when both cannot be cited. The existing query planner, source scope, postings and state storage remain unchanged; no parallel version parser or new module was needed. Reviewed affected and adjacent file roles and refreshed the touched six-section source headers.
- Two temporary-SQLite regressions in `knowledge/tests/test_query_intent.py` failed on the previous build. They now cover ranking, original citations, exact release/date isolation, reversed edges, duplicate qualifiers, malformed release labels and one-citation conflict handling. The focused run passed 174 tests and 189 subtests with local stand-ins for unavailable Brisart helpers; the official Native API stack and full Archive were not exercised. No new dependencies, settings or index changes.

## [1.5.0] - 2026-11-26

Research workspace, import hardening, and multicore processing.

### Release overview

BrisartAI now puts the local library, search scope, and evidence ahead of the transcript. Bulk imports use separate worker processes for file preparation without adding a setting or changing how the index is written.

### Changed

- `brisart_ai/ui/app.py`, `sidebar.py`, and `theme.py`: The library rail groups source and note actions with indexed counts. The workspace header holds Search settings and Help; the active scope stays visible while search and shutdown progress appear separately. A dark mineral palette with a muted mint accent makes the primary actions easier to pick out.
- `brisart_ai/ui/chat_panel.py`: The query composer sits above **Results** and **Activity**. Results holds questions, answers, and cited evidence; Activity holds imports, note saves, and search diagnostics.
- `brisart_ai/knowledge/ingest.py`: Desktop and CLI bulk imports detect available logical CPUs and use spawned processes to read, parse, and hash independent files. Worker count is limited by the work available and, on Windows, by the 61-worker executor limit. Single-file and single-core imports run directly. Work in flight is bounded, and the caller writes to SQLite in discovery order. If the pool becomes unavailable, remaining files run serially without replaying completed index writes.
- `docs/README.md` and the UI and knowledge folder READMEs explain the revised workflow and ownership. The redundant root README was removed, leaving only `run.py`, `cli.py`, and `version.py` at the project root.

### Fixed

- `brisart_ai/ui/chat_panel.py` gives the query controls layout priority in short windows and preserves drafts when a submission is rejected.
- `brisart_ai/ui/app.py` preserves the draft if the search worker cannot start, prevents Ctrl+L from stealing focus from a modal dialog, and destroys the window even if final service cleanup raises.
- `brisart_ai/io/binary_readers.py` sorts numbered PowerPoint parts numerically within slides and notes, so slide 10 no longer precedes slide 2. PDF extraction now reads only its requested raw-byte budget instead of reading the whole file before slicing it.

### Security

- `brisart_ai/io/binary_readers.py` bounds selected Office and OpenDocument XML to 16 MiB per member, 64 MiB total, and 2,048 members. Packages exceeding any budget yield no extracted text.
- The XML parser rejects DTD declarations, including in UTF-16 input. This is not a parser sandbox. The PDF raw-byte limit does not bound decompressed PDF streams.

### Compatibility and testing

No index rebuild or schema change is required. The CLI interface, external Native API arrangement, and `%APPDATA%` state path are unchanged. SQLite writes and individual query ranking remain serial. No import speedup has been benchmarked.

The workspace and hardening pass compiled and passed 35 focused tests, including the XML budgets, UTF-16 DTD rejection, numeric slide ordering, and bounded PDF reads. The multicore pass separately passed 24 focused tests, including a test with two real spawned processes working concurrently, caller-only index writes in discovery order, and serial recovery after pool failure. The combined 1.5.0 package compiled and passed 40 focused tests and 9 subtests. The Tk workspace module was skipped and three Native API-dependent cases were excluded because their dependencies were unavailable. These checks do not constitute an end-to-end Windows run. The Windows desktop smoke test and full integration suite against the official Native API stack remain outstanding.

### Import and query timing follow-up

- `ui/dialogs.py` and `ui/import_progress.py` show elapsed time during discovery, then a filling bar with percent, processed and remaining files, indexed count, and a throughput-based ETA. Empty folders have no ETA; the completed result stays visible. Skipped and failed files advance processed progress but not the indexed count.
- `ui/app.py` runs imports off the Tk event loop and gives them exclusive access to the service until completion. Its status line also shows elapsed time during query execution.
- `core/service.py` and `knowledge/ingest.py` forward real progress from discovery and indexing. Multicore file preparation and ordered single-writer SQLite behavior are unchanged. CLI output and the existing index and settings format are unchanged.
- The timing build compiled and passed 45 focused tests and 9 subtests, covering ETA formatting, file accounting when reads or writes fail, and ordered progress with real spawned workers. Tk and the official Native API stack were unavailable; the live Windows dialog and native integration remain unverified.

### Cancel an import without closing BrisartAI

- `ui/app.py` and `ui/dialogs.py` show **Cancel Import** during an active batch. **No** is the default and continues the import. **Yes** stops the batch after the current file, preserves prior index writes, and keeps BrisartAI open. Closing a window during import invokes the same cancel-only prompt.
- `ui/dialogs.py`, `ui/import_progress.py`, and `ui/app.py` switch to a stopping state when cancellation is confirmed: the bar, percentage, and ETA disappear, even if a worker sends late progress. The dialog labels the displayed paths as the original selection, explains that safe cleanup can take time, and reports the final indexed count once stopped. BrisartAI stays open, and the selection is available for retry. This follow-up compiled and passed 19 focused tests and 6 subtests; live Windows rendering was not tested.
- `io/readers.py`, `knowledge/ingest.py`, and `core/service.py` retain cooperative cancellation: discovery stops between entries and dispatched preparations drain without adding later files to SQLite. There are no index, settings, or CLI changes.

- The cancel-only build compiled and passed 49 focused tests and 9 subtests. The live Windows prompt and Native API integration remain unverified.

## [1.4.0] - 2026-11-25

### Release overview

BrisartAI 1.4.0 improves offline retrieval, adds bounded typo recovery, and gives the desktop clearer library actions and search status. Brisart owns candidate selection, ranking and cited evidence; SQLite remains storage.

### Changed

- `knowledge/ranker.py` uses the existing SQLite postings for candidate retrieval. It groups selected English variants (such as expire/expiry and renew/renewal), drops question framing when a topic remains, and prioritizes how many distinct concepts occur together in the strongest body passage. Intent, title, phrase and document scores break ties within that coverage tier.
- `knowledge/relevance_engine.py` supplies the shared passage splitter and concept matcher. It retains short lines, covers long unpunctuated text with overlapping windows, and walks sorted positions rather than testing every pair for proximity.
- `knowledge/synthesizer.py` favors broader topic coverage over repeated words or generic comparison, causal and quantity cues. It suppresses weaker excerpts when stronger coverage is available, caps excerpts before spending the overall answer budget, and labels partial coverage.

### Fixed

- Explicit empty source scopes no longer fall through to unrestricted search, and phrase boosts respect word boundaries. Regression tests cover buried passages, scattered keyword decoys, compound terms, short cited answers, partial matches and comparison distractors.

### Follow-up retrieval passes

- `knowledge/relevance_engine.py` reuses tokenized passages from a bounded in-memory cache for short documents, with longer documents streamed without caching. A per-query term lookup counts matched concepts for both ranking and excerpts without re-tokenizing cached passages. The cache changes no persistent data.
- `knowledge/ranker.py` prefers an exact, case-sensitive Python declaration or assignment over a mere mention when searching for a code-style identifier. The lexical shortlist still applies.
- Passage extraction keeps short colon-ended field labels together with adjacent numeric or yes/no values. This prevents citations like “Permit fee:” from dropping the amount on the next line. Regression tests cover declaration-versus-mention ranking and split field values.
- On the same 63-file, 20-question Linux benchmark with network syscalls blocked, median warm search time went from 131.7 ms to 52.4 ms. Correct first results increased from 9 to 10; top-five and top-ten results stayed at 18 and 20. These are follow-up measurements on the existing corpus, not independent relevance or Windows performance results.
- The updated headless suite passed 278 tests and 7 subtests; all 4 offline replay checks passed.

### Unified Brisart retrieval

- The Brisart engine is the single content-retrieval path. Notes now use its relevance order and matching passage previews instead of substring counts. Collections and timeline lookups use the same query concepts and postings, without changing the timeline's chronological display. Historical web entries are not considered by these vault lookups.
- The ranker fetches variants in bounded SQL batches and skips document-length work when there are no matching postings. SQLite stores and fetches records from ordinary tables; it does not run FTS or decide relevance. No BM25 library, TF-IDF package, embeddings, model or network service is used at runtime.
- The retrieval changes require no schema, settings or dependency additions. Existing indexes remain usable. Source-management filename filters remain simple UI filters, not full-text search.

- Verified 280 tests, 7 subtests and all four offline replay cases. The network-blocked 20-question benchmark kept the complete previous top-ten ordering for every query (10 first-place hits, 20 top-ten hits; 47.8 ms median warm query on this run). This verifies document ranking continuity, not note preview quality on a real library.

### Desktop and reliability
- `ui/sidebar.py`, `ui/theme.py` and `ui/app.py` group library and preference controls, distinguish the import action, show local file and note counts, and identify the active search scope. Help opens outside the transcript; Ctrl+L focuses the question and F1 opens Help.
- `ui/chat_panel.py` retains draft text when Enter is pressed during a search. `ui/app.py` passes worker results through a queue so workers do not call Tk; the main loop controls the busy state and defers closing until the answer finishes.
- `ui/dialogs.py` adds scrolling for long source lists and paths, Escape to close, and checkbox rollback with an error message when settings cannot be saved.
- `core/settings.py` accepts malformed or non-object JSON safely, replaces the settings file atomically, and restores the prior toggle after failed writes. `core/session_memory.py` resolves equal timestamps using insertion order.
- `util.py` honors the read limit before decoding and recognizes BOM-marked UTF-8 and UTF-16 for local text imports. Other legacy encodings are not guessed. Previously misdecoded files need reimporting to benefit.
### Retrieval refinements and testing
- `knowledge/ranker.py` now recovers a unique one-edit spelling neighbor for unmatched alphabetic terms in eligible sources. It keeps the first two letters fixed and skips ambiguous, oversized or unsupported cases. `knowledge/synthesizer.py` and `knowledge/vault.py` use the recovered forms for excerpts. Conversation answers disclose recovered spellings.
- `knowledge/ranker.py` caches one scope's document lengths per index connection and refreshes after local writes or commits by another connection. The index schema and scoring formula are unchanged.
- Added seven regression tests. The Linux headless application suite passed 287 tests and 7 subtests; all four replay fixtures passed. Tests used the supplied Brisart URL code and temporary standard-library stand-ins for missing Native APIs. Those stand-ins are not shipped and this run does not establish Official Native API parity.

- `scripts/benchmark_retrieval.py` compared six configurations across 270 queries with network access blocked. Correct first results increased from 220 to 244 against the attached sibling baseline; see `docs/TESTING.md` for full comparisons, limits and reproducibility.

### Documentation and dependency cleanup
- Expanded all 53 Python module, test and developer-tool headers into substantial, file-specific six-section documentation. Complex retrieval and service modules now describe their actual public operations, function signatures, dependency direction, matching behavior, error boundaries and regression coverage. Smaller files explain their real responsibilities without inventing unrelated features.
- The documentation audit retained executable Python unchanged. The 1.4.0 headless suite passed 281 tests and 5 subtests, and all four offline replay fixtures passed with the five supplied external Brisart helpers. The benchmark was not rerun because ranking code did not change.

- Reviewed all Python sources, tests and tools, and standardized file-specific headers in the required six-section order. Consolidated duplicate root and package READMEs into source headers and the product guide. Kept architecture ownership, operational security, reproducible benchmark evidence and release history as separate references with distinct purposes.
- `brisart_ai/native_path.py` now requires only the five helpers used by the offline app. Removed codec and robots from startup validation; existing seven-module Official folders still work. Added a regression check for discovery with only the five used helpers.
- Removed theme constant-format assertions while retaining the Tk-free dependency test. The Linux suite passed 281 tests and 5 subtests; all four offline replay cases passed using the five supplied Brisart helpers, without stand-ins. The Windows desktop and Explorer drop remain unverified. The historical benchmark was not rerun.
- No schema, index, ranking, file-format or settings migration changes. Version remains 1.4.0.

### Compatibility and limits
Existing SQLite indexes and settings remain usable without a schema migration or reindex. Keep the external Official Native API folder and the existing per-user data. Live Tk, Windows keyboard/layout behavior and Explorer drag-and-drop were not exercised. No auto-update or publication was performed.
---

## [1.3.0] - 2026-11-25

### Release overview

This release unifies source imports and adds notes with quoted evidence. BrisartAI now answers exclusively from imported files and saved research notes. Internet search, provider calls, crawling and automatic web fallback have been removed rather than merely disabled.

### Changed

- **Unified imports:** `ui/app.py`, `ui/sidebar.py` and `ui/dialogs.py` replace separate sidebar actions with **Add Sources**. Browse for multiple files, pick whole folders, or drop them from Explorer into one reviewable queue. Folder imports remain recursive. The dialog skips unsupported or unavailable paths, deduplicates queued paths and lets users remove items before importing. `ui/windows_drop.py` bridges local Windows shell events to the queue without another Python package. Browse works without the drop bridge.
- **Source notes:** `core/service.py` and `knowledge/index.py` supply indexed text to the note composer and verify that an attached passage actually occurs in the selected file. The note stores the excerpt, original title and path, and separately labeled observations. Existing plain notes continue working. Removing the original source does not remove a note's saved excerpt; remove the note separately if the excerpt must also be discarded.
- **Remove Sources search and selection:** Added live, case-insensitive filtering across source type, title and location; Ctrl/Shift-click multiple selection and Ctrl+A for all visible rows. Confirmations show the number selected. Only matching visible rows are selected by Ctrl+A.
- **Supported imports:** Browse Files uses the reader registry, including supported extensionless names. Existing regression coverage checks multi-file and nested-folder ingestion and unsupported-file filtering.
- `core/conversation.py` and `core/service.py` use only eligible `file` and `note` sources. Empty source selection returns no evidence instead of accidentally searching all types.
- `core/settings.py` and the desktop settings dialog expose only the two local evidence toggles. The obsolete automatic-web setting is ignored when loading older settings files.
- `cli.py` no longer accepts `research` or `ask --web`. The desktop no longer offers Research Web.
- Folder and project documentation now describe the local-only architecture.

### Fixed

- Closing the desktop during an answer now waits for the worker to finish before closing SQLite. Source and settings dialogs are modal, and they cannot open while an answer is running. A second question no longer appears in the transcript as if it was accepted while the worker is busy.
- **Remove Sources** commits a selection as one transaction instead of leaving a partially removed batch after a failure. Duplicate and stale IDs are skipped, dependent index rows are cleared, and original files remain untouched.
- Headless verification: 269 application tests, 7 subtests and 4 offline replay cases passed. New regression checks cover excerpt provenance, rejection of stale or mismatched excerpts, note retention after source removal, and rollback on batch failure. Windows Explorer drops and the live Tk desktop were not exercised.

### Removed

- The complete `brisart_ai/web/` implementation and its provider, crawler and fetch tests.
- The live-search replay script and obsolete web-only blocklist and startup purge behavior.

### Compatibility and limits

Historical `web` records remain in existing SQLite databases and may still be counted, but are excluded from answers. No database deletion or schema migration is performed. The external Official Native API dependency and `%APPDATA%` storage remain unchanged. Windows GUI launch and live network behavior are not tested in this environment.

---

## [1.2.0] - 2026-11-24

### Release overview

BrisartAI 1.2.0 keeps only `run.py`, `cli.py` and `version.py` at the project root, moves saved data to per-user storage, and requires all seven native modules to be loaded from outside Offline_AI. The index schema, settings format, ranking, synthesis and optional web research are unchanged.

- **Root layout.** Every other file is now in a folder: `native_path.py` moved into `brisart_ai/`, the test runner is `scripts/run_tests.py`, the project overview is `docs/README.md`, and the `data/` folder is gone. No `__init__.py` exists anywhere, and a test fails if the root gains a file.
- **Saved data location.** BrisartAI saves two files and both now live in the per-user folder: `brisart_ai_index.sqlite3` (imported files, crawled pages, notes and session memory) and `research_settings.json` (the three research toggles). On Windows that is `%APPDATA%\Brisart Research Archive\BrisartAI`; macOS uses `~/Library/Application Support/Brisart Research Archive/BrisartAI` and elsewhere `$XDG_CONFIG_HOME/Brisart Research Archive/BrisartAI` (or `~/.config/...`). `BRISARTAI_STATE_DIR` replaces the path. An index or settings file left beside the program by an earlier release is moved there once, on the first start of `run.py` or `cli.py`.
- **Startup.** The launchers and development scripts install the external native module path before importing application code. The shared Archive dependency is `94_Native_API's/Official`; no native implementation or fallback ships with Offline_AI.
- **Cleanup.** A duplicated service module is removed and the test suite no longer rewrites a settings file.
- **Documentation.** The project README and every folder README are rewritten, each describing only its own folder, and several statements that did not match the code are corrected (see Changed and Fixed).

### Added

- **`brisart_ai/state.py`.** `state_dir()`, `index_path()` and `settings_path()` give the per-user folder and the two files in it; `migrate_legacy_state()` does the one-time move from `<project>/brisart_ai_index.sqlite3` (with its `-wal`, `-shm` and `-journal` files) and `<project>/data/research_settings.json`. Standard library only. The move:
  - copies the index with SQLite's backup API, which reads through the write-ahead log, then checks `PRAGMA integrity_check` and compares every table's row count with the original before removing it;
  - copies the settings file through a temporary file, fsynced and size-checked;
  - never overwrites a settings file or an index with rows in any table, and replaces an index with none (what a start after a failed move would have created), so a failure cannot hide the old data on the next start;
  - on any failure keeps the original, removes its own temporary file and prints a warning naming both folders, and the program still starts;
  - takes a lock file in the new folder, so several copies starting together move each file once; a lock older than 120 s counts as abandoned;
  - does nothing, not even creating the folder, when there is nothing to move, and never runs when `BRISARTAI_STATE_DIR` is set.
- **`brisart_ai/native_path.py`.** `find_native_dir()` honors `BRISART_NATIVE_API` first; an invalid override raises instead of falling back. Without an override, it checks ancestor directories for `94_Native_API's`, preferring `Official/` and accepting the flat API folder if it is complete. Older folder spellings remain supported. All seven modules must be present and resolve outside Offline_AI. `install()` puts the chosen directory on `sys.path` once, so application code can keep its flat imports.
- **`scripts/run_tests.py`.** Runs pytest with the project root on `sys.path`, `native_path.install()` called first, `--import-mode=importlib` and the cache folder disabled. Other arguments go to pytest, and `brisart_ai/` is added when none names a path. It does what a root `pytest.ini` and `conftest.py` would, which `docs/TESTING.md` described but the tree never contained.

### Changed

- **Documentation.** Reworked the six-section headers across source files, tests and tooling. Reorganized the folder READMEs and clarified the shared native dependency, local state migration, and verification boundaries in the project guides. Historical release entries are unchanged.
- **`run.py`, `cli.py`.** Each calls `native_path.install()` before any other `brisart_ai` import, and `state.migrate_legacy_state()` before the index is opened. `run.py` now describes itself as the desktop entry point and points to `cli.py` for headless use; `cli.py --db` defaults to the index in the state folder.
- **`brisart_ai/knowledge/index.py`.** `DEFAULT_DB` is the index in the state folder instead of `<project root>/brisart_ai_index.sqlite3`, and `Index()` creates the parent folder of its database if it is missing. The header's placeholder limitations and examples are replaced.
- **`brisart_ai/core/settings.py`.** `DEFAULT_SETTINGS_PATH` is the settings file in the state folder. The header is rewritten.
- **`brisart_ai/core/service.py`.** `BrisartService(db_path, settings_path=None)`; the default is the state-folder file, and a path lets a caller keep settings elsewhere.
- **`scripts/debug_offline_replay.py`, `scripts/debug_search_replay.py`.** Call `native_path.install()` before their first `brisart_ai` import; their placeholder limitations and examples are replaced.
- **`README.md` is now `docs/README.md`, and is rewritten.** The project overview moved from the root so the root holds only the three entry files; GitHub shows `README.md` from `docs/` for the folder. It now covers what BrisartAI is, how to run it (the `cli.py` commands, including that `ask` never searches the web without `--web`), where saved data lives, what it reads, web research, how an answer is chosen, the project layout and the documents in `docs/`. It no longer lists `docs/KNOWN_ISSUES.md` or `docs/file_types.md`, or points to a `LICENSE`, none of which is in this tree.
- **`version.py`.** 1.2.0.
- **Folder READMEs.** Application and script READMEs describe their own folders. `brisart_ai/README.md` now documents the application package rather than duplicating the former native README. The project overview, architecture, test instructions and release history live under `docs/`.
- **Other documents.** `docs/ARCHITECTURE.md`, `docs/TESTING.md` and `docs/SECURITY.md` describe the entry points (`run.py` and `cli.py`; several passages still named `brisartai.py` or called the project GUI-only), the state folder and the move, where the native stack is found, the runner, and the application test setup. `docs/SECURITY.md` adds that saved data is an unencrypted SQLite file in a folder that is the roaming profile on Windows. The three documents no longer say the native modules are verified against the standard library in every case: the hash, Base64, DEFLATE, URL and JSON tests compare against it, and the markup and robots tests assert behavior.
- **`brisart_ai/ui/app.py`.** The startup error dialog told the user to check write access to "the install folder"; the database is now in the state folder, so it says "the folder that holds BrisartAI's saved data".
- **`brisart_ai/util.py`.** The header said `safe_read_text()` tries UTF-8, then UTF-16, then Latin-1, and that `same_site()` compares hostnames only. Neither was true: the UTF-8 decode with replacement never fails, so the other two are never tried, and `same_site()` compares the whole netloc, port included. The header now says so, and its placeholder Known limitations and Examples are replaced. The behavior is unchanged.
- **`run.py`.** The header no longer refers to a `start.bat` that is not in the project.

### Removed

- **`brisart_ai/native/`.** Removed the bundled implementations, their README and module-specific tests. The application suite still exercises calls into the external modules.
- **`native_path.py`, `README.md` and `data/` from the project root.** Moved as described above; `data/` held only `research_settings.json` and a README describing it, and the defaults are listed in `brisart_ai/core/README.md`.
- **`brisart_ai/ui/service.py` and `brisart_ai/ui/tests/test_service_headless.py`.** Below the header, `ui/service.py` was identical to `core/service.py`, and the two test files differed by one import line. Nothing imported `brisart_ai.ui.service`; `ui/app.py` and `cli.py` use `brisart_ai.core.service`.

### Fixed

- **Native API folder spelling.** Automatic discovery now recognizes the apostrophe in `94_Native_API's`. The previous path list omitted this spelling and prevented startup without an override.
- **Tests rewrote the settings file.** `BrisartService` always opened the project's own settings file and a service test toggled `search_notes`, so every run left it switched off; the committed file had `search_notes: false`, and with it `cli.py ask` ignored saved notes. The service tests now pass a temporary `settings_path`, and nothing in the suite touches the state folder.
- **Settings dialog note was wrong.** `brisart_ai/ui/dialogs.py` told the user that only Automatic Web Research changes how questions are answered and that files and notes are always searched. The Local Files and Research Notes settings do change what is searched, and the note now says what all three do.
- **Extra blank lines at the end of files.** 74 `.py` files ended with two blank lines and 14 `.md` files with one; each now ends with a single newline.

### Tests

- **Final 1.2.0 application suite:** `python scripts/run_tests.py -q` passed 346 tests and 7 subtests on Linux with Python 3.12. The test modules were staged outside Offline_AI under `94_Native_API's/Official`. The earlier 424-test result covered the bundled layout and included native-module tests that no longer ship with the application.
- **Dependency and startup:** Regression tests check exact folder spelling and precedence over an older alias, flat directory discovery, explicit overrides, rejection of local copies, and the external import origin of all seven modules. The CLI started from outside the repository without an override. It also saved and retrieved a note in the external-only layout. Startup failed as expected when the external stack was absent.
- **State and layout:** Tests cover platform paths using supplied environment values, SQLite migration including uncheckpointed data, preservation of existing destination data, failure and retry behavior, concurrent migration, and CLI startup after migration. Layout checks reject bundled native implementations, local saved state, `__init__.py`, and extra root files.
- **Not verified:** The final tests used staged modules, not the live Archive copy. Windows Python 3.14 desktop startup, Tk and Windows file locking were not verified.

### Compatibility and limits

- **Upgrading.** Keep `94_Native_API's/Official` outside Offline_AI. If updating an older copy in place, remove obsolete `brisart_ai/native/`, root `native_path.py` and root `README.md` if present. Preserve any legacy index or `data/research_settings.json` until migration is confirmed. Eligible files move to the per-user state folder on startup; when an existing destination blocks migration, the original is retained.
- **Roaming profile.** `%APPDATA%` is the roaming profile, which a domain can sync between computers, and the index records this computer's file paths. Set `BRISARTAI_STATE_DIR` if that matters.
- **Layout test.** `test_layout.py` fails while an index from an earlier release is still beside the program; start `run.py` or `cli.py` once, or delete it. It also fails if any other file, such as a `README.md` or `LICENSE`, is added to the root; edit `ROOT_FILES` in that test to allow one.
- **`brisart_ai.ui.service`** no longer exists; use `brisart_ai.core.service`. `BrisartService` is unchanged apart from the optional `settings_path`.
- **Running tests.** Use `python scripts/run_tests.py` to configure the external dependency before test collection. The API modules and their own tests belong to the shared API project.
- **Detached checkouts.** Set `BRISART_NATIVE_API` to the external directory containing all seven modules. There is no bundled fallback or automatic download.
- **Lock timeout.** If the move's lock cannot be taken within 150 s the move is skipped with a warning and the program starts on an empty index; the next start moves the old one over it as long as nothing was added to the new one.
- **History.** `cli.py`, and the public-only redirect handling in `web/fetcher.py` with `web/tests/test_public_fetch_policy.py`, were added after 1.1.0 and are not recorded in its entry; the changes made in 1.2.0 are listed above.
- **Missing files.** The tree has no `LICENSE`, `docs/KNOWN_ISSUES.md`, `docs/file_types.md` or `docs/safety.md`. The current READMEs no longer refer to them; older entries below still do.

---

## [1.1.0] - 2026-10-26

### Release overview

A ranking and answer fix for ordinary questions. Before this release a question such as "how do lawsuits work?" matched only the exact word *lawsuits* and treated *work* as a topic word, so documents about jobs, shifts and working hours outranked the document about lawsuits, and sentences that said "a lawsuit" were never picked for the answer. BrisartAI now matches regular singular and plural forms, ignores the *work* in "how does X work", and reads file-name titles word by word. Index format, settings, web research and the UI are unchanged; existing index databases work as they are because the change is on the query side only.

### Changed

- **`brisart_ai/util.py`.** New `term_variants()` (the term plus its regular -s/-es/-ies singular or plural; terms under three letters or containing digits get no variants, and "ss" endings are never stripped), `query_frame_terms()` (*work*/*works*/*worked* at the end of a "how do/does/did/can/will/would/could/should ..." question, unless it is the only topic word), `expand_query_terms()` (query tokens minus frame words, plus variants) and `title_tokens()` (tokenize after splitting on `_`, `-` and `.`).
- **`brisart_ai/knowledge/ranker.py`.** `search()` looks up every form of each query term and merges them per document into one term frequency, one document frequency, one rarity and one coverage slot, so "lawsuit lawsuits" scores the same as "lawsuit". Frame words get `STOPWORD_WEIGHT` and do not count toward coverage. `title_match_adjust()` matches title tokens from `title_tokens()` in either form, so file-name titles such as `LEGAL_SIMULATION.md` now earn the title bonus; before, the whole name was one token and never matched.
- **`brisart_ai/knowledge/synthesizer.py`.** `synthesize()` scores sentences against `expand_query_terms()` instead of the raw tokens, so a sentence about "a lawsuit" can answer a question about "lawsuits", and "work" no longer pulls in sentences about jobs.
- **`version.py`.** 1.1.0.
- **`docs/ARCHITECTURE.md`, `docs/TESTING.md`.** The ranking core lists the query-term step and the title split; test counts updated.

### Added

- **10 tests.** `knowledge/tests/test_ranker.py` (5): a plural query finds a singular document, "how do lawsuits work?" ranks a lawsuit document above a page full of *work*, "how does it work" still searches for *work*, both forms in one query count once, and a file-name title gets the title bonus. `tests/test_util.py` (4): variants in both directions, no bad strips, the question frame, title splitting. `knowledge/tests/test_synthesizer.py` (1): a singular sentence answers a plural question. Four of the ranker tests and the synthesizer test fail against 1.0.0, which confirms they cover the change; the full suite is 389 tests and passes (`pytest --import-mode=importlib` from the project root), including the pinned founder, inventor, statistic and explanation regression cases.

### Compatibility and limits

- Only regular English plurals are handled. Irregular forms (*children*, *people*/*person*), verb tenses and related words are not linked: *sued* does not match *lawsuit*, and *working* does not match *work*.
- Variant lookups add one indexed SQL query per extra form, usually two forms per term.
- `scripts/debug_offline_replay.py` and `scripts/debug_search_replay.py` were not run for this release; ranking was checked with the tests above and against Studio Empire's documents, where "how do lawsuits work?" now returns only lawsuit passages instead of job and shift rules.

---

## [1.0.0] - 2026-09-14

Official 1.0.0 release. BrisartAI moves from the 1.0.0-beta.x line to a stable, fully-documented, fully-tested release. No ranking or retrieval behavior changed in this release — every change below is architectural, verification, or documentation work performed on top of the exact feature set shipped in 1.0.0-beta.10.

### Added

**The Brisart Native Stack is now wired into the application.** All seven modules under `brisart_ai/native/` (`brisart_hash`, `brisart_codec`, `brisart_url`, `brisart_json`, `brisart_markup`, `brisart_robots`, `brisart_inflate`) — each a from-spec, pure-Python reimplementation of a standard-library primitive, previously built and verified but not yet imported anywhere — are now imported at every real call site: `util.py` (hashing, URLs), `blocklist.py` and `intent.py` (URLs), `io/extractor.py` (HTML tokenizing, URLs), `io/readers.py` and `core/settings.py` (JSON), `io/binary_readers.py` (DEFLATE/zlib), `web/search.py` (Base64, JSON, HTML tokenizing, URLs), `web/policy.py` (robots.txt, URLs), and `web/crawler.py` (URLs). Actual HTTP networking (`urllib.request`/`urllib.error`) is unchanged, since the native stack replaces parsing and encoding logic, not the network transport itself. This resolves the previously tracked KI-001.

**A full, co-located automated test suite.** 380 tests, one `tests/` subfolder inside every `brisart_ai/` package that contains source modules (`native/tests/`, `io/tests/`, `core/tests/`, `knowledge/tests/`, `web/tests/`, `ui/tests/`, plus `brisart_ai/tests/` for the four top-level shared modules). Every native module is tested directly against the real stdlib function it replaces (`hashlib`, `base64`, `zlib`, `urllib.parse`, `json`, `html.parser`, `urllib.robotparser`), not just internally self-consistent. The project's own founder/inventor/statistic/explanation ranking regression cases are preserved as pinned assertions. Network-dependent code (`web/search.py`'s live providers, `web/fetcher.py`'s live fetch) is tested with the network layer mocked or pointed at a non-routable address, never with real outbound calls. `pytest.ini` configures `--import-mode=importlib` so `pytest` (used only as the discovery runner) can find same-named `tests/` folders scattered across the tree without requiring `__init__.py` files, preserving `brisart_ai/`'s deliberate namespace-package design. This resolves the previously tracked KI-009.

### Changed

**`version.txt` replaced by `version.py`.** The version string is now a real, importable Python module (`__version__ = "1.0.0"`) at the project root instead of a bare text file. `brisart_ai/version_info.py` loads it by file path via `importlib.util` rather than a plain `import version`, since `version.py` lives outside the `brisart_ai` package and must not require the project root on `sys.path`. Falls back to `"0.0.0-unknown"` on any failure, exactly as the previous `version.txt`-reading implementation did.

**`brisartai.py` renamed to `run.py`.** The application is now started with `python run.py` (or `py run.py` on Windows, matching `start.bat`, which has been updated accordingly). Contents are otherwise identical to the former `brisartai.py`.

**Every documentation file rewritten.** The root `README.md` (previously missing entirely, with its content only surviving as a duplicate inside `docs/README.md`), `docs/README.md` (now a lean documentation index instead of a duplicate full README), `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/safety.md`, `docs/KNOWN_ISSUES.md`, `docs/TESTING.md` (new), `docs/CHANGELOG.md`, `docs/file_types.md`, `brisart_ai/native/README.md`, and every per-package `README.md` under `brisart_ai/` were all rewritten to a single consistent standard, trimmed to exactly what each file type needs. The native-stack wiring status is now stated correctly and consistently across every file that mentions it (previously several files still said "not yet wired," which was accurate at the time but became stale once the wiring work above landed).

### Fixed

**Two known issues closed out.** KI-001 (native stack built but not wired in) and KI-009 (no automated test suite) are both moved from `docs/KNOWN_ISSUES.md`'s open list to its Resolved section, with full resolution detail recorded there.

### Verification

- Full compile check: all 32 application modules and all 380 test files compile cleanly.
- All 7 native modules' own internal self-tests pass.
- Full 380-test suite passes (`pytest`, run from the project root).
- Full end-to-end pipeline test (local file indexed → ranked → synthesized into a cited answer) verified working against the fully-wired native stack.
- `version_info.__version__` confirmed correctly reading the new `version.py` via `importlib.util`, with the documented fallback behavior confirmed on a simulated missing/broken file.

### Known Limitations

- `brisart_ai/ui/app.py`, `chat_panel.py`, `dialogs.py`, and `sidebar.py` construct real Tkinter widgets and require a live display; they remain verified manually rather than under the automated test suite (see `docs/TESTING.md`).
- ZIP container parsing (`zipfile`) and XML parsing (`xml.etree.ElementTree`) — used by `io/binary_readers.py` for Office/ODT formats — remain stdlib dependencies; native replacements were scoped out of the Brisart Native Stack as a distinct, comparably-sized follow-up effort (see `brisart_ai/native/README.md`).
- All other known issues carried forward from 1.0.0-beta.10 remain open; see `docs/KNOWN_ISSUES.md` for the current list (KI-002 through KI-008).

---

## [1.0.0-beta.10] - 2026-08-30

### Changed

- Rewrote the top-of-file header/docstring for all 30 files in the BrisartAI package tree (`brisart_ai/` and its `core/`, `io/`, `knowledge/`, `ui/`, `web/` subfolders, plus `brisartai.py` and both `scripts/debug_*.py` files).
- First pass used documentation depth scaled to each file's actual complexity instead of a forced template:
  - **Trivial** files (`version_info.py`, `ui/theme.py`, `web/models.py`, `web/stats.py`, `io/input_cleaner.py`, `brisartai.py`) — one tight paragraph, no sections.
  - **Light** files (UI widgets, `core/settings.py`, `core/session_memory.py`, `knowledge/ingest.py`, `io/readers.py`) — a few natural paragraphs.
  - **Medium** files (`io/binary_readers.py`, `io/extractor.py`, `knowledge/index.py`, `core/conversation.py`, `ui/service.py`, `ui/app.py`, `web/fetcher.py`, `web/policy.py`, `knowledge/vault.py`, both debug scripts) — prose with bolded call-outs only where earned.
  - **Deep** files (`blocklist.py`, `intent.py`, `knowledge/ranker.py`, `knowledge/synthesizer.py`, `web/crawler.py`, `web/search.py`, `util.py`) — full narrative explanation of the non-obvious design decisions.
- Second pass replaced that with one rigid four-section template (`Purpose` / `Communication relationships` / `Settings-parameters` / `Edge-case behavior`) on every file regardless of size or complexity.

---

## [1.0.0-beta.9] - 2026-08-30

### Fixed

**Startup crash on a locked or unopenable database.** `ui/app.py`'s `BrisartApp.__init__()` now constructs the backend `BrisartService` (and therefore opens the SQLite index and session database) before the Tk window is created, not after. `run()` wraps app construction in a single `try/except` and shows a proper `messagebox.showerror()` dialog on failure instead of letting the exception propagate into an unhandled console traceback. Root cause: the Tk window was previously built first, and a subsequent failure opening the SQLite index (locked by another running copy, a read-only install folder, missing file permissions) raised a raw `sqlite3` exception straight out of the constructor, leaving a half-built, invisible window behind with no dialog ever shown. `ui/service.py`'s `BrisartService.__init__()` is documented as deliberately unguarded, so `run()`'s single catch site is the only place startup failures are handled. Verified with a standalone simulation reproducing the exact construction order: on failure, zero window-like objects are ever created; on success, the window is still created exactly once.

**Duplicate, drifted function-word list in web search.** `web/search.py`'s `FUNCTION_WORDS` (used to decide which query words are "meaningful" for judging whether a search result is on-topic) is no longer a second, hand-maintained word list — it now imports the single canonical list from `brisart_ai/blocklist.py`. Root cause: this module's local copy had silently drifted from the shared list and was missing common words present there (e.g. "about", "into", "over"). A query like "give me info about cats" treated "about" as a meaningful topic term, so a completely off-topic result that merely also contained the word "about" could be marked "related" and pass through untouched. Verified with a synthetic two-result batch: before the fix, both results were incorrectly marked related; after, only the genuinely on-topic result is.

**Founder/company recognition vocabulary expanded.** `intent.py`'s `_KNOWN_COMPANIES` now recognizes roughly 25 additional well-known single-token company names across streaming, gig-economy, fintech, gaming, and productivity software (Twitch, DoorDash, Notion, Figma, Palantir, Snowflake, Slack, Zoom, Roblox, and others). Root cause: any company not in this fixed list silently fell back to the inventor-intent default, which uses less appropriate boost/penalty vocabulary for a company-history question. Verified: "who founded twitch/notion/figma/palantir/databricks/roblox?" now all classify as founder intent (previously: inventor).

### Verification

- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero regressions.
- Re-ran the full 1.0.0-beta.8 crawler test suite after the `FUNCTION_WORDS` consolidation; all pass.
- Re-ran the mocked end-to-end pipeline test after all beta.9 changes; the correct source is still cited and the off-topic page is still excluded.

### Known Limitations

- No formal automated unit-test suite or CI pipeline existed at this point in the project's history (resolved 2026-09-13; see `docs/KNOWN_ISSUES.md`'s KI-R09).
- The crawl-time relevance check is still ranking-based, not a hard gate (see `docs/KNOWN_ISSUES.md`'s KI-002).

---

## [1.0.0-beta.8] - 2026-08-29

### Added

**Title- and phrase-aware public web ranking.** `web/search.py`'s `search_public_web()` now accepts an optional `with_titles` parameter returning `list[tuple[str, str]]` of `(url, title)` pairs instead of a bare `list[str]`; every provider already parsed out a result's title internally but previously discarded it before reaching the caller. `web/crawler.py`'s `score_result()`, `rank_results()`, and `explain_ranking()` now fold a result's own title into its relevance score on equal footing with its hostname, and a literal contiguous multi-word phrase match against the combined URL+title text earns a scoring bonus, with phrase detection delegated to `knowledge.ranker.phrase_match_adjust()`. Root cause: many ordinary result URLs carry an opaque numeric ID or truncated slug with none of the query's meaningful words; the words that actually answer the question typically live only in the page's title. Verified with a synthetic batch: two identically-shaped opaque numeric-slug URLs scored identically (-2, -2) with no title information; once real titles were supplied, the on-topic result scored 14 against the off-topic result's unchanged -2. Verified full backward compatibility with no title supplied.

**Broader numeric/quantity detection in answer synthesis.** `knowledge/synthesizer.py`'s `_HAS_QUANTITY` now also recognizes currency figures, distances, mass, and time units, in addition to the original population/demographic unit set. Root cause: a statistic-style question whose answer is a distance, weight, or dollar figure previously had no unit-word match at all. Verified against six representative sentence categories.

### Verification

- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero regressions.
- Full mocked end-to-end pipeline test for "how much does a blue whale weigh": confirmed the correctly-titled article is both ranked first and cited as the sole source.

### Known Limitations

- Search-result snippets (as opposed to titles) are still not incorporated into web ranking (see `docs/KNOWN_ISSUES.md`'s KI-006).
- The phrase-match bonus in `web/crawler.py` is a flat integer bonus, not the multiplicative factor `knowledge.ranker.phrase_match_adjust()` itself returns (see KI-007).
- The exact current HTML structure of Mojeek, Brave Search, and Startpage remains unverified against a live fetch (see KI-005).

---

## [1.0.0-beta.7] - 2026-08-26

### Fixed

**Text extraction.** `io/extractor.py`'s `HTMLTextExtractor` no longer leaks MediaWiki-style inline citation markers (e.g. Wikipedia's `<sup class="reference">[3]</sup>`) into extracted text. Scoped narrowly to `<sup>` elements carrying a `reference`, `cite-bracket`, or `citation` class, so ordinary superscript text is left untouched.

**Startup crash.** Removed the dependency on a separate `web/search_extra_providers.py` module entirely. That split caused a real production crash: the companion file existed on disk but was accidentally left empty, and `search.py`'s top-level import raised an `ImportError` before the application could start. Every search provider now lives directly in `web/search.py`.

**Decoy/off-topic search results.** Replaced the whole-batch `_results_look_unrelated()` guard with `_partition_related_results()`, which judges each `(url, title)` result individually against the query. Observed live: a "2025 Tesla vandalism" Wikipedia page surfaced as a source for "what is america?", and a "Nikola Tesla" page surfaced for a Trump-legislation query, in both cases sitting next to 2-3 genuinely relevant results — enough for the old whole-batch check to wave the entire batch through unfiltered.

**Ranking: generic words winning on title match.** `knowledge/ranker.py`'s `title_match_adjust()` now dampens a fixed set of generic instructional/question verbs (`GENERIC_QUERY_VERBS`) so they contribute at most 20% of what an equally-rare specific term contributes. Root cause: title-match weighting used corpus rarity (IDF) alone, and IDF cannot tell "explain" apart from a person's surname when both have a document frequency of 1. Observed live: "explain who jason brisart is and where does he live" surfaced a dictionary page about the word "explain" instead of the user's own indexed research documents.

**Ranking: bare generic-concept pages outranking specific answers.** Added `is_bare_generic_concept_title()` (correctly stripping common `" - Site Name"` suffixes) and `generic_concept_title_adjust()`, applying a fixed 0.35x penalty unconditionally regardless of detected intent. Root cause: the existing generic-concept-page guard only ran inside `score_intent()`, which is skipped entirely for `INTENT_GENERAL` queries. Observed live: "what laws have been passed since trump became president" surfaced a bare "Law - Wikipedia" page ahead of genuinely relevant sources.

**Ranking: long articles outranking shorter, more relevant ones.** Added BM25-style document-length normalization (`LENGTH_NORM_B = 0.6`) to the base TF-IDF scoring pass. Root cause: raw term frequency cannot distinguish "genuinely dense in this topic" from "long enough to mention this word a dozen times in passing." Observed live: a long "South Africa - Wikipedia" article surfaced as a source for a Trump/US-laws question purely because of its length.

### Added

- Three additional sequential fallback search providers — **Startpage, Brave Search, and Mojeek** — fully self-contained in `web/search.py`. Result parsing avoids hardcoded CSS class names; results are identified by domain heuristics instead, since these three providers' markup is undocumented or shifts often.
- Provider chain reordered by block-risk, not by establishment: **Startpage → Brave Search → DuckDuckGo HTML → DuckDuckGo Lite → Bing HTML → Mojeek → Wikipedia API**, from most likely to be blocked to least likely.

### Verification

- Re-ran the exact citation-marker repro from the live "what is america?" session; confirmed `[3]` no longer appears.
- Confirmed the merged, single-file `web/search.py` imports cleanly and the full 7-provider fallback chain cascades correctly end-to-end.
- Rebuilt the "Understanding 'Explain'" vs. research-document matchup and confirmed the research document now wins.
- Rebuilt the "Law - Wikipedia" vs. relevant-content matchup and confirmed the relevant page now wins (6.44 vs. 0.32 in test scoring).

### Known Limitations

- The exact current HTML structure of Mojeek, Brave Search, and Startpage has not been verified against a live fetch outside the development sandbox.
- Document-length normalization uses total indexed term count as a proxy for document length, not a stored character/byte count.

---

## [1.0.0-beta.6] - 2026-08-26

### Added

- **Title-match ranking signal** in `knowledge/ranker.py`. A document whose own title contains meaningful query terms now receives an explicit score multiplier (up to 1.42x), separate from ordinary TF-IDF credit.
- **Phrase-match ranking signal.** When the literal query text appears as a contiguous phrase anywhere in a document's title, location, or body, the score receives a flat 1.35x multiplier. Applies only to multi-word queries.
- `knowledge/vault.reindex_missing_notes()`, which walks all saved notes at startup and indexes any that predate note-mirroring. Existing notes silently gain full ranked search the next time the app runs.
- `knowledge/ranker.search()` now accepts an optional `source_types` parameter (a set of allowed source types), used to combine multiple source kinds into a single ranked query.

### Changed

- `knowledge/vault.add_note()` now mirrors every saved note into the main `sources` index (`source_type="note"`) in addition to the vault's own `notes` table — notes now receive the exact same TF-IDF, coverage, title-match, phrase-match, and intent-aware ranking as imported files and crawled web pages.
- `core/conversation.py` no longer merges notes into results via a separate substring-count pass; `build_conversation_answer()` builds one `source_types` set from settings and passes it directly to `knowledge/ranker.search()`.
- `ui/service.py` calls `reindex_missing_notes()` once during `BrisartService.__init__()`.

### Verification

- Confirmed a title-matching document ranks above a longer, non-titled document containing the same query terms.
- Confirmed a document containing the literal query phrase ranks above a document containing the same words non-contiguously.
- Confirmed a note inserted directly into the `notes` table (simulating a pre-beta.6 save) is invisible to ranked search until `reindex_missing_notes()` runs, then becomes fully ranked with zero user action.
- Re-ran the founder-intent regression case ("who invented microsoft?") to confirm the new signals compose correctly with the existing intent-aware layer.

### Known Limitations

- Phrase-match detection is a literal substring check after punctuation normalization; it does not account for synonyms, stemming, or word reordering within the phrase.
- Collections and entity extraction remain implemented in `knowledge/vault.py` but are still not exposed through the desktop UI.

---

## [1.0.0-beta.5] - 2026-08-26

### Added

- New `comparison` intent class in `brisart_ai/intent.py`, shared by both web ranking and offline ranking (e.g. "do dogs outlive cats").
- `knowledge/vault.py`'s `search_notes_as_documents()`, converting saved vault notes into the same document shape produced by `knowledge/ranker.search()`.

### Fixed

- `knowledge/synthesizer.py` no longer maintains its own separate query-intent detector; delegates directly to `brisart_ai.intent.detect_intent()`.
- The `search_notes` setting previously had no effect — saved notes were never queried by `core/conversation.py`. `build_conversation_answer()` now merges note results into the local evidence pool whenever the setting is enabled.
- The `search_local_files` setting is now actually applied during search.

### Removed

- The "Research Collections" toggle in `core/settings.py` and the Settings dialog — it rendered as a live checkbox but had no effect, since there is no "active collection" concept in the current UI for it to restrict.

### Changed

- `core/settings.py`'s `DEFAULT_SETTINGS` and `TOGGLE_LABELS` reduced from four entries to three (`search_local_files`, `search_notes`, `auto_web_research`). Existing settings files with a stale `search_collections` key are read safely; the unknown key is ignored on load.
- Moved `CHANGELOG.md` to `docs/CHANGELOG.md`.

### Verification

- Re-ran existing intent classification cases with zero regressions; added 3 new comparison-intent cases.
- Confirmed `search_notes_as_documents()` produces ranker-compatible documents.

### Known Limitations

- Notes participate in local search with simple substring/count scoring at this point in the project's history, not the full TF-IDF + intent-adjusted ranking used for files and web pages (superseded in 1.0.0-beta.6).

---

## [1.0.0] - 2026-08-26

### Maintenance

- Removed an unused `Iterable` import from `typing` in `brisart_ai/knowledge/vault.py`. No functional changes.
- This release marks BrisartAI's transition from beta to production status; the underlying feature set is the intent-aware ranking and GUI-only architecture already shipped in the 1.0.0-beta.1–beta.4 line.

---

## [1.0.0-beta.4]

### Added

- Intent-aware ranking layer shared by both public web search and offline document retrieval (`brisart_ai/intent.py`), classifying founder/company, inventor/device, statistics/population, explanation/mechanism, and general questions.
- Intent debugging information exposed through replay tooling.
- `scripts/debug_offline_replay.py` for validating offline retrieval behavior using standalone fixture datasets.
- Shared intent scoring between `web/crawler.py` and `knowledge/ranker.py`, preventing web and offline ranking from diverging.

### Fixed

- Search relevance no longer relies exclusively on raw keyword overlap; queries are now ranked using both term matches and question intent.
- Fixed article-slug scoring logic that recognized hyphenated titles but ignored underscore-separated titles.
- Fixed percent-encoded URL handling during ranking (e.g. `Invented_%28album%29` previously bypassed work-of-art relevance penalties).

### Changed

- Public web search and offline search now share a unified ranking model instead of maintaining independent relevance behavior.
- Ranking adjustments are deliberately bounded so intent acts as a hint rather than a hard filter.

### Verification

- `compileall` and import-smoke validation completed successfully.
- 23/23 intent-classification checks, 18/18 name-shape checks, 12/12 generic-concept checks passed.
- Observed search quality improvements during replay validation (e.g. "who invented microsoft?": 2/5 relevant → 5/5 relevant).

### Known Limitations

- Public web ranking evaluated URLs only at this point (title-awareness added in 1.0.0-beta.8).
- Founder detection used a finite company list (ongoing; see KI-004).

---

## [1.0.0-beta.3]

### Fixed

- The desktop UI no longer freezes during web research. `ui/app.py` now runs `BrisartService.ask()` on a background thread and marshals the result back onto the Tk main loop via `after()`.
- `knowledge/index.py`'s `Index` and `core/session_memory.py`'s `SessionMemory` SQLite connections are now opened with `check_same_thread=False`.
- The "Automatic Web Research" settings toggle now actually affects typed chat questions (previously `ui/service.py`'s `ask()` always forced `force_web=True`).
- Diagnostic output from the crawler/search/policy/fetcher layers is captured via `contextlib.redirect_stdout` and surfaced in the chat transcript.

### Changed

- The explicit "Research Web" sidebar action always forces a fresh public web search; ordinary typed questions respect the Automatic Web Research setting.

---

## [1.0.0-beta.2]

### Removed

- `knowledge/project_memory.py`, `knowledge/relationship_graph.py`, `knowledge/memory_report.py`, `knowledge/analyzer.py`, `knowledge/project_awareness.py`, `knowledge/source_attribution.py` — persistent project memory and analysis layer.
- The entire terminal CLI/chat stack (`core/cli.py`, `core/chat.py`, `core/commands.py`, `core/assistant.py`, and supporting modules). BrisartAI is now GUI-only.
- The personality/freeform/self-knowledge conversational layer — the Observation/Confidence/Why-I-think-this narration voice is gone; `knowledge/synthesizer.py` now returns the extracted answer and a plain source list directly.
- `--gui`/`--cli` startup flags (there is only one mode now).
- All `/vault`, `/collection`, `/timeline`, `/crawl`, `/scan-preview` chat slash-commands.
- The legacy `tests/` folder, which was tied to the pre-beta answer format.

### Fixed

- Full audit of every import across all remaining Python files confirmed zero dead imports and zero references to deleted modules.

---

## [1.0.0-beta.1]

### Added

- Persistent research settings module (`core/settings.py`).
- Automatic Web Research: local evidence is re-checked against the public web when it comes up empty.
- Desktop GUI (`brisart_ai/ui/`) built with Tkinter.
- `--gui` and `--cli` startup modes with automatic fallback.
- Query intent hints for count/measure questions.
- Number-aware answer synthesis: sentences containing an actual numeric quantity are boosted for "how many"-style questions.
- Dictionary/definition host blocking at ingest time.
- Off-topic Wikipedia rejection for pages whose title is a bare function word.
- Startup index cleanup for stale dictionary/disambiguation rows.
- Bing HTML search provider added alongside DuckDuckGo, with automatic provider fallback.

### Changed

- `brisartai.py` now launches the desktop interface by default.
- Public web search rewritten to use `html.parser.HTMLParser` instead of regex-based link extraction.
- Result-link extraction now captures only organic result anchors.
- Retrieval ranking down-weights ultra-common stop/function words and adds a coverage multiplier.

### Fixed

- Web search no longer returns dictionary/definition results for factual questions.
- Synthesized answers no longer include narration scaffolding.
- `robots.txt` retrieval failures are treated as "allowed" instead of a site-wide block.

---

## [0.9.0-alpha]

### Added

- Crawl statistics reporting for web ingestion operations.
- Duplicate-content detection before indexing crawled pages.
- Localhost protection to prevent accidental crawling of local machine resources.

### Changed

- Refactored the web subsystem into focused modules: `web/models.py`, `web/stats.py`, `web/fetcher.py`, `web/search.py`, `web/crawler.py`.

---

## [0.8.0-alpha]

### Added

- Split the command-line interface into focused modules: `commands.py`, `chat.py`, `cli.py`.

### Fixed

- Citation numbering is now sequential with no gaps.
- Removed a noisy tokenized diagnostic line from answers.
- `USER_AGENT` now reflects the actual package version via `__version__`.

---

## [0.7.0-alpha]

### Added

- Knowledge Vault layer built on the existing SQLite index: research collections, local research notes with search, lightweight entity extraction, timeline view, vault report.

### Fixed

- Corrected a syntax error in `io/readers.py` that prevented startup.

---

## [0.6.0-alpha]

### Fixed

- Running `py brisartai.py` now starts interactive chat instead of showing help.
- Session memory now stores compact topics instead of huge command strings.
- Self-knowledge questions use a dedicated module instead of falling back to "no indexed files."
- Basic command typo correction.

### Added

- `self_knowledge.py`, `conversation.py`, `input_cleaner.py`, `start.bat`.

---

## [0.5.0-alpha]

### Added

- Free-form response mode for any typed input.
- Wider file type support, including pure-Python best-effort readers for `.docx`, `.pptx`, `.xlsx`, `.odt`, and `.pdf`.
- General assistant fallback that explains limits instead of going silent.

---

## [0.4.0-alpha]

### Added

- Assistant voice/personality layer: logical observations, evidence explanations, confidence labels, suggested next moves.
- Local session memory for recent chat context.

---

## [0.3.0-alpha]

### Added

- Conservative drive/folder scanning with hard limits for max files and file size.
- Recommendation engine based on indexed data; duplicate content detection by hash.

---

## [0.2.0-alpha]

Shifted BrisartAI from crawler-first to data-first architecture.

---

## [0.1.0-alpha]

Initial crawler/index/retrieval prototype.


