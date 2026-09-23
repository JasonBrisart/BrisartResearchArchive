# BrisartSecurityResearch

Dependency-free, pure-Python research into custom cryptographic constructions for offline and air-gapped environments.

> [!WARNING]
> **Experimental research only.** This repository contains a custom cryptographic construction that has not undergone independent cryptanalysis, formal verification, certification, or production security review. Passing the included behavioral, regression, mutation, statistical, or performance tests does not establish cryptographic security. Do not use this project as the sole protection for credentials, personal information, sensitive research, access-control decisions, recovery material, regulated data, or other valuable information.

## Current Status

```text
Project release:           0.3.0-alpha
Release name:              BSR2 Alpha 3
Research implementation:   BSR2
Algorithm identifier:      BSR2-ARX-SPONGE-ETM
Envelope version:          2
Maturity:                  Alpha
Research focus:            Architecture and experimental validation
Production ready:          No
Independently reviewed:    No
Security certified:        No
```

The project release, cryptographic construction, and envelope version are separate identifiers.

Release `0.3.0-alpha` remains BSR2 and continues to use envelope version `2`.

## Architecture Overview

BSR2 is intentionally divided into three separate layers:

1. Deterministic cryptographic research components
2. Operating-system entropy boundary
3. Authenticated envelope layer

The deterministic layer performs transformation, hashing, authentication, key derivation, and deterministic expansion.

The operating-system entropy layer provides fresh entropy through Python's standard-library interfaces.

The authenticated envelope layer combines deterministic BSR2 outputs with fresh operating-system entropy contributions to produce authenticated ciphertext containers.

The operating-system entropy source remains external to the custom deterministic construction.

```text
                +----------------------+
                |   BSR2 Primitives    |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |      BSR2 DRBG       |
                +----------+-----------+
                           |
                           v
              +------------------------+
              |  BSR2 Envelope Layer   |
              +-----------+------------+
                          ^
                          |
            +-------------+--------------+
            |   OS Entropy Boundary      |
            |   secrets.token_bytes()    |
            +----------------------------+
```

The deterministic construction and operating-system entropy boundary are independent components.

The authenticated envelope combines both during encryption.

## Purpose

BrisartSecurityResearch is a small, inspectable research implementation built with the Python standard library and no third-party packages.

The project is designed for controlled experimentation, implementation review, reproducible testing, and offline or air-gapped research workflows.

Transparency and auditability are core goals. They do not substitute for established cryptographic analysis, independent review, or standardized cryptographic constructions.

## BSR2 Research Components

### Deterministic Components

- Custom 1024-bit permutation
- Sponge-style hash construction
- Custom keyed authentication construction
- Password-derived key experiment
- Purpose-separated subkey derivation
- Custom deterministic random-bit generator
- Counter-based stream generation

The deterministic construction is implemented primarily in:

- brisart_security_primitives.py
- [`brisart_security_drbg.py`](brisart_security_drbg.py)

### Operating-System Entropy Boundary

- Fresh entropy acquisition through the Python standard library
- Entropy sample validation
- Envelope salt and nonce diversification
- Failure handling through a dedicated entropy error type

The operating-system entropy boundary is implemented in:

- brisart_security_entropy.py

### Authenticated Envelope Layer

- Versioned encrypt-then-authenticate envelope
- Separate encryption and authentication keys
- Context binding
- Authentication verification before plaintext return
- Exact field-set and metadata validation
- Salt and nonce diversification

The authenticated envelope layer is implemented in:

- brisart_security_envelope.py

The core construction and committed fixed parameters are repository-defined.

The parameter generator is included for reproducibility:

- tools/generate_bsr2_parameters.py

The operating-system entropy source is intentionally external to the custom deterministic construction.

## Alpha 3 Entropy Hardening

BSR2's custom DRBG is deterministic.

Recreating the same seed, personalization, context, master key, and initial request sequence can recreate the same raw DRBG output.

Alpha 3 changes how envelope salt and nonce values are produced:

```text
final salt  = custom DRBG salt  XOR fresh operating-system entropy
final nonce = custom DRBG nonce XOR fresh operating-system entropy
```

Fresh entropy is requested through Python's standard-library `secrets.token_bytes()` interface and is obtained through:

- brisart_security_entropy.py

The authenticated envelope combines deterministic DRBG outputs with fresh operating-system entropy contributions.

This prevents recreation of the custom DRBG state by itself from recreating the final envelope salt, nonce, derived encryption key, stream, ciphertext, and authentication tag during normal operation.

### What Alpha 3 Mitigates

- Reuse of the same custom DRBG seed by itself
- Reuse of the same custom DRBG personalization by itself
- Recreation of the same custom DRBG state by itself
- Recreation of the same raw deterministic salt and nonce contributions by itself
- The demonstrated known-plaintext XOR recovery caused by recreating the same stream

### What Alpha 3 Does Not Guarantee

Alpha 3 does not guarantee uniqueness if an attacker reproduces the complete machine state, including:

- The master key
- Application state
- Custom DRBG state
- Persistent state
- Virtual-machine or system snapshot state
- Operating-system randomness state

No process-local Python implementation can guarantee protection from a complete rollback of every relevant state source.

The custom DRBG expands caller-provided seed material but does not create entropy.

The operating-system entropy boundary remains intentionally separate from the custom deterministic construction.

Software cannot create unpredictable physical entropy from deterministic code alone.

## Security Model

BSR2 separates deterministic cryptographic research code from the external operating-system entropy boundary.

```text
brisart_security_primitives.py
    Custom permutation, sponge, MAC, KDF experiment, stream generation,
    encoding helpers, and comparison routine

brisart_security_drbg.py
    Custom deterministic generator with reseeding and lifecycle limits

brisart_security_entropy.py
    Fresh operating-system entropy through the Python standard library

brisart_security_envelope.py
    Validated encrypt-then-authenticate envelope combining deterministic
    DRBG contributions with operating-system entropy contributions
```

The corresponding source files are:

- brisart_security_primitives.py
- [`brisart_security_drbg.py`](brisart_security_drbg.py)
- brisart_security_entropy.py
- brisart_security_envelope.py

The entropy module is not a custom entropy source.

The module requests entropy from the operating system through Python's standard-library interface and validates the returned sample before use.

The custom deterministic construction remains inspectable and reproducible, while final production envelope diversification depends on an external operating-system entropy source.

## Repository Layout

```text
BrisartSecurityResearch/
├── .github/
│   └── workflows/
│       └── tests.yml
├── docs/
│   ├── BSR2_PARAMETER_GENERATION.md
│   ├── DESIGN.md
│   └── TESTING.md
├── research/
│   ├── research_test_config.json
│   └── run_research_suite.py
├── results/
│   ├── research_test_results.csv
│   ├── research_test_results.json
│   └── research_test_results.md
├── tests/
│   ├── generate_test_vectors.py
│   ├── known_answer_vectors.json
│   ├── test_brisart_security.py
│   ├── test_bsr2_parameters.py
│   ├── test_entropy_hardening.py
│   ├── test_envelope_hardening.py
│   └── test_known_answer_vectors.py
├── tools/
│   └── generate_bsr2_parameters.py
├── .gitignore
├── brisart_security_drbg.py
├── brisart_security_entropy.py
├── brisart_security_envelope.py
├── brisart_security_primitives.py
├── CHANGELOG.md
├── LICENSE
├── README.md
└── SECURITY.md
```

## Core Implementation

### brisart_security_primitives.py

Contains:

- The BSR2 fixed parameters
- The custom permutation
- Sponge-style hashing
- Keyed authentication
- Password-derived key experimentation
- Purpose-separated subkey derivation
- Counter-based stream generation
- XOR transformation
- A comparison routine without an intentional early return
- Canonical lowercase hexadecimal encoding and decoding

### [`brisart_security_drbg.py`](brisart_security_drbg.py)

Contains the custom deterministic generator.

The DRBG requires:

- At least 64 seed bytes
- At least 16 personalization bytes
- Non-empty additional input for every request

The current limits include:

```text
Maximum request:             1 MiB
Output before reseed:       16 MiB
Requests before reseed:    100,000
```

The DRBG expands caller-provided seed material.

The DRBG does not create entropy.

### brisart_security_entropy.py

Provides the external entropy boundary used during envelope encryption.

The module:

- Requests bytes through `secrets.token_bytes()`
- Requires a positive integer request length
- Checks the returned type
- Checks the returned length
- Rejects an all-zero sample
- Rejects a sample equal to the immediately preceding process-local sample
- Raises `BrisartEntropyError` when acquisition or validation fails

The immediate duplicate check is a catastrophic-failure detector.

It is not an entropy estimate and does not validate the operating-system entropy source.

### brisart_security_envelope.py

Contains the authenticated BSR2 envelope.

The envelope contains exactly:

```text
algorithm
version
salt
nonce
ciphertext
tag
```

#### Encryption

1. Validates the master key, plaintext, context, and caller-supplied DRBG.
2. Requests deterministic salt and nonce contributions from the custom DRBG.
3. Requests independent fresh entropy contributions from the operating system.
4. Combines each deterministic contribution with its corresponding operating-system entropy contribution using XOR.
5. Derives separate encryption and authentication keys.
6. Generates the stream and transforms the plaintext.
7. Authenticates the algorithm, version, context, salt, nonce, and ciphertext.

#### Decryption

1. Validates the exact field set, metadata types, format identifier, encoding, field lengths, context size, and ciphertext size.
2. Derives the encryption and authentication keys from the stored message salt.
3. Verifies authentication before returning plaintext.
4. Rejects wrong keys, wrong contexts, malformed envelopes, and modified authenticated fields.

## Validation

Run all commands from the repository root.

The continuous-integration configuration is available in:

- [`.github/workflows/tests.yml`](.github/workflows/tests.yml)

### Compile

#### Linux, macOS, or a POSIX-Compatible Shell

```bash
python -m py_compile \
    brisart_security_primitives.py \
    brisart_security_drbg.py \
    brisart_security_entropy.py \
    brisart_security_envelope.py \
    research/run_research_suite.py \
    tools/generate_bsr2_parameters.py \
    tests/generate_test_vectors.py \
    tests/test_brisart_security.py \
    tests/test_bsr2_parameters.py \
    tests/test_entropy_hardening.py \
    tests/test_envelope_hardening.py \
    tests/test_known_answer_vectors.py
```

#### Windows Command Prompt or PowerShell

```bat
python -m py_compile brisart_security_primitives.py brisart_security_drbg.py brisart_security_entropy.py brisart_security_envelope.py research/run_research_suite.py tools/generate_bsr2_parameters.py tests/generate_test_vectors.py tests/test_brisart_security.py tests/test_bsr2_parameters.py tests/test_entropy_hardening.py tests/test_envelope_hardening.py tests/test_known_answer_vectors.py
```

### Run Unit And Regression Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The required ending is:

```text
OK
```

The primary behavioral and boundary tests are located in:

- tests/test_brisart_security.py

### Run The Research Suite

```bash
python research/run_research_suite.py
```

The research suite is implemented in:

- research/run_research_suite.py

Its default configuration is stored in:

- research/research_test_config.json

The research suite writes:

- results/research_test_results.md
- results/research_test_results.json
- results/research_test_results.csv

Research-suite observations and benchmarks do not establish cryptographic security.

## Entropy-Hardening Tests

tests/test_entropy_hardening.py verifies the specific Alpha 3 mitigation, including:

- Identical custom DRBG initialization does not repeat final envelope values during normal operation
- The demonstrated known-plaintext XOR recovery no longer recovers the second plaintext
- Entropy-source failure stops encryption
- All-zero entropy samples are rejected
- Consecutive duplicate samples are rejected
- Controlled deterministic entropy injection remains restricted to tests

These tests verify the implemented mitigation.

They do not validate the operating-system entropy source.

They do not establish the security of the underlying custom cryptographic construction.

## Envelope-Hardening Tests

tests/test_envelope_hardening.py provides focused boundary tests for defensive envelope hardening.

The tests cover:

- Generator-failure wrapping
- Oversized encryption and decryption contexts
- Context values that cannot be encoded as valid UTF-8
- Non-text algorithm identifiers
- Invalid envelope-version types
- Oversized ciphertext rejection before hexadecimal decoding
- Invalid fixed-field lengths before hexadecimal decoding
- Unchanged behavior for valid envelopes

These tests validate failure behavior and resource boundaries.

They do not establish cryptographic security.

## Known-Answer Vector Policy

Known-answer vectors freeze deterministic behavior.

Do not regenerate them before an ordinary regression run.

The committed vectors are stored in:

- tests/known_answer_vectors.json

The corresponding tests are located in:

- tests/test_known_answer_vectors.py

Production envelope generation uses fresh operating-system entropy.

Envelope vector tests inject a controlled all-zero entropy contribution strictly inside the test environment so the underlying deterministic BSR2 envelope logic remains reproducible.

The test-only zero contribution is not used during normal encryption.

Run the vector generator only after an intentional algorithm or format change:

```bash
python tests/generate_test_vectors.py
```

The vector generator is located at:

- tests/generate_test_vectors.py

Any intentional vector change should be reviewed together with:

- Versioning
- Documentation
- Changelog entries
- Compatibility implications
- Fresh research results

## Parameter Provenance

[`docs/BSR2_PARAMETER_GENERATION.md`](docs/BSR2_PARAMETER_GENERATION.md) documents the deterministic parameter generator and public seed used to produce the fixed BSR2 parameters.

The parameter-generation tool is located at:

- tools/generate_bsr2_parameters.py

Parameter reproducibility is verified by:

- tests/test_bsr2_parameters.py

The regenerated parameters are compared with the values embedded in:

- brisart_security_primitives.py

Reproducible parameter generation documents provenance.

It does not establish cryptographic strength.

## Research Configuration And Results

The configurable research suite is implemented in:

- research/run_research_suite.py

Its default configuration is stored in:

- research/research_test_config.json

Committed research results are available in:

- results/research_test_results.md
- results/research_test_results.json
- results/research_test_results.csv

The committed reports document observed behavior and local benchmarks for the implementation state under which they were generated.

They do not establish cryptographic security, production suitability, or resistance to cryptanalysis.

## Compatibility

- Existing BSR2 version 2 envelopes remain decryptable because decryption uses the salt and nonce stored in each envelope.
- The algorithm identifier remains `BSR2-ARX-SPONGE-ETM`.
- The envelope version remains `2`.
- The six-field envelope structure remains unchanged.
- BSR2 remains intentionally incompatible with BSR1 ciphertext, vectors, domains, parameters, and envelope metadata.
- Retain the frozen BSR1 archive separately if historical BSR1 material must be inspected or recovered.

## Appropriate Uses

- Controlled cryptographic research
- Source-code inspection
- Synthetic or disposable data
- Offline workflow prototypes
- Air-gapped workflow prototypes
- Parser and tamper-handling research
- Regression testing
- Reproducibility testing
- Educational analysis of custom constructions

## Unsupported Uses

Do not rely on this repository as the sole protection for:

- Passwords or credentials
- API keys or access tokens
- Identity records
- Recovery secrets
- Personal or regulated information
- Valuable unpublished research
- Production authorization
- Safety-critical systems
- Production security systems

## Security Claims

The project does not claim:

- Equivalence to AES, ChaCha20, SHA-2, SHA-3, HMAC, PBKDF2, Argon2, or another standardized construction
- Collision resistance
- Preimage resistance
- Stream indistinguishability
- Authentication-forgery resistance
- Differential resistance
- Rotational resistance
- Algebraic resistance
- Related-key resistance
- Validation of the operating-system entropy source
- State-compromise recovery
- Side-channel resistance
- Protection from complete machine-state rollback
- Production suitability

Passing the included tests does not establish any of these properties.

See [`SECURITY.md`](SECURITY.md) for the complete project security posture.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) describes the implemented construction and security boundaries.
- [`docs/BSR2_PARAMETER_GENERATION.md`](docs/BSR2_PARAMETER_GENERATION.md) documents fixed-parameter generation.
- [`docs/TESTING.md`](docs/TESTING.md) explains validation layers and vector policy.
- [`SECURITY.md`](SECURITY.md) defines the project security posture.
- [`CHANGELOG.md`](CHANGELOG.md) records release history and the Alpha 3 entropy hardening.
- [`.github/workflows/tests.yml`](.github/workflows/tests.yml) defines the continuous-integration test workflow.

## Licensing

This project is part of the Brisart ecosystem.

Current licensing terms and ecosystem policies are maintained through the BrisartLicensing project.

See [`LICENSE`](LICENSE).
