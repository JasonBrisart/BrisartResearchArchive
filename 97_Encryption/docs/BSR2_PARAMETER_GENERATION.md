# BSR2 Parameter Generation

This document describes how the fixed BSR2 parameters are generated.

The goal is reproducibility, transparency, and auditability.

Parameter generation documents provenance.

Parameter generation does not establish cryptographic security.

---

## Purpose

BSR2 uses a collection of fixed parameters including:

- Round constants
- Structural mixing constants
- Rotation values
- Word permutation values

Rather than selecting these values manually, BSR2 generates them deterministically from a public seed.

This allows anyone to regenerate the same values independently and verify that the implementation matches the documented generation procedure.

---

## Generator Location

Parameter generation is performed by:

```text
tools/generate_bsr2_parameters.py
```

Embedded parameters are stored in:

```text
brisart_security_primitives.py
```

Verification tests are located in:

```text
tests/test_bsr2_parameters.py
```

---

## Design Goals

The parameter generator was created to provide:

- Reproducibility
- Transparency
- Auditability
- Deterministic output
- Public provenance

The generator was not designed to prove cryptographic strength.

The generated values should be viewed as implementation parameters rather than validated cryptographic constants.

---

## Public Seed

BSR2 uses a fixed public seed value.

The generator uses this seed as input to produce all embedded parameters.

The seed is intentionally public.

Publishing the seed allows independent reproduction of every generated value.

A public seed is not intended to provide secrecy.

---

## Generated Values

The generator produces four categories of parameters.

### Round Constants

Round constants are generated for use during permutation rounds.

These values introduce round-specific variation into the permutation process.

Generated count:

```text
24 round constants
```

---

### Structural Mixing Constants

Additional fixed constants are generated for structural mixing operations.

Generated count:

```text
3 structural constants
```

---

### Rotation Values

Rotation values control bit movement during permutation operations.

Generated count:

```text
8 rotation values
```

Current values:

```text
34, 5, 38, 37, 31, 50, 59, 17
```

---

### Word Permutation

A complete permutation of the state-word indices is generated.

Generated count:

```text
16 positions
```

Current permutation:

```text
6, 11, 12, 0, 5, 15, 2, 14, 3, 13, 4, 7, 10, 9, 8, 1
```

---

## State Structure

The generated parameters support a permutation operating on:

```text
16 state words
64 bits per word
1024 total state bits
```

The default permutation configuration uses:

```text
32 rounds
```

---

## Reproducibility

The generation process is deterministic.

Given:

- The same source code
- The same public seed
- The same generation procedure

the generator should always produce the identical set of parameters.

Expected outputs include:

- Round constants
- Structural constants
- Rotation values
- Word permutation

Any deviation indicates either:

- A source-code change
- A seed change
- A generation-process change

---

## Verification

Parameter reproducibility is verified through:

```text
tests/test_bsr2_parameters.py
```

The test suite verifies:

- Round constant count
- Structural constant count
- Rotation count
- Rotation bounds
- Word permutation shape
- Parameter uniqueness requirements
- Exact equality between generated and embedded values

The test suite does not evaluate cryptographic strength.

The test suite only verifies consistency between generation and implementation.

---

## Updating Parameters

Parameter regeneration should be considered a breaking change.

Changing generated parameters may affect:

- Hash outputs
- MAC outputs
- DRBG outputs
- Stream outputs
- Envelope outputs
- Known-answer vectors

Any intentional parameter change should be accompanied by:

- Updated embedded parameters
- Updated known-answer vectors
- Updated tests
- Updated documentation
- Updated changelog entries
- Fresh research results

---

## Relationship To Known-Answer Vectors

Known-answer vectors depend on the generated parameters.

If parameters change, vector outputs may also change.

Because of this relationship:

```text
Parameter changes and vector changes should be reviewed together.
```

---

## Security Considerations

Reproducible generation improves auditability.

Reproducible generation does not establish:

- Collision resistance
- Preimage resistance
- Differential resistance
- Algebraic resistance
- Stream indistinguishability
- Authentication-forgery resistance
- Production security

The generated values have not undergone independent cryptanalysis.

The existence of a public generation process should not be interpreted as evidence of cryptographic strength.

---

## Summary

BSR2 generates its fixed parameters deterministically from a public seed.

The generation process exists to improve:

- Transparency
- Reproducibility
- Auditability

The generator allows independent verification that the implementation matches the documented parameter-generation process.

The generator does not establish cryptographic security and should be viewed as implementation provenance rather than security proof.