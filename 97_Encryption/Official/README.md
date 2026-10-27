# BrisartSecurityResearch

Pure-Python research into custom cryptographic constructions and a hardened, SQX-style secure archiver, built for offline and air-gapped environments. Part of the Brisart Research Archive (`97_Encryption`).

> [!WARNING]
> **This is experimental research software.** BSR2 is a custom construction. It has had no independent cryptanalysis, formal verification, certification, or production security review. The 0.4.0 modes (BSR2-S64, the v3 sealed format, BSR-STREAM-1, BSR2-MHF-1, and the archive) are newer than the empirical analysis in `docs/CRYPTANALYSIS.md` and have not been analysed at all. Passing tests does not show the code is secure. Do not use it as the only protection for credentials, personal data, recovery secrets, regulated data, or anything valuable.

## Current Status

```text
Project release:          0.4.0-alpha
Release name:             BSR2 Alpha 4
Permutation:              BSR2-P1024 (unchanged since Alpha 2)
Recommended formats:      Sealed message v3 (BSR2-S64-SIV)
                          Stream v1 (BSR-STREAM-1)
                          Archive v1 (Brisart Secure Archive, .bsa)
Legacy format:            Envelope v2 (BSR2-ARX-SPONGE-ETM), still supported
Dependencies:             Python 3.10+ standard library only
Production ready:         No
Independently reviewed:   No
```

The release number, the permutation, and each container format have separate version numbers. `brisart_security_version.py` is the single source of truth for all of them.

## What 0.4.0 Adds

| Capability | Where | Summary |
|---|---|---|
| Rate-64 sponge | `brisart_security_sponge.py` | Incremental absorb/squeeze over the frozen permutation, with hash, MAC, keystream, and multi-key derivation. One permutation call per 64 keystream bytes, versus about 12 in the legacy stream. |
| Sealed messages v3 | `brisart_security_aead.py` | Binary, key-committing, nonce-misuse-resistant AEAD (SIV). Supports associated data, Padmé/block padding, and armored text. |
| Chunked streams | `brisart_security_stream.py` | Encrypts inputs of any size. Detects reordering, dropped or duplicated chunks, truncation, and appended data. |
| Memory-hard KDF | `brisart_security_kdf.py` | BSR2-MHF-1, a scrypt-style construction with write-back, NFC password normalisation, and limits on header-supplied parameters. |
| Recovery records | `brisart_security_recovery.py` | Interleaved XOR parity that can repair burst damage without the key. Records can be internal or external (`.bsrr`). |
| Secure archive | `brisart_security_archive.py` | Multi-file archives with per-file or solid compression (store/deflate/lzma) and an encrypted directory. Adds comments, recovery data, repair, multi-volume split/join, and hardened extraction. |
| Key files | `brisart_security_keys.py` | Integrity-checked BSR2-KEYFILE v1 with fingerprints, created with owner-only permissions. |
| Command line | `brisart_security_cli.py` | Single entry point for every feature above, plus `selftest`. |

The 0.4.0 changes also harden the existing core: argument validation is stricter, the DRBG gains fork detection and refuses to be cloned, short entropy requests no longer fail at random, and the permutation runs about 1.7× faster with bit-identical output. See [`CHANGELOG.md`](CHANGELOG.md) for the full file-by-file record.

## Architecture

```text
                     brisart_security_cli.py
                              |
          +-------------------+--------------------+
          |                   |                    |
  brisart_security_   brisart_security_     brisart_security_
     archive.py          keys.py               (legacy)
     |   |   |   \                           envelope.py  drbg.py
     |   |   |    recovery.py                     |          |
     |   |   kdf.py                               |          |
     |   stream.py                                |          |
     aead.py   \                                  |          |
         \      \                                 |          |
          +------+---- sponge.py (BSR2-S64)       |          |
                          |                       |          |
                  primitives.py (BSR2 permutation, legacy rate-32 modes)
                          |
                  entropy.py (OS randomness boundary, health checks)
```

The layers are:

1. **Core:** `brisart_security_primitives.py` holds the frozen permutation and the legacy rate-32 modes. Their outputs are pinned by known-answer vectors.
2. **v3 modes:** `brisart_security_sponge.py` builds the rate-64 sponge on that permutation.
3. **Formats:** the sealed message, stream, KDF, and recovery record modules.
4. **Applications:** the archive, key files, and CLI.

`brisart_security_entropy.py` is the only module that reads non-deterministic randomness.

## Quick Start

Run every command from the `97_Encryption` root.

```bash
python brisart_security_cli.py selftest
python brisart_security_cli.py keygen lab.key --label "lab key"
python brisart_security_cli.py fingerprint lab.key
```

### Files

```bash
python brisart_security_cli.py encrypt notes.txt notes.bsrs --key-file lab.key
python brisart_security_cli.py decrypt notes.bsrs notes.txt.out --key-file lab.key

# password mode (prompted, or --password-env NAME for scripts)
python brisart_security_cli.py encrypt notes.txt notes.pw --password-prompt
```

Decryption writes to a temporary file and only renames it into place once the whole input has authenticated. A failed decryption leaves no output behind.

### Sealed messages

```bash
python brisart_security_cli.py seal secret.txt secret.asc --key-file lab.key --armor
python brisart_security_cli.py unseal secret.asc secret.out --key-file lab.key
```

### Archives

```bash
python brisart_security_cli.py archive create lab.bsa data/ --key-file lab.key --comment "run 42" --recovery 5
python brisart_security_cli.py archive list lab.bsa --key-file lab.key
python brisart_security_cli.py archive test lab.bsa --key-file lab.key
python brisart_security_cli.py archive extract lab.bsa restored/ --key-file lab.key

# damage tolerance (repair does not need the key)
python brisart_security_cli.py archive rr lab.bsa lab.bsrr --percent 10
python brisart_security_cli.py archive repair damaged.bsa fixed.bsa --external lab.bsrr

# volumes
python brisart_security_cli.py archive split lab.bsa --size 1048576
python brisart_security_cli.py archive join lab-joined.bsa lab.bsa.001 lab.bsa.002 lab.bsa.003
```

Useful options include `--solid` (compress all files as one block), `--compression store|deflate|lzma`, `--kdf-memory BLOCKS` for password archives, and `--overwrite`. The CLI never overwrites an existing file unless you pass `--overwrite`.

### Library use

```python
from brisart_security_aead import seal, unseal
from brisart_security_archive import build_archive, ArchiveReader

key = bytes(range(32))  # use brisart_security_keys.generate_key() in practice
blob = seal(key, b"secret", "notes:1", associated_data=b"header", padding="padme")
assert unseal(key, blob, "notes:1", associated_data=b"header") == b"secret"

archive = build_archive([("a/b.txt", b"alpha", 0, "comment")], key=key, recovery_percent=5)
assert ArchiveReader(archive, key=key).read("a/b.txt") == b"alpha"
```

## Security Model

| Threat or failure | Handling in 0.4.0 |
|---|---|
| DRBG restart or reused DRBG state | The legacy envelope XORs DRBG output with OS entropy (Alpha 3). The v3 formats do the same and are also nonce-misuse resistant. |
| OS entropy failure **and** replayed DRBG | v3 keeps different messages on different keystreams. Only identical messages produce identical output. |
| Tampering, truncation, reordering | SIV tags cover every v3 byte. Chunk index and final flag are authenticated. Archive preamble is bound as associated data. |
| Wrong key, or key substitution | Explicit 32-byte key commitment in every v3 header. The archive has a key check. |
| Hostile headers (DoS) | KDF memory, chunk size, directory size, entry count, and unpacked size are capped before any work starts. Decompression is bounded by the authenticated size. |
| Path traversal and overwrite attacks | Names are validated on create and on extract. Resolved paths must stay inside the destination. Symlinked parents are refused. No overwrite without opt-in. Outputs are written atomically. |
| Accidental corruption | Recovery records repair damage without the key. Authentication is re-checked after repair. |
| Process fork | The DRBG destroys itself in a forked child. The entropy duplicate-detector resets. |

**Out of scope:** side channels (CPython is not constant-time; MHF indexing depends on secret data), a full machine-state rollback that also replays OS randomness, public-key signatures, and any cryptographic strength claim for the custom constructions. See [`SECURITY.md`](SECURITY.md).

## Repository Layout

```text
97_Encryption/
├── docs/
│   ├── BSR2_PARAMETER_GENERATION.md
│   ├── CRYPTANALYSIS.md
│   ├── DESIGN.md
│   ├── FORMATS.md
│   └── TESTING.md
├── research/
│   ├── __init__.py
│   ├── research_test_config.json
│   └── run_research_suite.py
├── tests/
│   ├── __init__.py
│   ├── generate_test_vectors.py
│   ├── generate_v3_vectors.py
│   ├── known_answer_vectors.json
│   ├── v3_known_answer_vectors.json
│   ├── test_aead_v3.py
│   ├── test_archive.py
│   ├── test_brisart_security.py
│   ├── test_bsr2_parameters.py
│   ├── test_drbg_hardening.py
│   ├── test_entropy_hardening.py
│   ├── test_envelope_hardening.py
│   ├── test_kdf_mhf.py
│   ├── test_keys_and_cli.py
│   ├── test_known_answer_vectors.py
│   ├── test_primitives_hardening.py
│   ├── test_recovery.py
│   ├── test_sponge64.py
│   ├── test_stream_v3.py
│   └── test_v3_known_answers.py
├── tools/
│   ├── __init__.py
│   └── generate_bsr2_parameters.py
├── brisart_security_aead.py
├── brisart_security_archive.py
├── brisart_security_cli.py
├── brisart_security_drbg.py
├── brisart_security_entropy.py
├── brisart_security_envelope.py
├── brisart_security_kdf.py
├── brisart_security_keys.py
├── brisart_security_primitives.py
├── brisart_security_recovery.py
├── brisart_security_sponge.py
├── brisart_security_stream.py
├── brisart_security_version.py
├── CHANGELOG.md
├── README.md
└── SECURITY.md
```

The research suite writes `results/` on demand.

## Validation

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python research/run_research_suite.py
python brisart_security_cli.py selftest
```

In 0.4.0 these ran on CPython 3.12 (Linux) with the following results: 175 tests, `OK`, in about 80 seconds; 19 of 19 research checks passed plus 3 benchmarks in about 90 seconds; and 6 of 6 self-test checks passed. Most of the unit-test time is the legacy 10,000-iteration KDF in `tests/test_brisart_security.py`. [`docs/TESTING.md`](docs/TESTING.md) describes each layer and the vector policy.

## Performance

Everything is pure Python. Measured on the release machine:

| Operation | Approximate rate |
|---|---|
| Permutation (32 rounds) | 0.9 ms per call |
| v3 seal or unseal (SIV, two passes) | ~31 KiB/s |
| BSR-STREAM-1 encrypt (64 KiB chunks) | ~27 KiB/s |
| Legacy v2 envelope encrypt | ~4 KiB/s |
| BSR2-MHF-1 default (1 MiB) | ~4.6 s per derivation |

These are research speeds. Use the archive for documents and datasets, not multi-gigabyte media.

## Compatibility

- Every BSR2 Alpha 2/3 envelope still decrypts. The v2 encrypt path still produces v2 envelopes. The frozen legacy vectors pass unchanged.
- The legacy rate-32 hash, MAC, stream, KDF, and DRBG produce bit-identical output.
- The v3, stream, archive, KDF, and key-file formats are new. Earlier releases cannot read them.
- BSR1 material is still incompatible and should stay in its own archive.

## Documentation

- [`docs/DESIGN.md`](docs/DESIGN.md): constructions, layering, and design rationale
- [`docs/FORMATS.md`](docs/FORMATS.md): byte-level layouts for every format
- [`docs/TESTING.md`](docs/TESTING.md): test layers, vector policy, release checks
- [`docs/CRYPTANALYSIS.md`](docs/CRYPTANALYSIS.md): first-pass empirical analysis of the permutation and the legacy modes
- [`docs/BSR2_PARAMETER_GENERATION.md`](docs/BSR2_PARAMETER_GENERATION.md): parameter provenance
- [`SECURITY.md`](SECURITY.md): security posture and reporting
- [`CHANGELOG.md`](CHANGELOG.md): release history

## Licensing

This project is part of the Brisart ecosystem. Licensing terms and ecosystem policies are maintained by the BrisartLicensing project.
