# BSR2 Cryptanalysis Notes

Identifier: BSR2-ARX-SPONGE-ETM
Envelope Version: 2
Scope: empirical, first-pass cryptanalysis of the BSR2 permutation and the
constructions built on it (sponge hash, keyed MAC, subkey derivation, counter
stream, authenticated envelope).

> **Status of this document.** This is a *first-pass empirical evaluation*, not a
> security proof, not independent review, and not certification. It records what
> was tested, how, and what was found. Passing every test here does **not**
> establish cryptographic security. See "Limits of this analysis" and BSR2's
> `SECURITY.md`. The correct one-line summary of the results below is:
>
> *"No breaks were found across every cryptanalytic and statistical test run so
> far, and the primitive behaves like an ideal random function on all of them —
> but BSR2 remains unreviewed by independent cryptographers and must not be
> treated as proven."*

---

## 0. Parameters under analysis

The permutation operates on 16 × 64-bit words (1024-bit state), 32 default rounds.
Fixed parameters (reproducibly generated from a public seed; see
`docs/BSR2_PARAMETER_GENERATION.md`):

- Rotations: `34, 5, 38, 37, 31, 50, 59, 17`
- Word permutation: `6, 11, 12, 0, 5, 15, 2, 14, 3, 13, 4, 7, 10, 9, 8, 1`
- 24 round constants, plus structural constants (round-index, lane-index,
  initial-state).

Round structure per round: XOR of round constant into lanes 0 and 15, three ARX
mixing layers (modular add + XOR + fixed rotation), a word permutation, then a
nonlinear neighbor-mixing layer (`(a & b) ^ (~c & d)`, Chi-like) with an
index/round-dependent additive constant.

---

## 1. Methodology and reproducibility

All tests are empirical: statistical behavior is measured over random inputs and
reduced-round variants, and compared against two references.

- **Ideal reference (gold standard).** A SHA-256-based random function mapping the
  1024-bit state to 1024 bits. Represents "what a perfect random permutation looks
  like" on each test.
- **Weak reference (broken control).** The BSR2 ARX skeleton with the **nonlinear
  Chi layer removed**. Included so each test has a design known to be weak; if the
  weak control also passes a test, that test has low discriminating power and its
  result for BSR2 carries correspondingly less weight.

A round-isolated implementation `one_round(state, round_index)` was verified
**byte-identical** to the shipping `permute` across 2,000 random states × 8 round
depths, so per-round analysis reflects the real cipher. The full permutation was
independently reimplemented in C and verified byte-identical on fixed vectors,
which (a) validates the reference used here and (b) enabled large-sample
statistical testing at speed.

Seeds are fixed in the test scripts; reruns reproduce the figures below up to
sampling noise.

---

## 2. Diffusion and the Strict Avalanche Criterion (SAC)

**Test.** Flip one input bit; measure the fraction of the 1024 output bits that
change. Ideal = 0.5. Also measured per-output-bit flip probability (SAC).

**Results (BSR2).**

| Rounds | Mean avalanche |
|-------:|:--------------:|
| 1 | 0.053 |
| 2 | 0.433 |
| 3 | 0.501 |
| 4–32 | 0.500 |

- Full avalanche is reached by **round 3**. At 32 rounds this is a **~10×
  round-count margin** over the depth required for complete diffusion.
- Full-round per-bit SAC (1,500 trials): min 0.457, max 0.538, mean 0.4994; **0 of
  1024** output bits deviate more than 6% from 0.5.
- Structured inputs (all-zero, all-ones, single-bit, all-lanes-equal) all diffuse
  to ~512 output popcount with no residual structure at 32 rounds.

**Interpretation.** Diffusion is fast and complete; no dead or stuck output bits.

---

## 3. Differential cryptanalysis (empirical)

### 3.1 Single-bit differential propagation

**Test.** For fixed single-bit input differences, measure minimum output
difference (Hamming weight) over many random base states, per round.

**Results.** Minimum output difference climbs 3 → 54 → **445–455** by round 3 and
stays near 512 through round 8. No single-bit difference produces an anomalously
low output difference beyond round 2. (Verified single-bit differences only —
i.e. guaranteed-nonzero inputs; an earlier run reporting "0" was traced to a
test-harness bug that canceled two bit flips, not a collision.)

### 3.2 Greedy differential characteristic search

**Test.** Under the Markov-cipher assumption, estimate each round's best
differential transition probability with 40k–120k random-state pairs, then greedily
chain the dominant trail edge (Din_{r+1} = argmax_Dout P(Dout | Din_r)) and record
how many rounds a characteristic survives before its best edge falls below the
sampling floor (~2⁻¹⁷).

**Results.**

- Input differences in words 0–7: **no characteristic survives round 0** (best
  output difference does not repeat within 120k pairs).
- Input differences in words 8–15: a measurable round-0 edge exists (2⁻⁹ to
  2⁻¹⁵ — e.g. `w15.b63` → weight-3 output at ~2⁻⁹), but it **dies by round 1**;
  it cannot be extended a second round above the sampling floor.

**Interpretation.** The most promising differential edge in the cipher cannot be
extended past ~2 rounds under a greedy search. Against 32 rounds this indicates a
large margin. (See limits: greedy ≠ optimal; clustering/hull effects and
sub-threshold trails are not visible to this method.)

### 3.3 Comparative differential (BSR2 vs references)

**Test.** Minimum achievable output difference from a single-bit input difference
at 4 rounds. Ideal ≈ 512; a weak design allows a small value.

| | BSR2 | WEAK (control) | IDEAL |
|-----------------------|:----:|:--------------:|:-----:|
| Diff min-bits @ r4 | **455** | **21** | 447 |

**Interpretation.** This is the test with the most discriminating power in the
battery: the broken control is clearly exposed (21), while BSR2 sits on top of the
ideal reference (455 vs 447). The nonlinear layer is doing the work it exists to
do — with it removed, the differential property collapses.

---

## 4. Linear cryptanalysis (empirical)

**Test.** Maximum absolute bias of single-input-bit → single-output-bit linear
approximations over sampled bit pairs at reduced rounds; N = 3,000–4,000. Noise
floor ≈ 1/√N ≈ 0.016–0.018.

**Results.** Best |bias| observed ≈ **0.02–0.029** at rounds 2–4, consistent with
the sampling noise floor and matching the IDEAL reference (≈0.028) rather than any
structured correlation.

**Interpretation.** No exploitable linear approximation surfaced. (Sampled pairs
only; not a linear-hull proof.)

---

## 5. Other structural tests

| Test | What a break looks like | BSR2 result |
|------|-------------------------|-------------|
| **Bijectivity** (1-round, 200k inputs) | Any collision → not a permutation | 0 collisions |
| **Rotational-XOR** (r6) | P commutes with rotation → distinguisher | mean diff 0.4996 (ideal 0.5) |
| **Integral/saturation** (r5, 256-value active word) | Balanced (zero) output sum → distinguisher | 0 balanced words |
| **Fixed points / symmetry** | Symmetric input class preserved | all-lanes-equal → 16/16 distinct output words; no trivial fixed point |

**Interpretation.** The classic sponge symmetry trap (a symmetric state preserved
by the permutation) is closed by the per-round constant injection into lanes 0 and
15. No integral or rotational distinguisher appeared at the depths tested.

---

## 6. Construction-level analysis

The mode-level attacks that break real deployments (independent of primitive
strength):

| Attack | Break condition | Result |
|--------|-----------------|--------|
| **Length extension** on sponge hash | Forge H(m‖pad‖x) from H(m) without state | 0 forgeries / 20,000 attempts |
| **MAC forgery** (birthday on truncated tag) | Two messages, one tag | 0 collisions / 40,000 (8-byte tags) |
| **Keystream reuse** | Block repeats, or nonce A predicts nonce B | 0 duplicate blocks / 3,000 nonces; adjacent-nonce bit-diff 0.498 |

**Interpretation.**

- **Length-extension resistance** comes from the sponge capacity (768 bits) never
  being output; an attacker who sees the 32-byte rate still lacks the capacity to
  continue absorbing. This is the structural reason `H(secret‖msg)`-style forgery
  (which broke MD5/SHA-1-based MACs) does not apply.
- The **keyed MAC** uses separate inner/outer domains and frames key and message,
  so far without an observed inner-collision path to a forgery.
- The **counter stream** derives each block as an independent keyed MAC of
  `nonce‖counter`, giving no observed cross-nonce correlation.

Note (unchanged from design): the package/envelope `signature` field is a
shared-secret hash, not a digital signature — it detects alteration, not origin.

---

## 7. Statistical battery (large sample)

A 40 MB (335,544,320-bit) keystream was generated from the C reference and tested:

| Test | Result | Pass |
|------|--------|:----:|
| Monobit frequency | p = 0.68 | ✓ |
| Byte uniformity (χ², 255 df) | p = 0.21 | ✓ |
| Runs test (NIST) | p = 0.02 | ✓ |
| Lag-1 serial correlation | +0.00007 | ✓ |
| Byte entropy | 8.00000 bits/byte | ✓ |
| Block-frequency (M=128, 2.6M blocks) | p = 0.35 | ✓ |
| Incompressibility (zlib) | 100.03% | ✓ |

Control: `os.urandom` scored χ² p = 0.49 on the same test — BSR2's output is
statistically indistinguishable from the OS CSPRNG on this battery.

**Interpretation.** No statistical defect detected at this sample size. (Caveat:
statistical batteries catch catastrophic bias, not structural cryptographic
weakness — weak designs routinely pass them. This is a necessary, not sufficient,
result. Running PractRand / dieharder to multi-terabyte depth is recommended as a
stronger follow-up.)

---

## 8. Key-derivation cost

`derive_password_key` was measured at roughly 22 ms/iteration on a single core in
the test environment. At the enforced 10,000-iteration minimum this is ≈3–4 minutes
per derivation, and at the 120,000 default ≈45 minutes, making online and offline
guessing expensive by design. The iteration count is recorded and validated on
read, so a downgraded header is rejected rather than honored.

**Caveat (from DESIGN.md, restated):** this KDF is **not memory-hard**. It raises
time cost but not memory cost, so it is weaker against custom-hardware / ASIC
attackers than a memory-hard function (Argon2/scrypt). This is a known limitation,
not a finding.

---

## 9. Summary of findings

- **No break was found** in any test: differential, linear, rotational, integral,
  bijectivity, symmetry, length-extension, MAC forgery, keystream reuse, or
  statistical.
- On every discriminating test, BSR2 **matches the ideal random-function
  reference** and **separates clearly from the broken control**.
- Diffusion completes by round 3 against 32 rounds — a large empirical margin.
- The most promising differential characteristic dies before round 2 under greedy
  search.

This is a strong first-pass result. It raises confidence that BSR2 is free of
*obvious and moderate* flaws and is therefore worth the time of a formal reviewer.

---

## 10. Limits of this analysis (read this)

The above is empirical, sampled, reduced-round, and single-analyst. It **cannot**
establish security. Specifically it does not rule out:

1. **Deep differential/linear trails.** Greedy search follows locally dominant
   edges; the best *overall* trail can route through locally sub-optimal edges that
   recombine (clustering / hull effect). Only exhaustive **MILP/SAT** modeling gives
   provable lower bounds on active nonlinear operations per round. Not done here.
2. **Sub-threshold characteristics.** Sampling resolves probabilities to ~2⁻¹⁷; a
   characteristic holding at, say, 2⁻²⁵ per round is invisible to these tests but
   could still chain into an attack.
3. **Attack classes not run.** Boomerang, rebound, higher-order/integral at depth,
   division property, algebraic/Gröbner, meet-in-the-middle, invariant-subspace,
   and related-key attacks were not attempted.
4. **Markov-assumption error.** Per-round independence with uniform inputs is a
   standard first-pass approximation, not a theorem; true trail probabilities can
   differ from the product of per-round estimates.
5. **Analyst fallibility.** A harness bug during this work produced a false
   "collision" that was caught only on inspection. Subtler modeling errors over 32
   rounds could go unnoticed.

**Statistical-battery passes prove very little on their own** — broken designs pass
them routinely. The differential and construction results carry more weight, but
remain empirical.

---

## 11. Recommended next steps (toward actual assurance)

1. **MILP/SAT differential model** of the round function → provable per-round bound
   on active nonlinear operations. The single highest-value follow-up; converts
   "no trail found" into "no trail below 2⁻ˣ can exist."
2. **PractRand / dieharder** to multi-terabyte depth using the C reference.
3. **Independent cryptanalysis** by a specialist (the only path to trust).
4. **Public exposure** for adversarial review over time.

Until at least (1) and (3) are done, BSR2's own guidance stands: research software,
not for use as the sole protection of credentials, identity records, or recovery
secrets.
