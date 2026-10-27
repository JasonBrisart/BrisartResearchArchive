# Testing Guide

BrisartSecurityResearch uses three testing layers. Each layer answers a different question, and none establishes cryptographic security.

## 1. Behavioral and boundary tests

File:

```text
tests/test_brisart_security.py
```

Run from the repository root:

```bash
python -m unittest -v tests.test_brisart_security
```

The suite covers implemented behavior including:

- encryption and decryption round trips
- randomized envelope output
- mutation rejection for salt, nonce, ciphertext, and tag
- wrong-key and wrong-context rejection
- malformed envelope fields
- empty plaintext
- hexadecimal encoding and decoding
- deterministic hash behavior
- a basic avalanche observation
- DRBG determinism, reseeding, destruction, and lifecycle behavior

The suite also checks fail-closed boundaries for malformed envelopes, invalid primitive parameters, canonical hexadecimal validation, envelope size limits, DRBG request limits, and DRBG lifecycle boundaries.

## 2. Frozen known-answer regression tests

Files:

```text
tests/test_known_answer_vectors.py
tests/known_answer_vectors.json
```

Run:

```bash
python -m unittest -v tests.test_known_answer_vectors
```

The JSON file contains expected outputs for the hash, MAC, stream generator, DRBG, and complete envelope. The test verifies that the current implementation still produces those exact outputs.

### Vector policy

Do not regenerate vectors before an ordinary test run. Regenerating first would replace the expected answers and could hide an accidental algorithm change.

Run the vector generator only when intentionally changing the algorithm or envelope format:

```bash
python tests/generate_test_vectors.py
```

Review vector changes separately. An intentional vector change should be accompanied by a version decision, documentation update, changelog entry, and fresh research results.

## 3. Configurable research suite

Files:

```text
research/run_research_suite.py
research/research_test_config.json
```

Run:

```bash
python research/run_research_suite.py --config research/research_test_config.json
```

The suite writes:

```text
results/research_test_results.md
results/research_test_results.json
results/research_test_results.csv
```

The configuration controls trial counts, message sizes, deterministic seed, statistical boundaries, output sample size, and benchmark repetitions.

The generated JSON and Markdown reports record:

- Python version and implementation
- operating system and platform release
- Git source revision when available
- configuration SHA-256
- known-answer-vector SHA-256
- check and benchmark summaries
- per-result metrics and runtime

Performance measurements are labeled `BENCHMARK` and are not included in the passed-check count.

## Complete local test sequence

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python research/run_research_suite.py --config research/research_test_config.json
```

## Interpreting results

Behavioral and known-answer passes establish only that the tested implementation behaved as expected for the supplied cases.

Research-suite observations can expose obvious regressions, repeated outputs, poor diffusion, malformed-envelope acceptance, or unexpected local statistics. They do not establish:

- collision resistance
- preimage resistance
- pseudorandomness
- stream indistinguishability
- authentication-forgery resistance
- password-guessing resistance
- side-channel resistance
- production security

Performance measurements are informational, machine-dependent benchmarks. They are not security passes.

## Continuous integration

The GitHub Actions workflow compiles the source, research, and test files, runs the unittest modules, and runs the configurable research suite. The workflow must not regenerate known-answer vectors.

## Updating committed results

Commit fresh reports after a deliberate implementation or configuration change. The report, configuration, source revision, and known-answer vectors should describe the same implementation state.
