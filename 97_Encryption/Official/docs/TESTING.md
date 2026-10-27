# Testing Guide

Release: `0.4.0-alpha`

BrisartSecurityResearch uses five testing layers. Each one answers a different question. A passing result shows only that the tested behaviour happened as expected. It does not establish cryptographic security.

Run everything from the `97_Encryption` root. `tests/`, `tools/` and `research/` contain an `__init__.py` so that installed third-party packages with the same names cannot shadow them. Before 0.4.0, a site-packages `tests` package made `python -m unittest tests.test_bsr2_parameters` import the wrong module.

---

## 1. Unit and behaviour suites

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

| Suite | Covers |
|---|---|
| `test_brisart_security.py` | Legacy v2 envelope, rate-32 primitives, DRBG lifecycle (unchanged cases) |
| `test_envelope_hardening.py` | v2 failure ordering, size checks before hex decoding, master-key ceiling |
| `test_entropy_hardening.py` | Alpha 3 restart mitigation; all-zero, constant, and repeat rejection; short-request fix; fork reset |
| `test_primitives_hardening.py` | Fast permutation equals the Alpha 3 reference; type and range validation; XOR fast path; cache isolation; `wipe` |
| `test_sponge64.py` | BSR2-S64 incremental equivalence, padding, domain and framing separation, keystream, key derivation |
| `test_aead_v3.py` | Sealed v3 round trips, every-byte tamper rejection, binding, uniform errors, reserved bits, **randomizer-reuse misuse resistance**, armor |
| `test_stream_v3.py` | BSR-STREAM-1 boundaries; truncation, drop, duplicate, reorder, append; hostile chunk size; plaintext limits |
| `test_kdf_mhf.py` | BSR2-MHF-1 determinism, sensitivity, NFC normalisation, parameter encoding, hostile-header limits |
| `test_recovery.py` | Single, burst, and truncation repair; group overflow; damaged parity; record integrity |
| `test_archive.py` | All archive modes; encrypted directory; password mode; tamper; name validation; malicious directories; symlinked parents; overwrite; bombs; internal and external repair; footer rebuild; volumes |
| `test_drbg_hardening.py` | Fork detection, clone refusal, `from_system_entropy`, limits, unchanged output |
| `test_keys_and_cli.py` | Key file integrity and permissions; every CLI command; password mode; atomic failure; KDF downgrade rejection |
| `test_bsr2_parameters.py` | Embedded parameters equal the generator output |
| `test_known_answer_vectors.py` | Frozen legacy vectors (format 2) |
| `test_v3_known_answers.py` | Frozen v3 vectors (S64, sealed, stream, MHF) |

Result at release (CPython 3.12, Linux): **175 tests, `OK`, about 80 s**. Most of that time is the legacy 10,000-iteration KDF in `test_brisart_security.py`'s `setUpClass`.

---

## 2. Parameter reproducibility

```bash
python -m unittest -v tests.test_bsr2_parameters
```

This suite regenerates the BSR2 parameters from the public seed and compares them with `brisart_security_primitives.py`.

---

## 3. Frozen known-answer vectors

| File | Generator | Pins |
|---|---|---|
| `tests/known_answer_vectors.json` | `tests/generate_test_vectors.py` | Legacy hash, MAC, stream, DRBG, v2 envelope |
| `tests/v3_known_answer_vectors.json` | `tests/generate_v3_vectors.py` | BSR2-S64 modes, sealed v3, stream v1, BSR2-MHF-1 |

**Policy.** Never regenerate a vector file before an ordinary regression run. Regenerate only when you are deliberately changing the format it pins. When you do, review it together with the version numbers, `docs/FORMATS.md`, and the changelog.

In 0.4.0 the legacy vector file was **verified, not regenerated**. Its passing is the evidence that the permutation speed-up, the domain cache, and the integer XOR changed no output. The v3 vector file is new in this release.

Deterministic envelope, sealed, and stream vectors replace OS entropy with a fixed value, and only inside the test or generator. Production code never does this.

---

## 4. Research suite

```bash
python research/run_research_suite.py
python research/run_research_suite.py --config research/research_test_config.json
```

The suite writes `results/research_test_results.{md,json,csv}`. Each report records the project release, Python and OS versions, the git revision and dirty state, and SHA-256 hashes of the configuration and of both vector files.

| Category | Checks |
|---|---|
| hash, mac, stream, drbg, envelope | Legacy observations (avalanche, collisions, domain separation, tamper, wrong key/context, simple statistics) |
| v3 | Sealed round trips, single-bit tamper, **forced randomizer reuse** (no plaintext recovery), S64 keystream statistics, stream round trips, archive round trips |
| performance | `BENCHMARK` entries, excluded from the pass/fail count |

Result at release: **19 of 19 checks PASS, 3 benchmarks, about 90 s.**

In 0.4.0 the runner moved from `tests/` to `research/`. That is where this guide and the README already said it was, and where its default configuration path pointed. `research/research_test_config.json` did not exist before 0.4.0, so the suite could not run with its defaults.

---

## 5. CLI self-test

```bash
python brisart_security_cli.py selftest
```

This runs six fast end-to-end checks: sealed round trip and tamper, stream round trip and truncation, KDF determinism, and archive round trip. Use it on a new machine or after copying the folder into an air-gapped environment.

---

## Release checklist

1. `python -m py_compile` every `.py` file. Or simply run the unit suite, which imports all of them.
2. Run the unit suite and confirm it ends in `OK`.
3. Run the research suite and confirm there is no `FAIL` or `ERROR`.
4. Run `selftest`.
5. Confirm `brisart_security_version.py`, `README.md`, `CHANGELOG.md`, and `docs/FORMATS.md` all name the same release and format versions.
6. If vectors changed, confirm the change was intended and is recorded.

Do not rely on a fixed test count, because the suites grow over time.
