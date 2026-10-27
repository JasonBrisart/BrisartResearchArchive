# Changelog

All notable project-level changes to BrisartSecurityResearch are recorded here.

This repository is experimental research software. A changelog entry records implementation history and does not imply security validation.

## Unreleased

### Changed

- Renamed the experimental algorithm identifier from `BRC1-ARX-SPONGE-ETM` to `BSR1-ARX-SPONGE-ETM` to align with BrisartSecurityResearch.
- Regenerated known-answer vectors for the renamed BSR1 domains and envelope identifier.

### Documentation

- Reorganized project documentation around the current repository structure.
- Separated design, testing, security, licensing, and release-history material.
- Clarified that known-answer vectors are frozen regression fixtures.
- Clarified that statistical and performance results are observations rather than cryptographic proofs.

### Repository

- Moved test modules and known-answer vectors into `tests/`.
- Moved generated research reports into `results/`.
- Added automated test execution through GitHub Actions.

## 0.1.0-alpha

### Added

- Custom 1024-bit permutation using 16 unsigned 64-bit state words.
- Sponge-style hash experiment with domain separation.
- Custom keyed authentication construction.
- Password-derived key experiment.
- Purpose-separated subkey derivation.
- Deterministic random-bit generator with reseeding and lifecycle limits.
- Counter-based stream generation.
- Versioned encrypt-then-authenticate envelope.
- Behavioral tests for round trips, malformed envelopes, tampering, wrong keys, wrong contexts, encoding, and generator lifecycle behavior.
- Frozen known-answer vectors for the hash, MAC, stream generator, DRBG, and envelope.
- Configurable research checks for diffusion, collision observation, domain separation, stream statistics, tamper rejection, and local performance.
- Markdown, JSON, and CSV result output.

### Status

- Experimental research
- Alpha maturity
- Not production ready
- Not independently reviewed
- Not security certified
