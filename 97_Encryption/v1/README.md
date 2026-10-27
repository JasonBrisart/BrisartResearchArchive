# BrisartSecurityResearch

Dependency-free, pure-Python research into custom cryptographic constructions for offline and air-gapped environments.

> [!WARNING]
> **Experimental research only.** This repository contains a custom cryptographic construction that has not undergone independent cryptanalysis, formal verification, certification, or production security review. Passing the included tests does not establish cryptographic security. Do not use this project as the sole protection for credentials, personal information, sensitive research, access-control decisions, recovery material, or other valuable data.

## Purpose

BrisartSecurityResearch is a small, inspectable research implementation built with the Python standard library and no third-party packages. The repository explores:

- a custom 1024-bit permutation
- a sponge-style hash construction
- a keyed authentication construction
- a password-derived key experiment
- purpose-separated subkey derivation
- a deterministic random-bit generator
- counter-based stream generation
- a versioned encrypt-then-authenticate envelope
- behavioral, boundary, regression, mutation, statistical, and performance testing

The design prioritizes readability, auditability, reproducibility, and offline inspection. Those properties are useful for research, but they are not substitutes for established cryptographic analysis.

## Status

- **Maturity:** Alpha
- **Research implementation:** BSR1
- **Intended use:** Controlled research and offline prototypes
- **Production ready:** No
- **Independently reviewed:** No
- **Security certified:** No

## Repository layout

```text
BrisartSecurityResearch/
├── .github/
│   └── workflows/
│       └── tests.yml
├── docs/
│   ├── DESIGN.md
│   └── TESTING.md
├── research/
│   ├── research_test_config.json
│   └── run_research_suite.py
├── results/
├── tests/
│   ├── generate_test_vectors.py
│   ├── known_answer_vectors.json
│   ├── test_brisart_security.py
│   └── test_known_answer_vectors.py
├── .gitignore
├── brisart_security_drbg.py
├── brisart_security_envelope.py
├── brisart_security_primitives.py
├── CHANGELOG.md
├── LICENSE
├── README.md
└── SECURITY.md
```

## Core files

### `brisart_security_primitives.py`

Contains the custom permutation, sponge construction, keyed authentication construction, password-derived key experiment, subkey derivation, stream generation, XOR transformation, comparison routine, and hexadecimal codec.

### `brisart_security_drbg.py`

Contains the deterministic generator used to expand caller-provided seed material. The generator does not create entropy. Output depends on the supplied seed, personalization, additional input, and call sequence.

### `brisart_security_envelope.py`

Contains the versioned authenticated envelope. The module derives separate encryption and authentication subkeys, transforms plaintext with a generated stream, authenticates the envelope, and verifies authentication before returning plaintext.

## Running the tests

From the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python research/run_research_suite.py --config research/research_test_config.json
```

The first command runs behavioral, boundary, and frozen known-answer regression tests. The second runs the configurable research suite and writes reports into `results/`.

Do not regenerate known-answer vectors during an ordinary test run. See [`docs/TESTING.md`](docs/TESTING.md) for the complete workflow.

## Research results

The `results/` directory contains generated research-suite output in Markdown, JSON, and CSV formats after the research runner is executed. Reports include runtime provenance, the current source revision when Git is available, and SHA-256 hashes for the configuration and frozen vector file.

These reports document observed behavior only. They do not demonstrate collision resistance, preimage resistance, stream indistinguishability, forgery resistance, side-channel resistance, or production suitability. Performance entries are labeled as benchmarks rather than security passes.

## Entropy boundary

The custom deterministic generator expands caller-provided seed material but cannot manufacture unpredictable physical entropy. Any real security property depends on the quality, unpredictability, secrecy, and lifecycle of externally supplied seed material.

## Appropriate uses

- controlled cryptographic research
- source-code inspection
- synthetic or disposable data
- offline workflow prototypes
- parser and tamper-handling research
- regression testing of the experimental format
- educational analysis of custom constructions

## Unsupported uses

Do not rely on this repository as the sole protection for:

- passwords or credentials
- API keys or access tokens
- biometric or identity records
- recovery secrets
- personal or regulated information
- valuable unpublished research
- production authorization
- safety-critical systems

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md) describes the implemented construction.
- [`docs/TESTING.md`](docs/TESTING.md) explains test layers, boundary coverage, result interpretation, and the vector policy.
- [`SECURITY.md`](SECURITY.md) defines the project security posture.
- [`CHANGELOG.md`](CHANGELOG.md) records project-level changes.

## Licensing

This project is part of the Brisart ecosystem. The current licensing terms and ecosystem policies are maintained in the BrisartLicensing repository. See [`LICENSE`](LICENSE).
