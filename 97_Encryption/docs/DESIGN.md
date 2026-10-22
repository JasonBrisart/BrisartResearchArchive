# BSR2 Design Notes

Release: `0.4.0-alpha` (BSR2 Alpha 4)

This document explains what each construction does and why it was designed that way. Byte layouts are in [`FORMATS.md`](FORMATS.md). Nothing here is a security proof, a standard, or a recommendation for production use.

---

## 1. Layering

```text
Layer 4  Applications   archive.py, keys.py, cli.py
Layer 3  Formats        aead.py (sealed v3), stream.py, kdf.py, recovery.py, envelope.py (legacy v2)
Layer 2  Modes          sponge.py (BSR2-S64)                 drbg.py (legacy rate-32 DRBG)
Layer 1  Core           primitives.py (permutation + legacy rate-32 modes)
Boundary                entropy.py (only source of non-deterministic randomness)
```

Each layer imports only from layers below it or from the entropy boundary. Layer 1 is frozen: the known-answer vectors from Alpha 2/3 must keep passing.

---

## 2. The Permutation (Layer 1, unchanged)

- 16 words × 64 bits = 1024-bit state, 32 rounds by default.
- Each round does the following in order:
  1. XOR a round constant into lane 0 and a round-index constant into lane 15.
  2. Apply three ARX pair layers (adjacent pairs, half-state pairs, adjacent pairs).
  3. Apply the fixed word permutation.
  4. Apply a Chi-like nonlinear layer, `(a & b) ^ (~c & d)`, rotated, plus an additive lane constant.
- Rotations: `34, 5, 38, 37, 31, 50, 59, 17`. Word permutation: `6, 11, 12, 0, 5, 15, 2, 14, 3, 13, 4, 7, 10, 9, 8, 1`.
- All parameters come from a public seed via `tools/generate_bsr2_parameters.py`.

**0.4.0 implementation change.** The additive lane constant depends only on `r mod 192`, and every rotation index depends only on `r mod 8`. Both are now precomputed tables, and the round body is inlined. Output is bit-identical. Two things show this: the reference-equivalence test, which compares against the Alpha 3 loop for 1–40 and 200 rounds, and the frozen vectors. One call now takes about 0.9 ms instead of about 1.5 ms.

---

## 3. Legacy Rate-32 Modes (Layer 1, frozen)

- **Sponge hash:** rate 32 bytes, domain-dependent initial state, `0x80` padding plus a 64-bit length. Outputs are 1–1024 bytes. From 0.4.0, the initial state for each domain is cached; a cache entry costs one permutation per 32 bytes of framed domain.
- **Keyed MAC:** inner/outer construction over framed key and message. It is custom and not equivalent to HMAC.
- **Legacy KDF:** iterated sponge, minimum 10,000 iterations, default 120,000. Now capped at 10,000,000. It is not memory-hard.
- **Subkey derivation:** `keyed_mac(master, frame(salt) | frame(purpose))`.
- **Legacy stream:** `keyed_mac(key, frame(nonce) | u64 counter, 64)` per 64-byte block. That costs about 12 permutation calls per block.

These modes stay because v2 envelopes and the DRBG depend on them. New work should use BSR2-S64.

---

## 4. BSR2-S64 (Layer 2, new)

**Why it exists.** The legacy stream spends about 12 permutation calls per 64 bytes because each block is a full two-pass MAC. A standard sponge over the same permutation can absorb or squeeze one full rate block per call.

**Parameters.** Rate 64 bytes, capacity 64 bytes (512 bits), pad10\*1. The IV is distinct from every legacy initial state (word 15 carries the tweak `BSR2S64\x01`). Each domain string is absorbed first, so domains start from separate states.

**Modes.** Every variable-length input is framed:

- `hash64`
- `mac64`: key-prefixed. The capacity is never output, so length extension is ruled out structurally.
- `keystream64`: absorb key and nonce, then squeeze.
- `derive_keys64`: a single `mac64` call, split into independent keys.

**Rationale and risk.** A 512-bit capacity gives a generic bound of about 2^256 for an ideal permutation. Whether the BSR2 permutation behaves like an ideal permutation in this mode has **not** been analysed. `docs/CRYPTANALYSIS.md` covers the permutation and the rate-32 modes only.

---

## 5. Sealed Message v3 (Layer 3, new)

**Goal.** Fix the remaining weakness that Alpha 3 recorded. If the OS entropy and the DRBG state are both replayed, the v2 envelope reuses its keystream. That reuse enables the known-plaintext XOR attack demonstrated against Alpha 2.

**Construction (SIV).**

1. A random 32-byte *randomizer* is built from OS entropy, optionally XORed with a caller DRBG.
2. The randomizer and the header prefix derive three keys: `enc`, `mac`, and `commit`.
3. The keystream nonce is the SIV, a MAC over the header, the commitment, the context, the associated data, and the whole padded payload.

**Properties claimed (behavioural, not proven).**

| Property | Mechanism |
|---|---|
| Nonce-misuse resistance | Repeating the randomizer only matters if the plaintext and associated data are also identical. Different messages get different SIVs, so different keystreams. Tested in `test_randomizer_reuse_is_misuse_resistant`. |
| Key commitment | A 32-byte `commit` value is stored and checked first. Opening one ciphertext under two keys would require a BSR2-S64 collision. |
| Full-header authentication | The SIV covers every header byte. The test suite flips every single bit position. |
| Length hiding (optional) | Padmé padding leaks O(log log L) bits; block padding hides length within 256 bytes. Padding must be canonical. |
| No decryption oracle | All post-parse failures return the same message. Plaintext is never returned before the SIV verifies. |

**Costs.** SIV needs two passes, so throughput is about half the raw keystream rate. Identical inputs produce identical outputs, but only after a total entropy failure.

---

## 6. BSR-STREAM-1 (Layer 3, new)

Large inputs are split into fixed-size chunks. Each chunk is sealed SIV-style, with its index and a final flag bound into both the tag and the keystream nonce. A header tag binds the chunk size, randomizer, commitment, context, and associated data, so a wrong key or context is caught before any chunk is processed.

Together the index and final flag rule out chunk reordering, duplication, dropping, truncation (including at a chunk boundary), and extension. Callers that need all-or-nothing output should write to a temporary file. The CLI does this.

---

## 7. BSR2-MHF-1 (Layer 3, new)

The legacy KDF is time-hard only. BSR2-MHF-1 follows scrypt's ROMix:

1. Fill a table of `m` 128-byte blocks, each produced by `F` applied to the previous block.
2. Make `m·t` data-dependent passes that read a block, mix it, and **write the result back**.

`F` is the BSR2 permutation reduced to 8 rounds with feed-forward. The reduced-round choice follows scrypt's Salsa20/8, and the first-pass analysis observed full diffusion by round 3. Text passwords are NFC-normalised. Parameters read from untrusted headers are bounded by caller-supplied ceilings before any memory is allocated.

**Limitations.** Data-dependent addressing leaks access patterns to a co-resident cache-timing attacker, as scrypt does. In CPython the defender spends much more RAM and time than an attacker's native code would. The default (1 MiB, one pass, about 4.6 s) is modest by native standards.

---

## 8. Recovery Records (Layer 3, new)

SQX and RAR style recovery data, implemented as interleaved single parity:

- Chunk `i` belongs to group `i mod P`.
- One XOR parity block per group.
- CRC-32 plus Adler-32 per chunk to locate damage.

Interleaving lets a contiguous burst of up to `P` damaged chunks be repaired. Repair needs no key. The checksums only detect accidents; authenticity comes from the archive MACs, which are checked again after repair, so a malicious "repair" can never yield accepted plaintext.

---

## 9. Brisart Secure Archive (Layer 4, new)

**Design choices**

- **Everything is encrypted.** File data and the whole directory (names, sizes, times, comments) are encrypted. Only the preamble, footers, and recovery record are in clear.
- **Preamble as associated data.** Every stream and the directory authenticate the preamble, so flags, KDF parameters, and the archive id cannot be swapped.
- **Per-file streams.** Each file has its own context (`bsa:<id>:entry:<i>`), so entries cannot be swapped between positions or archives. Solid mode trades random access for ratio.
- **Compression fallback.** If compression does not shrink a file, it is stored.
- **Redundant footers.** There are two copies, and the recovery record carries enough metadata to rebuild them.

**Extraction hardening**

- Names are checked when the archive is created and again when it is extracted.
- `realpath` containment is checked for the target and for its parent after `mkdir`, so pre-existing symlinks are caught.
- No write through a symlink.
- Atomic temp-and-rename for every file.
- No overwrite without opt-in.
- Permission bits are limited to 0644/0755.
- Decompression is bounded by the authenticated size plus one byte.

**Not provided:** public-key signatures (SQX had them), encrypted recovery records, append/update of existing archives, or streaming (out-of-core) processing.

---

## 10. Legacy Envelope v2

This format is unchanged from Alpha 3. Salt and nonce are each a DRBG contribution XORed with fresh OS entropy. The keys are `derive_subkey(master, salt, "BSR2/encryption" | "BSR2/authentication")`, the legacy stream is used, and the tag covers the algorithm, version, context, salt, nonce, and ciphertext. 0.4.0 adds only a 1024-byte master-key ceiling.

---

## 11. Randomness

`brisart_security_entropy.system_entropy` is the only non-deterministic source. In 0.4.0 it:

- Always draws at least 32 bytes and runs its health checks on the full draw. Previously a 1-byte request failed 1 time in 256 because a zero byte was treated as an all-zero sample.
- Rejects all-zero samples, constant samples, and immediate repeats.
- Resets its repeat memory after `fork`.

`BrisartDRBG` remains deterministic, with these additions:

- It detects being used in a forked child and destroys itself until reseeded.
- It refuses `copy`, `deepcopy`, and `pickle`, because duplicating its state reproduces the restart attack.
- It bounds personalization to 4096 bytes and additional input to 64 KiB.

---

## 12. Unestablished Properties

None of the following has been established for any construction here:

- Collision or preimage resistance
- Pseudorandomness or indistinguishability
- Forgery resistance
- Differential, linear, rotational, algebraic, or related-key resistance
- Memory-hardness or time-memory-trade-off resistance
- Side-channel resistance
- Entropy-source validity
- Production suitability
