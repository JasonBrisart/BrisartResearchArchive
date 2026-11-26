# Scripts

This folder contains developer utilities used to test and diagnose BrisartAI. These scripts are not part of the normal desktop question-answering path.

## Developer commands

- `run_tests.py`: Bootstraps the project test environment and invokes pytest.
- `debug_offline_replay.py`: Replays local retrieval and answer fixtures for diagnosis.
- `benchmark_retrieval.py`: Runs pinned retrieval comparisons and timing measurements in supported development environments.
- `benchmark_data/`: Contains the fixed inputs and recorded results for the historical 1.4.0 comparison.

## Benchmark boundaries

Optional comparator packages used by development benchmarks are not BrisartAI runtime dependencies. The [testing record](../docs/TESTING.md) distinguishes historical comparisons from the current 1.6.0 judged-query results and documents what was actually executed.

## Running development checks

The test runner prepares the project environment and delegates assertions to the existing test modules. It should be used with the first-party Native API helpers available to both the parent process and spawned workers. A test harness that injects modules only into the parent process cannot establish correct spawned-process integration.

The offline replay utility is useful when a question retrieves an irrelevant passage or omits a citation. Its fixtures should distinguish the expected source, expected excerpt, and acceptable missing-evidence behavior rather than treating any keyword match as success.

## Interpreting benchmarks

The retrieval benchmark uses pinned queries so changes can be compared against a stable workload. Historical comparator results and newer judged-query results differ in corpus size, environment, and metrics; they should not be combined into one performance claim.

Top-1 accuracy measures whether the first returned file is the judged target. It does not establish that the answer formatter quoted the correct passage, that every contradiction was found, or that latency will remain similar with a large real archive. Refer to `docs/TESTING.md` for exact counts, methodology, and known gaps.
