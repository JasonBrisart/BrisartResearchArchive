# Changelog

This document records every notable project-level change to BrisartSecurityResearch (Brisart Research Archive, `97_Encryption`).

This repository contains experimental research software. A changelog entry records implementation history and design evolution. It does not imply cryptographic validation, certification, production approval, or security guarantees.

Each entry from `0.4.0-alpha` onward follows the Brisart Identity Tools technical style. Every claim in those entries is tied to a source change and to the tests that exercise it. Entries for `0.3.0-alpha` and earlier are reproduced as they were written and were **not re-verified** for this release.

## 0.4.0-alpha

### BSR2 Alpha 4

Release status:

```text
Current experimental release
```

### Release Overview

Alpha 4 turns BSR2 from a single-envelope experiment into a complete offline encryption toolkit. It also closes the residual risk that Alpha 3 documented.

The frozen BSR2 permutation now underpins a new rate-64 sponge (BSR2-S64). On top of that sponge, this release adds:

- A nonce-misuse-resistant, key-committing sealed-message format (v3)
- A chunked stream format for inputs of any size
- A memory-hard password KDF
- Key-free recovery records
- An SQX-style secure archiver with an encrypted directory, compression, comments, repair, and multi-volume support
- Integrity-checked key files
- A complete command-line interface

The existing core is hardened at the same time: stricter validation, fork-safe and clone-proof DRBG state, a corrected entropy health check, and a permutation that runs about 1.7× faster.

The legacy rate-32 modes, the DRBG, and the v2 envelope produce bit-identical output. Every Alpha 2/3 envelope still decrypts.

All verification below was run on CPython 3.12 (Linux):

- Unit suite: **175 tests, `OK`**, about 80 s
- Research suite: **19 of 19 checks PASS** plus 3 benchmarks, about 90 s
- `selftest`: **6 of 6 PASS**
- The frozen legacy vector file passed **without regeneration**

### Added

#### `brisart_security_sponge.py`: BSR2-S64

- **What:** an incremental `Sponge64` (absorb, then squeeze) with rate 64 bytes, capacity 64 bytes, and pad10\*1. A distinct IV keeps it separate from every legacy initial state, and domain states are cached. It also provides the `hash64`, `mac64`, `keystream64`, `derive_keys64`, and `xor_into` modes.
- **Why:** the legacy stream spends about 12 permutation calls per 64 bytes because every block is a two-pass MAC. BSR2-S64 needs one call per 64 keystream bytes.
- **Measured:** v3 sealing runs at about 31 KiB/s, against about 4 KiB/s for the legacy v2 envelope on the same machine.
- **Tests:** `tests/test_sponge64.py` checks incremental/one-shot equivalence across rate boundaries, piecewise squeezing, padding distinctness at 0, 1, 62, 63, 64, 65 and 128 bytes, domain and framing separation, separation from the legacy sponge, keystream prefix consistency, and absorb-after-squeeze and pickling refusal.

#### `brisart_security_aead.py`: sealed message v3 (`BSR2-S64-SIV`)

- **What:** a binary format with a 104-byte header (magic, version, suite, flags, padding id, randomizer, commitment, SIV). Supported features:
  - Associated data
  - Padding: none, Padmé, or 256-byte blocks
  - Armored hex text with a checksum line
  - `inspect_sealed` to read the header without a key
- **Why:** Alpha 3 mitigated DRBG restarts by XORing in OS entropy, but recorded that a full rollback replaying OS randomness could still reuse a keystream. Making the keystream nonce a MAC of the whole message (SIV) means a repeated randomizer reuses a keystream only for identical messages.
- **Key commitment:** each header stores a commitment that is checked first, so a ciphertext cannot be opened under a second key without a BSR2-S64 collision.
- **Uniform errors:** every post-parse failure raises the same `authentication failed` message.
- **Tests:** `tests/test_aead_v3.py`.
  - `test_randomizer_reuse_is_misuse_resistant` forces OS entropy to a constant and replays the same DRBG. The known-plaintext XOR recovery that broke Alpha 2 does not recover the second message, and identical messages produce identical output, as SIV is expected to.
  - `test_every_byte_is_authenticated` flips one bit at every byte offset of a sealed message and gets a rejection at all of them.
  - The research suite repeats the misuse case 20 times with random inputs: 0 recoveries.

#### `brisart_security_stream.py`: BSR-STREAM-1

- **What:** chunked AEAD for files of any size (64-byte to 16 MiB chunks, 64 KiB default). Each chunk is sealed SIV-style with its index and a final flag in both the tag and the keystream nonce. A header tag binds the chunk size, context, and associated data.
- **Why:** the v2 envelope and the v3 sealed format cap a single message at 16 MiB and need the whole input in memory.
- **Tests:** `tests/test_stream_v3.py` checks round trips at 0, 1, 63, 64, 65, 128, 129 and 640 bytes. It rejects truncation at a chunk boundary, dropped, duplicated and reordered chunks, appended bytes, body and header bit flips, a header-only stream, wrong key, context or associated data, a 1 GiB header chunk size (rejected before allocation), and plaintext over the caller's limit.

#### `brisart_security_kdf.py`: BSR2-MHF-1

- **What:** a scrypt-ROMix-style memory-hard KDF over 128-byte blocks. The block function is the BSR2 permutation reduced to 8 rounds with feed-forward, and the mixing passes write their results back into the table.
  - Text passwords are Unicode NFC-normalised.
  - Parameters are serialised as a fixed 73-byte block (`KdfParams`).
  - Header-supplied parameters are limited by `max_memory_blocks` and `max_passes` before any allocation.
  - Default: 8192 blocks (1 MiB), one pass, about 4.6 s.
- **Why:** `docs/DESIGN.md` and `docs/CRYPTANALYSIS.md` both listed the legacy KDF's lack of memory-hardness as a known limitation.
- **Tests:** `tests/test_kdf_mhf.py` covers determinism; sensitivity to password, salt, memory, passes and output length; NFC equivalence (`café` composed versus decomposed); rejection of non-power-of-two, boolean, float and out-of-range parameters; encoding round trip and rejection of a bad id or non-zero filler; and the decode ceiling.

#### `brisart_security_recovery.py`: BSRR-1 recovery records

- **What:** interleaved XOR parity. Chunk *i* belongs to group *i mod P*. Each chunk carries a CRC-32 and Adler-32 checksum, and the record header is CRC-protected. Optional auxiliary metadata lets the archive rebuild its footers.
- **Why:** damage tolerance like SQX/RAR recovery data, so an archive with a damaged sector stays recoverable without the key.
- **Tests:** `tests/test_recovery.py` covers single-chunk repair (first, middle and last partial chunk), a burst exactly *P* chunks long (repaired), a burst of *P*+1 (refused), truncation repair, damaged parity that only matters when its group is also damaged, record integrity, and empty data.

#### `brisart_security_archive.py`: Brisart Secure Archive (`.bsa`) v1

- **What:** a multi-file archiver.
  - Per-file or solid mode, with `store`, `deflate` or `lzma` compression (standard-library `zlib`/`lzma`) and an automatic store fallback when compression does not help.
  - Key-file or password mode.
  - Everything encrypted, including the directory (names, sizes, times, comments) sealed as a v3 message with Padmé padding.
  - Archive and per-file comments.
  - Optional internal recovery record and external `.bsrr` records.
  - Key-free `repair_archive` that also rebuilds destroyed footers by scanning for the recovery record.
  - Multi-volume `split_volumes` and `join_volumes` with per-volume set id, index and CRC.
- **Extraction hardening:**
  - Names are validated on create and again on extract (absolute paths, `..`, `.`, empty segments, backslashes, colons, control characters, trailing dots or spaces, Windows reserved device names, case-insensitive duplicates).
  - `realpath` containment is checked for every target and its parent.
  - Writes through symlinks are refused.
  - Every file is written to a temporary name and renamed.
  - Nothing is overwritten without `overwrite=True`.
  - Permission bits are limited to 0644/0755.
  - Decompression stops at the authenticated size plus one byte.
- **Why:** this is the "much more to do" layer: a practical SQX-style tool built on the hardened constructions instead of a single-message demo.
- **Tests:** `tests/test_archive.py` (19 tests) covers:
  - All six mode/compression combinations, plus a check that no member name, comment or content appears in clear in a stored archive
  - Password mode with wrong-password, key-instead-of-password and no-credential rejection
  - A hostile 128 MiB KDF header refused under a 512 KiB ceiling
  - Tampering in the data region and in the directory
  - A preamble flag flip with a recomputed CRC, which still fails authentication
  - 15 unsafe names; malicious directories built with validation disabled (all rejected, nothing written); a symlinked parent directory (nothing written outside)
  - Overwrite rules, mtime and executable restoration, and a 5 MB deflate bomb stopped at 1001 bytes
  - Internal repair of preamble and data damage plus both footers (byte-identical result)
  - External-record repair, unrepairable damage (no output file created), and split/join including reversed order, a missing volume and a corrupted volume

#### `brisart_security_keys.py`: BSR2-KEYFILE v1

- **What:**
  - `generate_key`, from OS entropy optionally XORed with a DRBG.
  - `fingerprint`, a 128-bit BSR2-S64 fingerprint printed in 4-hex-digit groups.
  - Key files in JSON with a checksum over every field, created with `O_EXCL` and mode `0600`.
  - `permission_warning` for group- or world-readable files.
- **Tests:** `tests/test_keys_and_cli.py` round-trips a key file, checks its `0600` mode, refuses to overwrite it, and rejects five kinds of hand edit.

#### `brisart_security_cli.py`: command-line interface

- **What:** commands `info`, `keygen`, `fingerprint`, `encrypt`, `decrypt`, `seal`, `unseal`, `hash`, `kdf-bench`, `selftest`, and `archive create|list|test|extract|repair|rr|split|join`.
  - Passwords come only from `--password-prompt` (with confirmation when creating) or `--password-env`, never from argv.
  - Password-encrypted files store their KDF block and bind it as associated data.
  - Outputs are written atomically; nothing is overwritten without `--overwrite`.
  - Exit status is 1 on errors and 2 on usage errors.
- **Tests:** `tests/test_keys_and_cli.py` drives every command in-process. A wrong password exits 1 and leaves no output or `.partial` file. Patching the stored KDF memory from 128 to 64 blocks fails authentication.

#### `brisart_security_version.py`

- **What:** single source of truth for the project release, the release name, and every format version. The CLI `info`/`--version` and the research reports read from it.

#### Test infrastructure

- `tests/test_primitives_hardening.py`, `test_sponge64.py`, `test_aead_v3.py`, `test_stream_v3.py`, `test_kdf_mhf.py`, `test_recovery.py`, `test_archive.py`, `test_drbg_hardening.py`, `test_keys_and_cli.py` and `test_v3_known_answers.py`, as described above.
- `tests/generate_v3_vectors.py` and `tests/v3_known_answer_vectors.json` freeze BSR2-S64, sealed v3, stream v1 and BSR2-MHF-1 outputs.
- `research/research_test_config.json` is new. The suite's default config path pointed at it, but it did not exist, so the suite could not run with its defaults.

### Changed

#### `brisart_security_primitives.py`

- **Permutation schedule:**
  - **What:** the additive lane constants (period 192 rounds) and all rotation indices (period 8) are precomputed, and the round body is inlined into `permute_unchecked`.
  - **Effect:** one 32-round call drops from about 1.5 ms to about 0.9 ms.
  - **Verified identical by:** `tests/test_primitives_hardening.py`, which compares against a verbatim copy of the Alpha 3 loop for 1–40 rounds and 200 rounds (crossing both periods) and for all-zero, all-one and high-bit states; and by the unmodified legacy vector file.
- **Domain initial-state cache:** `_initial_state` caches up to 256 domains and always returns a copy. Isolation is tested.
- **Integer XOR:** `xor_bytes` uses big-integer XOR instead of a per-byte generator. A test checks it against byte-wise XOR at 0, 1, 31, 32 and 1000 bytes.
- **Hex decoding:** `hex_decode` uses a dictionary lookup in place of `str.index`.
- **New helpers:** `permute_unchecked` (internal fast path, used by BSR2-S64 and BSR2-MHF-1) and `wipe(bytearray)`.

#### `brisart_security_drbg.py`

- Output is unchanged (DRBG vector, plus a prefix check in `test_drbg_hardening.py`).
- Adds `from_system_entropy(personalization)`.
- Adds `__repr__`, which never shows state.

#### `brisart_security_envelope.py`

- Format and output are unchanged (envelope vector). The module docstring now describes it as the legacy v2 format and records its non-misuse-resistance limitation.

#### `research/run_research_suite.py` (moved from `tests/`)

- **What:**
  - Moved to `research/`, matching its own header, `docs/TESTING.md` and `README.md`.
  - Six v3 checks added: sealed round trips, single-bit tamper, forced randomizer reuse, S64 keystream statistics, stream round trips and archive round trips.
  - A v3 seal benchmark added.
  - The project release and the v3 vector hash added to provenance.
  - A config without a `v3` section skips the new checks, so older configs still run.
- **Action:** delete `tests/run_research_suite.py` when applying this release.

#### Documentation

- `README.md`, `SECURITY.md`, `docs/DESIGN.md` and `docs/TESTING.md` were rewritten for 0.4.0.
- New `docs/FORMATS.md` documents every byte layout.
- Every changed Python file now has an individual six-section header: Purpose, Communication / relationships, Settings / parameters, Edge cases, Known limitations, Examples.
- References to `.github/workflows/tests.yml`, `.gitignore` and `LICENSE` were removed from the layout. None of them is in this folder's export, and GitHub distribution is discontinued in favour of self-hosting on brisartresearcharchive.com.

### Fixed

- **Spurious entropy failures on short requests** (`brisart_security_entropy.py`). `system_entropy(n)` ran its all-zero check on the raw `n`-byte draw, so `system_entropy(1)` failed whenever the OS returned a zero byte (1 in 256 calls). Every request now draws at least 32 bytes, runs the checks on the full sample, and returns the first `n` bytes. Covered by `test_short_requests_use_full_health_sample` and `test_short_requests_do_not_fail_spuriously` (2,000 one-byte requests).
- **Test packages shadowed by installed packages** (`tests/__init__.py`, `tools/__init__.py`, `research/__init__.py`). Without `__init__.py`, an installed top-level `tests` package took precedence over the local folder, and `python -m unittest tests.test_bsr2_parameters` failed with `ModuleNotFoundError`. This failure was reproduced in the 0.4.0 build environment before the fix.
- **Research suite could not run with its defaults.** The runner sat in `tests/` while its documentation said `research/`, and its default config file did not exist. Both are fixed (see Changed and Added).

### Hardened

- **`brisart_security_primitives.py`:**
  - `permute` requires a `list` of exactly 16 ints in [0, 2^64) and an `int` round count (no `bool` or `float`).
  - Booleans are rejected for all lengths and counts.
  - `sponge_hash` validates the domain type.
  - `keyed_mac` validates the message type.
  - `stream_bytes` is capped at 64 MiB per call and validates the nonce type.
  - `derive_password_key` is capped at 10,000,000 iterations and rejects non-UTF-8 passwords with `BrisartPrimitiveError` instead of a raw `UnicodeEncodeError`.
- **`brisart_security_drbg.py`:**
  - The generator records its owner PID. Used after `fork`, it destroys itself and raises until reseeded.
  - `copy`, `deepcopy` and `pickle` raise `TypeError`, because duplicating DRBG state is the restart attack.
  - Personalization is capped at 4096 bytes and additional input at 64 KiB per request or reseed.
  - `True` is rejected as a length.
  - Tests: `tests/test_drbg_hardening.py`.
- **`brisart_security_entropy.py`:**
  - Constant samples (one repeated byte value) are rejected.
  - Requests are capped at 1 MiB.
  - The previous-sample memory resets after `fork`.
  - Tests: five new cases in `tests/test_entropy_hardening.py` (constant sample, two short-request cases, length validation, fork reset).
- **`brisart_security_envelope.py`:** the master key is capped at 1024 bytes on both encrypt and decrypt (`test_master_key_ceiling`).

### Security Impact

The residual risk recorded in Alpha 3 was that a rollback replaying both the DRBG state and OS randomness reuses a keystream. That risk is **closed for the v3 sealed, stream and archive formats**: under that rollback, distinct messages still get distinct keystreams, and only identical messages are revealed as identical. It is **unchanged for the legacy v2 envelope**, which keeps its exact Alpha 3 behaviour for compatibility.

### Compatibility

- Every BSR2 v2 envelope from Alpha 2 or Alpha 3 still decrypts, and `encrypt` still produces v2 envelopes. The algorithm identifier (`BSR2-ARX-SPONGE-ETM`), envelope version (`2`) and field set are unchanged.
- The legacy rate-32 hash, MAC, stream, KDF and DRBG produce identical output. `tests/known_answer_vectors.json` was not regenerated.
- The new formats cannot be read by Alpha 3 or earlier: sealed v3 (`BSRE`), stream v1 (`BSRS`), archive v1 (`.bsa`), recovery v1 (`BSRR`), volumes (`BSAVOL01`), CLI password files (`BSRPW001`) and key files (`BSR2-KEYFILE` v1).
- Python 3.10 or newer is required. The legacy code already used `int.bit_count` and `X | None` annotations, which need 3.10.
- Callers that passed `True` or `False` as a length, round count or iteration count, an over-limit size, or non-bytes where bytes are documented now get the module's error type.
- BSR1 material remains incompatible.

### Residual Risks and Limits

- **No analysis of the new constructions.** BSR2-S64 (rate 64, capacity 512), the v3 SIV composition, BSR-STREAM-1, BSR2-MHF-1 (8-round block function) and the archive composition have only behavioural tests. `docs/CRYPTANALYSIS.md` covers the permutation and the legacy rate-32 modes only.
- **Side channels.** CPython is not constant-time, and BSR2-MHF-1's data-dependent addressing leaks access patterns to a co-resident attacker.
- **Memory-hardness.** The 1 MiB default is modest. Pure-Python overhead means the defender pays far more than an attacker's native implementation would.
- **Recovery** repairs at most one damaged chunk per parity group. It is not Reed-Solomon.
- **Archives** are processed in memory, and throughput is tens of KiB/s.
- **No public-key signatures.** Archive authenticity is shared-key only.
- **Partial output from the stream API.** `decrypt_stream` used as a library writes each verified chunk before the end of the stream is known. Only the CLI guarantees all-or-nothing output.
- **Unreviewed analysis document.** `docs/CRYPTANALYSIS.md` was not revised in this release. Two of its statements do not match the source: §6 mentions an envelope `signature` field that does not exist, and §8 says the legacy KDF's iteration count is "recorded and validated on read", but the legacy KDF has no header. They are noted here for a later documentation pass.

## 0.3.0-alpha

### BSR2 Alpha 3

Release status:

```text
Historical experimental release
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

- Superseded by BSR2 Alpha 2, BSR2 Alpha 3, and BSR2 Alpha 4.
- Not production ready.
- Not independently reviewed.
- Not security certified.
