# brisart_ai/core/

The core is the shared request layer for the desktop and CLI. Start with `service.py` to trace a command, `conversation.py` to trace an answer, or `settings.py` to investigate which sources a request can use.

## `service.py`

`BrisartService(db_path=DEFAULT_DB, settings_path=None)` owns one `Index`, one `SessionMemory` and one `ResearchSettings`. `settings_path` defaults to the settings file in the per-user state folder; tests pass a temporary path.

Construction is not wrapped in `try/except`: a database that cannot be opened raises out of the constructor. It also runs two cleanups and prints a line for each that did anything: stale dictionary and definition pages are purged from the index, and notes saved before notes were mirrored into the index are indexed.

| Method | Behavior |
|---|---|
| `counts()` | `(total, files, web)` source counts. |
| `ask(text, limit=8, web_limit=5, force_web=None)` | Answers a question. `None` for `force_web` uses the `auto_web_research` setting; `True` or `False` overrides it. |
| `research(query, limit=5, depth=0)` | Searches the web and indexes the pages; returns a one-line summary. |
| `import_paths(paths)` | Indexes files and folders; returns a one-line summary. |
| `add_note(title, body)`, `list_notes(limit=20)`, `search_notes(query, limit=10)` | Notes, through `knowledge/vault.py`. |
| `toggle_setting(key)` | Flips a setting by name or alias; returns `(label, new_value)`. |
| `settings_panel_text()` | The text of the settings summary. |
| `close()` | Closes the memory and index connections. |

While `ask()` runs, everything printed by the crawler, search, policy and fetcher code is captured. `last_diagnostics` then holds up to five distinct captured lines that contain `WARN`, `SKIP` or `ERROR`. The capture redirects the process-wide `sys.stdout` under a lock.

---

## `conversation.py`

`build_conversation_answer(query, index, memory, limit=8, settings=None, web_limit=5, force_web=False)` answers one question:

1. Trims the question and removes one pair of matching outer quotes.
2. Chooses which source types may be searched. `web` is always included; `file` is added when `search_local_files` is on (or when there are no settings); `note` is added when `search_notes` is on.
3. Runs the ranked search.
4. Searches the web at most once, when `force_web` is true, or when there were no local results and `auto_web_research` is on. The search is followed by one more local search.
5. If anything was found, returns the synthesized answer, prefixed with "Searched the public web ..." when a web search ran. If nothing was found, returns a message saying so, worded differently when the web was searched.
6. Records the question and the answer in session memory, including when nothing was found.

---

## `session_memory.py`

`SessionMemory(db_path)` keeps a rolling log in a `conversation_memory` table of the same SQLite file the index uses.

- `add(role, content)` stores a compressed form: the content is cleaned the same way as a question, tokenized, and cut to the first 12 terms. If tokenizing leaves nothing it keeps the first 140 characters. Content that compresses to nothing is dropped. At most 400 characters are stored.
- `recent_topics(limit=6)` returns the newest topics first, without duplicates, each cut to 120 characters. Time stamps have one-second resolution, so the order of two entries added in the same second is not guaranteed.
- The connection is opened with `check_same_thread=False`.

---

## `settings.py`

`ResearchSettings(path=DEFAULT_SETTINGS_PATH)` holds three booleans in a JSON file.

| Setting | Default | Effect |
|---|---|---|
| `search_local_files` | on | Include imported files in local search |
| `search_notes` | on | Include saved notes in local search |
| `auto_web_research` | off | Search the web when local search finds nothing |

- `get(key)`, `set(key, value)` and `toggle(key)`; `set` raises `KeyError` for an unknown key and saves immediately.
- `resolve_key(raw)` accepts `web`, `auto-web`, `auto_web`, `local`, `local-files`, `notes` or a full setting name, case-insensitively.
- `render()` returns the text of the settings panel; `TOGGLE_LABELS` holds the display names.
- A missing file is created with the defaults. A corrupt file is ignored and the defaults are kept. Only known keys with true or false values are read, so a stale key is ignored and never written back.
- The file's folder is created if it does not exist. The file is written in place, with no locking, so two processes saving at once can overwrite each other.

---

## `tests/`

| File | Covers |
|---|---|
| `test_conversation.py` | Answering from indexed files, the empty-index message, each source toggle, memory recording |
| `test_service_headless.py` | `BrisartService` without a display; every service uses a temporary database and settings file |
| `test_session_memory.py` | Adding, compression, de-duplication, limits |
| `test_settings.py` | Defaults, persistence, toggling, corrupt files, stale keys, aliases |
