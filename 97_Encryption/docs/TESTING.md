# Testing Guide

BrisartSecurityResearch uses four testing layers.

Each layer answers a different question.

Passing results establish only the behavior that was actually tested.

Passing results do not establish cryptographic security.

---

## 1. Behavioral And Boundary Tests

File:

```text
tests/test_brisart_security.py
```

Run:

```bash
python -m unittest -v tests.test_brisart_security
```

This suite covers:

- Round-trip encryption/decryption
- Randomized envelopes
- Tamper rejection
- Wrong-key rejection
- Wrong-context rejection
- Envelope validation
- Primitive boundary checks
- Generator validation
- DRBG lifecycle behavior

### Generator Validation

The suite verifies that encryption rejects:

- Generators without a callable `generate()` method
- Salt values that are not bytes
- Nonce values that are not bytes
- Salt values that are not exactly 32 bytes
- Nonce values that are not exactly 32 bytes
- Equal salt and nonce values

### Deterministic Restart Demonstration

The suite also demonstrates that two fresh DRBG instances created with identical inputs reproduce the same first envelope sequence.

This records an operational risk.

It is not a desired randomness property.

---

## 2. Parameter Reproducibility Tests

File:

```text
tests/test_bsr2_parameters.py
```

Run:

```bash
python -m unittest -v tests.test_bsr2_parameters
```

These tests regenerate BSR2 parameters and compare them with the values embedded in:

```text
brisart_security_primitives.py
```

They also verify:

- Parameter counts
- Uniqueness requirements
- Rotation bounds
- Permutation shape

---

## 3. Frozen Known-Answer Regression Tests

Files:

```text
tests/test_known_answer_vectors.py
tests/known_answer_vectors.json
```

Run:

```bash
python -m unittest -v tests.test_known_answer_vectors
```

The vector file contains expected outputs for:

- Hashing
- MAC generation
- Stream generation
- DRBG output
- Complete envelope generation

The suite also verifies:

```text
Format version: 2
Algorithm: BSR2-ARX-SPONGE-ETM
Envelope version: 2
```

### Vector Policy

Do not regenerate vectors before an ordinary regression run.

Doing so could replace expected answers and hide an unintended algorithm change.

Only regenerate vectors when intentionally changing:

- The algorithm
- The envelope format
- The expected outputs

Regeneration command:

```bash
python tests/generate_test_vectors.py
```

Any intentional vector change should be accompanied by:

- Documentation updates
- Changelog updates
- Version review
- Fresh research results

---

## 4. Configurable Research Suite

Files:

```text
research/run_research_suite.py
research/research_test_config.json
```

Run:

```bash
python research/run_research_suite.py
```

or

```bash
python research/run_research_suite.py --config research/research_test_config.json
```

Generated reports:

```text
results/research_test_results.md
results/research_test_results.json
results/research_test_results.csv
```

The configuration controls:

- Trial counts
- Message sizes
- Statistical boundaries
- Deterministic seed
- Output sample sizes
- Benchmark repetitions

Performance measurements are labeled:

```text
BENCHMARK
```

and are excluded from the pass/fail count.

---

## Complete Validation Sequence

Run from the repository root.

### Compile

```bash
python -m py_compile \
    brisart_security_primitives.py \
    brisart_security_drbg.py \
    brisart_security_envelope.py \
    research/run_research_suite.py \
    tools/generate_bsr2_parameters.py \
    tests/generate_test_vectors.py \
    tests/test_brisart_security.py \
    tests/test_bsr2_parameters.py \
    tests/test_known_answer_vectors.py
```

### Unit Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Research Suite

```bash
python research/run_research_suite.py
```

Success is determined by:

```text
OK
```

from unittest and the absence of:

```text
FAIL
ERROR
```

from the research suite.

Do not rely on a fixed test count because the suite may grow over time.

---

## Interpreting Results

Passing tests establish only that the implementation behaved as expected for the supplied inputs.

Passing tests do not establish:

- Collision resistance
- Preimage resistance
- Pseudorandomness
- Stream indistinguishability
- Authentication-forgery resistance
- Side-channel resistance
- Production security

---

## Continuous Integration

The GitHub Actions workflow:

1. Compiles source files
2. Compiles research files
3. Compiles tool files
4. Compiles test files
5. Runs unittest discovery
6. Runs the research suite

The workflow does not regenerate known-answer vectors.

---

## Updating Committed Results

Commit fresh research reports after a deliberate implementation or configuration change.

The following should describe the same implementation state:

- Source code
- Configuration
- Research results
- Known-answer vectors
- Fixed parameters
- Changelog entries