# BrisartSecurityResearch

Dependency-free, pure-Python research into custom cryptographic constructions for offline and air-gapped environments.

> [!WARNING]
> **Experimental research only.** This repository contains a custom cryptographic construction that has not undergone independent cryptanalysis, formal verification, certification, or production security review. Passing the included behavioral, regression, mutation, statistical, or performance tests does not establish cryptographic security. Do not use this project as the sole protection for credentials, personal information, sensitive research, access-control decisions, recovery material, regulated data, or other valuable information.

## Current Status

```text
Project release:          0.3.0-alpha
Release name:             BSR2 Alpha 3
Research implementation: BSR2
Algorithm identifier:     BSR2-ARX-SPONGE-ETM
Envelope version:         2
Maturity:                 Alpha
Production ready:         No
Independently reviewed:   No
Security certified:       No
```

The project release, cryptographic construction, and envelope version are separate identifiers. Release `0.3.0-alpha` remains BSR2 and continues to use envelope version `2`.

## Purpose

BrisartSecurityResearch is a small, inspectable research implementation built with the Python standard library and no third-party packages.

BSR2 includes:

- A custom 1024-bit permutation
- A sponge-style hash construction
- A custom keyed authentication construction
- A password-derived key experiment
- Purpose-separated subkey derivation
- A custom deterministic random-bit generator
- Counter-based stream generation
- A versioned encrypt-then-authenticate envelope
- A separate operating-system entropy boundary for envelope diversification

The core construction and committed fixed parameters are repository-defined. The parameter generator is included for reproducibility. The operating-system entropy source is intentionally external to the custom deterministic construction.

These properties support transparency and auditability. They do not substitute for established cryptographic analysis.

## Alpha 3 Entropy Hardening

BSR2's custom DRBG is deterministic. Recreating the same seed, personalization, context, master key, and initial request sequence can recreate the same raw DRBG output.

Alpha 3 changes how envelope salt and nonce values are produced:

```text
final salt  = custom DRBG salt  XOR fresh operating-system entropy
final nonce = custom DRBG nonce XOR fresh operating-system entropy
```

Fresh entropy is requested through Python's standard-library `secrets.token_bytes()` interface.

This prevents recreation of the custom DRBG state by itself from recreating the final envelope salt, nonce, derived encryption key, stream, ciphertext, and authentication tag during normal operation.

### What Alpha 3 Mitigates

- Reuse of the same custom DRBG seed by itself
- Reuse of the same custom DRBG personalization by itself
- Recreation of the same custom DRBG state by itself
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

## Security Model

BSR2 separates deterministic cryptographic research code from the external entropy boundary.

```text
brisart_security_primitives.py
    Custom permutation, sponge, MAC, KDF experiment, stream generation,
    encoding helpers, and comparison routine

brisart_security_drbg.py
    Custom deterministic generator with reseeding and lifecycle limits

brisart_security_entropy.py
    Fresh operating-system entropy through the Python standard library

brisart_security_envelope.py
    Validated encrypt-then-authenticate envelope combining the DRBG and
    operating-system entropy inputs
```

The entropy module is not a custom entropy source. Software cannot create unpredictable physical entropy from deterministic code alone.

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

### `brisart_security_primitives.py`

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

### `brisart_security_drbg.py`

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

The DRBG expands caller-provided seed material. The DRBG does not create entropy.

### `brisart_security_entropy.py`

Provides the external entropy boundary used during envelope encryption.

The module:

- Requests bytes through `secrets.token_bytes()`
- Requires a positive integer request length
- Checks the returned type and length
- Rejects an all-zero sample
- Rejects a sample equal to the immediately preceding process-local sample
- Raises `BrisartEntropyError` when acquisition or validation fails

The immediate duplicate check is a catastrophic-failure detector. It is not an entropy estimate and does not validate the operating-system entropy source.

### `brisart_security_envelope.py`

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

Encryption:

1. Validates the master key, plaintext, context, and caller-supplied DRBG.
2. Requests deterministic salt and nonce contributions from the custom DRBG.
3. Requests independent fresh entropy contributions from the operating system.
4. Combines each pair using XOR.
5. Derives separate encryption and authentication keys.
6. Generates the stream and transforms the plaintext.
7. Authenticates the algorithm, version, context, salt, nonce, and ciphertext.

Decryption:

1. Validates the exact field set, metadata types, format identifier, encoding, field lengths, context size, and ciphertext size.
2. Derives the encryption and authentication keys from the stored message salt.
3. Verifies authentication before returning plaintext.
4. Rejects wrong keys, wrong contexts, malformed envelopes, and modified authenticated fields.

## Validation

Run all commands from the repository root.

### Compile

```bash
python -m py_compile     brisart_security_primitives.py     brisart_security_drbg.py     brisart_security_entropy.py     brisart_security_envelope.py     research/run_research_suite.py     tools/generate_bsr2_parameters.py     tests/generate_test_vectors.py     tests/test_brisart_security.py     tests/test_bsr2_parameters.py     tests/test_entropy_hardening.py     tests/test_known_answer_vectors.py
```

### Run Unit And Regression Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The required ending is:

```text
OK
```

### Run The Research Suite

```bash
python research/run_research_suite.py
```

The research suite writes:

```text
results/research_test_results.md
results/research_test_results.json
results/research_test_results.csv
```

Research-suite observations and benchmarks do not establish cryptographic security.

## Entropy-Hardening Tests

`tests/test_entropy_hardening.py` verifies the specific Alpha 3 mitigation, including:

- Identical custom DRBG initialization does not repeat final envelope values during normal operation
- The demonstrated known-plaintext XOR recovery no longer recovers the second plaintext
- Entropy-source failure stops encryption
- All-zero entropy samples are rejected
- Consecutive duplicate samples are rejected
- Controlled deterministic entropy injection remains restricted to tests

These tests verify the implemented mitigation. They do not validate the operating-system entropy source.

## Known-Answer Vector Policy

Known-answer vectors freeze deterministic behavior. Do not regenerate them before an ordinary regression run.

Production envelope generation uses fresh operating-system entropy. Envelope vector tests inject a controlled all-zero entropy contribution strictly inside the test environment so the underlying deterministic BSR2 envelope logic remains reproducible.

The test-only zero contribution is not used during normal encryption.

Run the vector generator only after an intentional algorithm or format change:

```bash
python tests/generate_test_vectors.py
```

Any intentional vector change should be reviewed together with versioning, documentation, changelog entries, and fresh research results.

## Parameter Provenance

[`docs/BSR2_PARAMETER_GENERATION.md`](docs/BSR2_PARAMETER_GENERATION.md) documents the deterministic parameter generator and public seed used to produce the fixed BSR2 parameters.

`tests/test_bsr2_parameters.py` verifies that regenerated parameters match the values embedded in `brisart_security_primitives.py`.

Reproducible parameter generation documents provenance. It does not establish cryptographic strength.

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
- Parser and tamper-handling research
- Regression testing
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

## Security Claims

The project does not claim:

- Equivalence to AES, ChaCha20, SHA-2, SHA-3, HMAC, PBKDF2, Argon2, or another standardized construction
- Collision or preimage resistance
- Stream indistinguishability
- Authentication-forgery resistance
- Differential, rotational, algebraic, or related-key resistance
- Validation of the operating-system entropy source
- State-compromise recovery
- Side-channel resistance
- Protection from complete machine-state rollback
- Production suitability

See [`SECURITY.md`](SECURITY.md) for the project security posture.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) describes the implemented construction and security boundaries.
- [`docs/BSR2_PARAMETER_GENERATION.md`](docs/BSR2_PARAMETER_GENERATION.md) documents fixed-parameter generation.
- [`docs/TESTING.md`](docs/TESTING.md) explains validation layers and vector policy.
- [`SECURITY.md`](SECURITY.md) defines the project security posture.
- [`CHANGELOG.md`](CHANGELOG.md) records release history and the Alpha 3 entropy hardening.

## Licensing

This project is part of the Brisart ecosystem. Current licensing terms and ecosystem policies are maintained through the BrisartLicensing project. See [`LICENSE`](LICENSE).
