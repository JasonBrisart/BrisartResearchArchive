# Developer tools

- `run_tests.py` bootstraps external imports and executes co-located pytest tests.
- `debug_offline_replay.py` runs local ranking and answer fixtures.
- `benchmark_retrieval.py` runs one Linux comparison mode at a time. `benchmark_data/` preserves the pinned queries and six recorded result sets for the 1.4.0 benchmark. See [testing and reproduction](../docs/TESTING.md) for staging and interpretation. Comparator packages are not application dependencies.
