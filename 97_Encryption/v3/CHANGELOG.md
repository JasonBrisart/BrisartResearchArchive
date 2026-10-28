# Changelog

All notable project-level changes to BrisartSecurityResearch are recorded in this document.

This repository contains experimental research software. A changelog entry records implementation history and design evolution. It does not imply cryptographic validation, certification, production approval, or security guarantees.

## 0.3.0-alpha

### BSR2 Alpha 3

Release status:

```text
Current experimental release
```

This release hardens BSR2 against the demonstrated deterministic-generator restart and state-reuse attack under normal operating-system conditions. It introduces an explicit operating-system entropy boundary while retaining the custom deterministic BSR2 construction.

### Added

#### Operating-System Entropy Boundary

Added:

```text
brisart_security_entropy.py
```

The new module:

- Requests fresh entropy through Python's standard-library `secrets.token_bytes()` interface.
- Requires a positive integer request length.
- Verifies that the returned value is `bytes`.
- Verifies that the returned value has the requested length.
- Rejects an all-zero sample.
- Rejects a sample identical to the immediately preceding sample.
- Uses a lock to protect the process-local previous-sample check.
- Raises `BrisartEntropyError` when entropy acquisition or validation fails.

The immediate duplicate-sample check is a catastrophic-failure detector. It is not an entropy estimate and does not validate the operating-system entropy source.

#### Entropy Hardening Tests

Added:

```text
tests/test_entropy_hardening.py
```

The new tests verify that:

- Fresh BSR2 DRBG instances created from identical deterministic inputs no longer produce identical envelopes during normal operation.
- Identical deterministic DRBG state no longer reproduces the final envelope salt and nonce by itself.
- The previously demonstrated known-plaintext XOR recovery no longer recovers the second plaintext under normal operation.
- Operating-system entropy failure stops encryption.
- All-zero entropy samples are rejected.
- Consecutive duplicate entropy samples are rejected.
- Deterministic entropy injection remains available strictly inside controlled regression tests.

### Changed

#### Envelope Diversification

Updated:

```text
brisart_security_envelope.py
```

Envelope encryption now combines two independent inputs for each message salt and nonce:

```text
custom DRBG output XOR fresh operating-system entropy
```

The custom BSR2 DRBG remains deterministic. The operating-system entropy contribution prevents recreation of the custom DRBG state by itself from recreating the same final salt, nonce, derived encryption key, stream, ciphertext, and authentication tag.

The envelope continues to use:

```text
Algorithm: BSR2-ARX-SPONGE-ETM
Envelope version: 2
```

The envelope field structure remains:

```text
algorithm
version
salt
nonce
ciphertext
tag
```

#### Envelope Validation

The envelope implementation now also:

- Limits encoded context data to 4,096 bytes.
- Rejects context strings that cannot be encoded as UTF-8.
- Requires an exact integer envelope version and rejects boolean version values.
- Requires a textual algorithm identifier.
- Checks fixed hexadecimal field lengths before decoding.
- Checks the ciphertext size before decoding.
- Wraps custom DRBG failures in `BrisartEnvelopeError`.
- Wraps entropy-source failures in `BrisartEnvelopeError`.
- Rejects equal raw generator salt and nonce values.
- Rejects equal diversified salt and nonce values.
- Continues to authenticate metadata and ciphertext before returning plaintext.

#### Known-Answer Vector Testing

Updated:

```text
tests/test_known_answer_vectors.py
tests/generate_test_vectors.py
```

Production envelope encryption now uses nondeterministic operating-system entropy. Deterministic envelope regression testing therefore injects an all-zero entropy contribution strictly inside the test environment.

XOR with the controlled zero contribution preserves the existing deterministic envelope vector and allows the underlying BSR2 envelope logic to remain reproducible.

The test-only zero contribution is not used during normal encryption.

#### Continuous Integration

Updated:

```text
.github/workflows/tests.yml
```

The workflow now compiles and tests:

- `brisart_security_entropy.py`
- `tests/test_entropy_hardening.py`
- The existing BSR2 implementation, parameter, vector, and research files

### Security Impact

Before this release, recreating the same custom DRBG seed, personalization, context, master key, and initial request sequence could recreate the same salt, nonce, encryption subkey, and stream.

That allowed the demonstrated relation:

```text
ciphertext_1 XOR ciphertext_2 XOR known_plaintext_1
```

to recover the corresponding portion of a second plaintext when the same stream was reused.

In Alpha 3, recreation of the custom DRBG state alone is no longer sufficient to recreate the final envelope salt and nonce during normal operation because each value also includes fresh operating-system entropy.

### Security Boundary

This mitigation depends on the operating-system randomness service exposed through Python's standard-library `secrets` module.

It does not guarantee uniqueness if an attacker reproduces the entire machine state, including:

- The master key
- Application state
- Custom DRBG state
- Persistent state
- Virtual-machine or system snapshot state
- Operating-system randomness state

No process-local Python implementation can guarantee protection from a complete rollback of every relevant state source.

### Compatibility

- Existing BSR2 version 2 envelopes remain decryptable because decryption uses the salt and nonce stored in each envelope.
- The algorithm identifier remains `BSR2-ARX-SPONGE-ETM`.
- The envelope version remains `2`.
- The envelope field set remains unchanged.
- Existing deterministic primitive, stream, DRBG, and envelope vectors remain usable with the controlled entropy injection in regression tests.
- BSR2 remains intentionally incompatible with historical BSR1 ciphertext, vectors, domains, parameters, and envelope metadata.

### Validation Status

The Alpha 3 hardening tests exercise the specific deterministic-restart mitigation and entropy failure behavior.

Passing these tests does not establish:

- Cryptographic security of the custom construction
- Validation of the operating-system entropy source
- Resistance to independent cryptanalysis
- Side-channel resistance
- Formal correctness
- Production suitability
- Protection from complete machine-state rollback

BSR2 has not undergone independent cryptanalysis, formal verification, third-party certification, or production-security review.

## 0.2.0-alpha

### BSR2 Alpha 2

Release status:

```text
Historical experimental release
```

This release introduced the BSR2 implementation and replaced the historical BSR1 construction.

### Added

#### Core Construction

- Added the BSR2 custom 1024-bit permutation.
- Added a 16-word, 64-bit-per-word state design.
- Added repository-generated fixed parameters.
- Added repository-generated round constants.
- Added repository-generated structural mixing constants.
- Added repository-generated rotation values.
- Added repository-generated word permutation values.

#### Parameter Infrastructure

Added:

```text
tools/generate_bsr2_parameters.py
docs/BSR2_PARAMETER_GENERATION.md
tests/test_bsr2_parameters.py
```

These files provide deterministic parameter generation, parameter provenance documentation, and verification that generated parameters match the values embedded in `brisart_security_primitives.py`.

#### Validation

Added explicit verification of:

- Envelope algorithm identifier
- Envelope version
- Known-answer vector format version
- Envelope parsing and field validation
- Primitive input validation
- Hexadecimal validation
- Size limits
- DRBG lifecycle limits

#### Research Reporting

Added provenance metadata to generated research reports, including:

- Python version and implementation
- Operating system
- Git revision when available
- Configuration hash
- Known-answer vector hash

### Changed

- Changed the algorithm identifier from `BSR1-ARX-SPONGE-ETM` to `BSR2-ARX-SPONGE-ETM`.
- Changed the envelope version from `1` to `2`.
- Replaced inherited fixed parameters with repository-generated BSR2 parameters.
- Updated active domain strings for hashing, authentication, KDF, DRBG, stream, subkey, and envelope operations.
- Regenerated `tests/known_answer_vectors.json` for BSR2.
- Updated unsupported-version tests to derive invalid values from the active implementation.
- Relabeled throughput measurements as `BENCHMARK` rather than `PASS`.
- Updated GitHub Actions and repository documentation for the BSR2 folder layout.

### Hardened

- Added validation for generator-produced salt and nonce values.
- Added malformed-generator regression tests.
- Added deterministic restart and reuse observation tests.
- Anchored research output paths to the repository layout.
- Improved Git provenance handling.
- Documented deterministic restart risks and comparison-routine limitations.

### Compatibility

BSR2 Alpha 2 is intentionally incompatible with:

- BSR1 ciphertext
- BSR1 known-answer vectors
- BSR1 domain strings
- BSR1 fixed parameters
- BSR1 envelope metadata

BSR2 Alpha 2 is superseded by BSR2 Alpha 3.

## 0.1.0-alpha

### BSR1 Alpha 1

Release status:

```text
Historical experimental release
```

### Added

- Added the initial BSR1 custom permutation experiment.
- Added the initial sponge-style hash construction.
- Added the initial keyed authentication construction.
- Added the initial password-derived key experiment.
- Added purpose-separated subkey derivation.
- Added the deterministic random-bit generator.
- Added counter-based stream generation.
- Added the version 1 authenticated envelope.
- Added behavioral, boundary, mutation, known-answer, statistical, and performance testing.
- Added Markdown, JSON, and CSV research-report generation.

### Status

- Superseded by BSR2 Alpha 2 and BSR2 Alpha 3.
- Not production ready.
- Not independently reviewed.
- Not security certified.
