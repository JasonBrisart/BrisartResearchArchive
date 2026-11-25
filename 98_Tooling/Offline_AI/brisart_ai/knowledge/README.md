# brisart_ai/knowledge/

This folder owns evidence after extraction. Follow `ingest.py` and `index.py` for storage, `ranker.py` and `relevance_engine.py` for scoring, and `synthesizer.py` for cited excerpts. `vault.py` adds notes and research metadata over the same index.

## `index.py`

`Index(path=DEFAULT_DB)` opens a SQLite file (creating its folder if needed) with write-ahead logging, `synchronous=NORMAL` and foreign keys on, and creates two tables:

- **`sources`**: `source_key` (unique), `source_type`, `location`, `title`, `text`, `content_hash`, `size_bytes`, `extension`, `indexed_at`.
- **`terms`**: `term`, `source_id`, `tf`, with `(term, source_id)` as the key and a cascade delete from `sources`.

`DEFAULT_DB` is `brisart_ai_index.sqlite3` in the per-user state folder. It is fixed when the module is imported, so pass a path to `Index()` to use another file.

`source_type` is `file`, `web` or `note`. The connection is opened with `check_same_thread=False` and nothing locks it.

| Method | Behavior |
|---|---|
| `add_source(source_type, location, title, text, content_hash="", size_bytes=0, extension="")` | Upserts on `source_key`, which is the hash of `source_type|location`, so adding the same file or page again replaces its row and all its term rows. The terms are the tokens of the title, location and text with their counts. Raises `ValueError` for an empty type or location and returns `False` for empty text. |
| `source_count(source_type=None)` | Number of sources, overall or of one type. |
| `purge_junk_web_sources()` (also `purge_blocked_web_sources()`) | Deletes `web` rows whose location the blocklist rejects; returns how many. File and note rows are never touched. |
| `clear()` | Deletes every term and source. |
| `close()`, and use as a context manager | Closes the connection. |

---

## `ingest.py`

`ingest_paths(paths, index)` indexes every supported file in the given files and folders and returns how many were added. For each file it reads the text, skips it when empty, records its size, SHA-256 and lowercased extension, and stores it with the file name as title and the resolved path as location. It prints `INGESTED`, `SKIPPED EMPTY` or `WARN` lines. A failure on one file, including a failed hash, is reported and never stops the rest.

---

## `relevance_engine.py`

The base term score. It uses small fixed tables instead of a continuous curve.

| Part | Rule |
|---|---|
| Rarity (`rarity_weight`) | By the share of documents containing the term: 20% or more is 0.4, 5% or more 1.0, 1% or more 1.8, less than 1% 2.6. |
| Presence (`presence_points`) | By occurrences in one document: 1 is 1.0, 2 is 1.3, 4 is 1.5, 8 or more is 1.6. |
| Contribution (`term_contribution`) | Presence times rarity. |
| Shape (`shape_multiplier`) | By document length against the corpus average: 2.5 times or more is 0.55, 1.5 or more is 0.75, 0.75 or more is 1.0, shorter is 1.15, so a short document is boosted. |
| Proximity (`proximity_bonus`) | A multiplier that starts at 1.0 and gains 0.15 for each pair of distinct matched terms within 120 characters of each other, up to 0.6 in total. |

A term in no document, or an empty corpus, scores 0.

---

## `ranker.py`

`search(index, query, limit=8, source_type=None, source_types=None)` returns a list of dictionaries, best first, each with `id`, `score`, `source_type`, `location`, `title`, `text`, `extension`, `size_bytes`, `indexed_at`, `intent`, `intent_boosts` and `intent_penalties`. A query with no searchable terms returns `[]`.

1. **Terms.** The query is tokenized. Each term is looked up in all its regular singular and plural forms, which share one score, one rarity and one coverage slot. In "how do X work" the word *work* is a frame word: it is scored like a stopword and left out of coverage, unless it is the only topic word.
2. **Base score.** For each matched term, a weight times the term's contribution. The weight is 0.15 for stopwords and frame words and 1.0 otherwise. The sum is multiplied by the shape multiplier.
3. **Coverage.** Multiplied by 0.15 plus 0.85 times the share of meaningful query terms the document matched.
4. **Adjustments**, applied to the top `limit * 5 + 10` candidates:
   - a title match, up to 1.42 times, damped for generic verbs such as "explain";
   - times 0.35 when the title or URL is a bare generic concept word such as "Law";
   - times 1.35 when a query of two or more words appears verbatim, ignoring case and punctuation, in the title, the location or the first 2,000 characters of the text;
   - the proximity bonus;
   - for a non-general intent, times `1 + 0.30 * delta` from `intent.score_intent`, kept between 0.40 and 1.90.
5. The top `limit` candidates are returned.

Intent only scales a score; it never removes a document. `phrase_match_adjust()` is also used by the web crawler.

---

## `synthesizer.py`

`synthesize(query, docs, max_sources=6, max_sentences=10, recent_topics=None)` builds the answer text. `recent_topics` is accepted and not used.

- With no documents it returns "I don't have any indexed information that answers that yet."
- Sentences come from the first `max_sources` documents and are scored by how many query terms (with their singular and plural forms) they contain, plus a density term. A sentence with no query term scores nothing.
- Quantity questions add 10 to a sentence with a real quantity (a number with a unit or currency) or 3 to one with any digit; comparison questions add 8 for comparative wording; "why" questions add 8 for causal wording. These apply only to sentences that already share a query term.
- Identical sentences are dropped. When a mode applies, sentences with its signal come first.
- The answer is one paragraph per source with up to three sentences, numbered `[1]`, `[2]` and so on in order of use, followed by `Sources:` and one `[n] type: title :: location` line each.
- If documents exist but no sentence matches, it returns "I found related sources, but none of them contained a passage that directly answers that."

It quotes the indexed text; it does not paraphrase or add facts.

---

## `vault.py`

Notes and some structure on top of the index. `init_vault_schema()` creates these tables on first use: `collections`, `source_collections`, `notes`, `entities`, `source_entities` and `timeline_events`.

**Notes.** `add_note(index, title, body, collection_name="")` saves a note, rejects an empty body, and also adds it to `sources` as `note:<id>`, so notes are ranked like files and web pages. `reindex_missing_notes(index)` adds any note that is missing from `sources` and returns how many; running it again does nothing. `list_notes` and `search_notes` return formatted text; `search_notes` counts term occurrences and is independent of the ranked index. `search_notes_as_documents` returns the same matches as document dictionaries.

**Collections, entities and timeline.** `create_collection`, `list_collections`, `add_sources_to_collection`, `extract_entities_from_text` (a capitalized-phrase pattern, not machine learning), `rebuild_entities`, `vault_report` and `timeline` are implemented. Nothing in the window or `cli.py` calls them today; only the note functions are reachable. The tests cover collections, entity extraction and the report, but not `rebuild_entities` or `timeline`.

---

## `tests/`

| File | Covers |
|---|---|
| `test_index.py` | Adding, upserting, counting, validation, purging, the context manager |
| `test_ingest.py` | Folders, single files, empty files, unsupported types |
| `test_relevance_engine.py` | Each table, its boundaries and its caps |
| `test_ranker.py` | Search results, source-type scoping, intent cases, title, generic-title and phrase adjustments, plural handling |
| `test_synthesizer.py` | The answer format, sentence scoring modes, citation numbering |
| `test_vault.py` | Notes, reindexing, collections, entities, the report |
