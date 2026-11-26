# Scripts

This folder contains developer utilities used to test and diagnose BrisartAI. These scripts are not part of the normal desktop question-answering path.

## Developer commands

- `run_tests.py`: Bootstraps the project test environment and invokes pytest.
- `debug_offline_replay.py`: Replays local retrieval and answer fixtures for diagnosis.
- `benchmark_retrieval.py`: Runs pinned retrieval comparisons and timing measurements in supported development environments.
- `benchmark_data/`: Contains the fixed inputs and recorded results for the historical 1.4.0 comparison.

## Benchmark boundaries

Optional comparator packages used by development benchmarks are not BrisartAI runtime dependencies. The [testing record](../docs/TESTING.md) distinguishes historical comparisons from the current 1.6.0 judged-query results and documents what was actually executed.
