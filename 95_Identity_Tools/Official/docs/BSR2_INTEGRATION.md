# BSR2 Integration and Threat Model

This document describes the application integration with BSR2 and the limits
of the protections implemented by BrisartIdentityTools.

It is not an independent cryptographic assessment.

## Primary caveat

BSR2 is custom, unreviewed research cryptography.

Application validation, context binding, regression tests, and file-integrity
pins do not establish the security of its original constructions.

BSR2 must not be treated as the sole protection for high-value or irreplaceable
credentials, identity records, recovery secrets, or comparable material.

## Integration boundary

The supplied BSR2 files provide primitives used by `crypto/`.

The application integration layer handles:

- Payload sealing and opening.
- JSON serialization and padding.
- Master-key wrapping.
- Context construction.
- Factor binding.
- Generator lifecycle management.
- Unlock-attempt limiting.

The supplied vendor-integrity test compares file bytes against pinned digests.
A matching digest establishes agreement with that pin, not upstream
authenticity, independent review, or cryptographic security.

## Master keys and wrapping

Vault and Biometrics use a random 32-byte master key for application payloads.

The keyring wraps that key under:

- A passphrase-derived key.
- A recovery-code-derived key.

Unlocking derives a wrapping key and opens the corresponding wrapper.
Subsequent operations within that unlocked session reuse the master key.

Changing a passphrase rewraps the master key rather than re-encrypting every
payload.

The recovery code is another route to the same master key. It is not
lower-privilege access.

The generated recovery code contains 40 Crockford-base32 characters. The
implementation displays it during creation and does not provide a later
plaintext retrieval operation.

## KDF parameters and runtime

Iteration counts are stored and validated against the integration's accepted
range.

Rejecting out-of-range counts reduces parameter-abuse opportunities. It does
not establish that every accepted parameter is appropriate for every
deployment.

KDF runtime depends on iteration count, hardware, interpreter, and system
load. Earlier development-machine measurements are historical observations,
not fixed latency guarantees.

Separate CLI invocations do not share an unlocked in-memory session.

## Factor protection

Password-derived factors use the slow KDF path.

Master-key-bound factors use derived subkeys and keyed MACs.

The fast binding path relies on the master key remaining protected. Device
identifiers, machine information, and template digests are not automatically
secret or high-entropy inputs.

Factor names and values are framed and bound to their expected roles.
This prevents some cross-role substitution within the integration's model;
it is not proof of a real-world identity.

## Context binding

Sealed objects use context strings identifying their application role, such
as a record, template, package payload, recipient key slot, or keyring wrapper.

Opening supplies the expected context. An envelope moved to a different
context should fail authentication.

Context binding does not independently authenticate the caller or authorize
an operation.

## Length padding

The integration prefixes the original length and pads plaintext to 256-byte
buckets before sealing.

Padding is inside the authenticated plaintext.

Ciphertext length still reveals a size bucket. Surrounding filenames, labels,
counts, timestamps, and other metadata can disclose additional information.

## Random-generator lifecycle

The integration seeds its managed generator from operating-system entropy and
handles generator lifecycle limits.

A deterministic generator expands entropy; it does not create entropy.
Lifecycle handling is not independent validation of the generator's security.

## Attempt limiting

Vault and Biometrics persist attempt state in their JSON containers.

The default limiter uses exponential retry delays, capped at 300 seconds,
and a 900-second lockout after the fifth failure.

Vault passphrase and recovery-code unlocks share attempt state. Biometrics
CLI and GUI passphrase unlocks use the shared keyring-access module.

Limits:

- Stored attempt state is editable and unauthenticated.
- Copied files can be attacked offline.
- A party able to edit state can reset it.
- Concurrent processes do not have a distributed or transactional counter.
- Package demonstration key prompts do not receive equivalent password-KDF
  protection merely because other tools use a keyring.

## Vault protection and disclosure

Vault record payloads are sealed.

Record-shell metadata remains readable, including identifiers, kinds, labels,
and timestamps. File records can expose original filenames, sizes, and
plaintext SHA-256 fingerprints.

A fingerprint can reveal that protected content matches a known candidate.

The keyring is stored with the data it protects. Knowledge of an unlocking
secret or access to the unwrapped master key defeats payload confidentiality.

## Biometrics protection and disclosure

Template payloads are sealed under a local master key and bound to identity
and modality contexts.

Identity metadata remains readable.

Machine binding is a weak keyed check over machine information. It is not
hardware-backed identity or an independent security boundary.

Matching is hand-built, threshold-based feature comparison. It is not a
trained or population-calibrated biometric authentication system.

Video motion checks are not general anti-spoofing. Voice and fingerprint
matching do not supply equivalent liveness checks.

Stored verification reports omit the complete video motion/liveness result.
They cannot fully reconstruct every gate decision.

## Packages protection and disclosure

A content key seals the payload. Recipient master keys wrap that content key
into recipient slots.

Creating or adding recipients requires their master keys. This is symmetric
key distribution, not public-key encryption.

Removing a recipient does not revoke old package copies, previously obtained
content keys, or previously recovered plaintext.

The CLI and GUI demonstration prompts hash typed text once with unsalted
SHA-256. This is not a slow password KDF.

Package saves from the CLI and GUI use atomic replacement, so an interrupted
save does not truncate package state. Concurrent saves can still lose an
update.

## Custody chains and audit files

Custody entries use unkeyed hash links. Verification checks internal
consistency, not authenticated authorship or complete history.

A party able to rewrite the chain can recompute hashes. Removing a valid
suffix can leave a valid shorter chain.

Actor labels are caller-supplied text.

External audit and report files use append-style application behavior.
Filesystem permissions do not make them inherently append-only, immutable,
or authenticated.

Where the current application supplies an integrity ledger, the same
unkeyed-chain limitations apply. Checkpoints also miss changes and exact
reversions occurring entirely between observations.

## Filesystem hardening

Sensitive writes request POSIX `0600` permissions through the atomic-write
helper.

This is best effort:

- Tightening occurs after replacement.
- Permission failures are swallowed.
- Temporary plaintext and intermediate files require separate consideration.
- Windows ACL enforcement is outside these POSIX checks.

Atomic replacement reduces partial destination writes. It does not provide
multi-file transactions, concurrent-writer locking, or universal power-loss
durability.

## Bulk-file boundaries

Chunking bypasses the per-envelope size limit, not resource limits.

Path bundles are materialized as plaintext temporary ZIP files and read
completely into memory. Restore also reassembles complete content.

Bulk workflows are not bounded-memory streaming, sector-level disk imaging,
consistent live-filesystem snapshots, or secure-erasure mechanisms.

Unreadable files can be skipped. Restore can leave partial output if
interrupted.

## Residual risks

- Unreviewed cryptographic constructions.
- Python execution without whole-program constant-time guarantees.
- Master keys in process memory.
- Readable metadata and plaintext fingerprints.
- Keyrings co-located with protected data.
- No forward secrecy for data protected by a compromised master key.
- Research-grade biometric matching and limited motion checks.
- Editable attempt counters and concurrent-writer limitations.
- Demonstration package text-to-key derivation.
- Unauthenticated custody labels and rewritable local audit history.
- Memory, temporary-storage, throughput, and partial-restore limits.
- Optional hardware logic without physical-device validation.

## Related documentation

- KNOWN_ISSUES.md
- [Security policy](SECURITY.md)
- [File and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md)
- ../vault/README.md
- ../biometrics/README.md
- ../packages/README.md
