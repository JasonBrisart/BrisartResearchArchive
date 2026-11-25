# scripts/

Use these scripts for verification and diagnostics: `run_tests.py` runs the application suite, `debug_offline_replay.py` uses fixed evidence without network access, and `debug_search_replay.py` contacts live providers. All three initialize the external native modules before importing application code.

## `run_tests.py`

```bash
python scripts/run_tests.py                              # everything under brisart_ai/
python scripts/run_tests.py brisart_ai/web/tests -v      # one folder, verbose
python scripts/run_tests.py -k robots                    # tests whose name matches
```

Any argument is passed to pytest unchanged, and `brisart_ai/` is added when none of them names a path. The script puts the project on `sys.path`, finds the native stack, and passes `--import-mode=importlib` and `-p no:cacheprovider` to pytest, which is what lets same-named `tests/` folders coexist without any `__init__.py`. Plain `pytest` or `python -m unittest` from the project root cannot import the native modules by their plain names. The exit status is pytest's. See `docs/TESTING.md`.

---

## `debug_offline_replay.py`

```bash
python scripts/debug_offline_replay.py              # all fixtures
python scripts/debug_offline_replay.py microsoft    # one fixture by name
python scripts/debug_offline_replay.py --list       # names and queries only
```

Builds a temporary index from four small text fixtures, `microsoft`, `transistor`, `cats` and `purr`, runs the real search against it, and prints each result with its score and the boost and penalty signals that applied. Each fixture names the document that should come first. The exit status is non-zero when one does not, and 2 for an unknown fixture name. The temporary index is deleted afterwards, and nothing in the project is written. Four fixtures show the order on those texts only; they say nothing about quality on a real collection.

---

## `debug_search_replay.py`

```bash
python scripts/debug_search_replay.py                              # ten built-in queries
python scripts/debug_search_replay.py --query "who founded apple?" # one query; repeatable
python scripts/debug_search_replay.py --limit 5 --delay 45
```

For each query it prints the natural and keyword forms, the topic terms and detected intent, a trace of which providers answered and which batches were rejected, the accepted and rejected URLs, the final ranking, and a per-URL score breakdown. `--limit` is the number of results (default 5) and `--delay` the seconds waited between queries (default 45). The delay is long because live providers rate-limit; lower it only for a single query. The results change from run to run, and Ctrl+C stops with exit status 130. Nothing is indexed or saved.
