# Testing BrisartAI

Run tests from the project root using `python scripts/run_tests.py`. The runner adds the project directory, loads the external native stack, and uses pytest importlib mode to collect co-located tests without adding package initializers.

## Layout

```
brisart_ai/
├── tests/               100 tests  -- util, blocklist, intent, version_info, native_path, state, and the project layout rules
├── io/tests/              49 tests  -- all 4 io/ modules
├── core/tests/            32 tests  -- conversation, session_memory, settings, service (headless)
├── knowledge/tests/       86 tests  -- all 6 knowledge/ modules
├── web/tests/             71 tests  -- all 6 web/ modules, including the public-fetch redirect policy
└── ui/tests/               8 tests  -- theme.py (the only Tk-free UI module)
```

## Running the tests

Use the runner. The project root holds only `run.py`, `cli.py` and `version.py`, so there is no root `pytest.ini` or `conftest.py`; `scripts/run_tests.py` does what they would do. It puts the project root on `sys.path`, calls `native_path.install()` so the flat `brisart_*` imports resolve (see `docs/ARCHITECTURE.md` §7), and runs pytest with `--import-mode=importlib`:

```bash
python scripts/run_tests.py
```

Any other argument goes straight to pytest, and `brisart_ai/` is added when none of them names a path:

```bash
python scripts/run_tests.py brisart_ai/tests/test_native_path.py
python scripts/run_tests.py brisart_ai/knowledge/tests/test_ranker.py -v
python scripts/run_tests.py -k robots
```

The runner needs `pytest` installed; nothing else in the project does.

### Why pytest, and why `--import-mode=importlib`

`unittest discover`'s built-in recursive discovery requires every intermediate directory to have an `__init__.py` to be walked into as a package. Since `brisart_ai/`'s subfolders are deliberately namespace packages with **no** `__init__.py`, `unittest discover` run from the project root silently finds **zero** tests.

`pytest` doesn't have that restriction and discovers test files by path directly. With its default "prepend" import mode, a test file in a folder without `__init__.py` is imported under its bare file name after its folder is put on `sys.path`, so two test files with the same name in different `tests/` folders collide, and the folders themselves become importable by accident. `--import-mode=importlib` (passed by the runner) imports each file by its literal path instead, so neither can happen.

Use the project runner so the external native stack is configured before pytest imports application tests.

## What's covered, and what's deliberately out of scope

The native modules and their own tests are maintained outside Offline_AI.
- **`brisart_ai/web/search.py` and `crawler.py`** — all pure-logic helpers (URL decoding/unwrapping, tracking-parameter stripping, query cleaning, scoring, ranking, partitioning) are tested directly. The actual HTTP-calling provider functions are **not** exercised, since hitting live search engines from a test suite would be flaky and could itself trigger the rate-limiting/challenge-page behavior those functions exist to detect. `fetch_url()` is tested only for its error-handling paths using a non-routable address (`198.51.100.1`, reserved by RFC 5737) so no real network dependency is required.
- **`brisart_ai/ui/`** — `theme.py` (pure constants, no Tk import) is tested headlessly. `app.py`, `chat_panel.py`, `dialogs.py`, and `sidebar.py` all construct real `tkinter` widgets and require a live display; they are verified by manually running the application instead. `BrisartService`, which the GUI and `cli.py` share, lives in `core/service.py` and is tested in `core/tests/`.
- **`native_path.py`** — covered by `brisart_ai/tests/test_native_path.py` against temporary directory layouts, not against the real Archive checkout.
- **`state.py`** — covered by `brisart_ai/tests/test_state.py`: per-platform folders from supplied environments, the one-time move (including rows still in the write-ahead log, files that already exist, an empty index left by a failed start, a corrupt index, an unwritable target, an abandoned lock, and four processes started together), and child-process runs of a copy of `cli.py` with `HOME`, `APPDATA` and `XDG_CONFIG_HOME` redirected. Windows file locking is not exercised.
- **Project layout** — `brisart_ai/tests/test_layout.py` fails if the root holds any file other than `run.py`, `cli.py` and `version.py`, if a `data/` folder, `research_settings.json` or `.sqlite3` file is inside the project, or if any `__init__.py` exists.
- Every test that touches SQLite (`Index`, `SessionMemory`, vault functions, `BrisartService`) uses a fresh `tempfile.TemporaryDirectory()` per test, so tests never share state through the filesystem and can run in any order.

## A note on saved state

`ResearchSettings()` and `Index()` default to the per-user state folder (`brisart_ai/state.py`). That is the intended production behavior, but a test that used the defaults would rewrite the developer's own saved settings and index; the suite once did exactly that to the old project-folder settings file, leaving `search_notes` switched off. `BrisartService` therefore takes an optional `settings_path`, and every test passes paths inside its own `tempfile.TemporaryDirectory()`. See `_make()` in `brisart_ai/core/tests/test_service_headless.py` for the pattern, and `_clean_env()` in `test_state.py` for how a child process is kept away from the real folder.
