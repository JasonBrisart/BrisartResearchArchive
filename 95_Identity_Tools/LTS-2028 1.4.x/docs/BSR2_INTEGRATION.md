# BSR2 Integration and Threat Model

This document describes the application integration with BSR2 and the limits
of the protections implemented by BrisartIdentityTools.

It is not an independent cryptographic assessment.

## Contents

- [Primary caveat](#primary-caveat)
- [What these tools do not protect against](#what-these-tools-do-not-protect-against)
- [Integration boundary](#integration-boundary)
- [Encryption migration](#encryption-migration)
- [Master keys and wrapping](#master-keys-and-wrapping)
- [KDF parameters and runtime](#kdf-parameters-and-runtime)
- [Factor protection](#factor-protection)
- [Context binding](#context-binding)
- [Length padding](#length-padding)
- [Random-generator lifecycle](#random-generator-lifecycle)
- [Attempt limiting](#attempt-limiting)
- [Vault protection and disclosure](#vault-protection-and-disclosure)
- [Biometrics protection and disclosure](#biometrics-protection-and-disclosure)
- [Packages protection and disclosure](#packages-protection-and-disclosure)
- [Custody chains and audit files](#custody-chains-and-audit-files)
- [Filesystem hardening](#filesystem-hardening)
- [Bulk-file boundaries](#bulk-file-boundaries)

## Primary caveat

BSR2 is custom, unreviewed research cryptography.

Application validation, context binding, and regression tests do not establish
the security of its original constructions.

BSR2 must not be treated as the sole protection for high-value or irreplaceable
credentials, identity records, recovery secrets, or comparable material.

## What these tools do not protect against

These are limits of the design, not bugs. Each one stays true however
carefully the tools are used. Open bugs are tracked separately in
[Known issues](KNOWN_ISSUES.md).

### The encryption itself

**BSR2 is unreviewed research cryptography.** No one outside this project has
analysed it, and the constructions new in BSR2 Alpha 4 (sealed format v3,
BSR-STREAM-1, and BSR2-MHF-1) have had no analysis at all. Tests show that the
code does what it was written to do, not that the construction is secure.

*What you can do:* don't make these tools the only protection for anything you
can't afford to lose or expose.

**Timing is not guaranteed constant.** Checks that compare a secret value,
such as keyring check values and factor bindings, use a constant-time
comparison. Everything else, including BSR2 itself, runs as ordinary Python,
whose timing depends on the values it handles. Someone who can measure timing
precisely on the same machine may learn something about keys.

*What you can do:* don't run the tools on a machine shared with people you
don't trust.

### While the tools are running

**An unlocked master key sits in memory.** While a vault or biometrics
keyring is unlocked, its master key is held in the process. Locking drops the
tools' reference to it, but Python cannot wipe memory, so copies can remain
until the memory is reused, and can reach swap files or crash dumps. In the
GUI, a store stays unlocked until you press Lock or close the window. Each CLI
command unlocks, runs, and exits.

*What you can do:* lock when you finish, and treat a machine where someone can
read process memory as one where the key is exposed.

### Files on disk

**Some information is readable without a passphrase.** Only payloads are
encrypted. Without unlocking, anyone with the files can read:

- **Vault:** every record's id, label, kind, and created and updated times.
  File records also show the original filename, its size, and the SHA-256 of
  its contents, so anyone holding a copy of a file can confirm it is in the
  vault.
- **Biometrics:** each identity's id and label, which modalities are enrolled,
  and each attachment's filename, size, and SHA-256.
- **Packages:** the package id, each recipient's id and label, and the custody
  chain.

*What you can do:* use labels and filenames that reveal nothing you'd mind
being read.

**The lock and what it protects are stored together.** A vault keeps its
keyring inside the same `vault.json` as its records. Biometrics keeps
`data/keyring.json` next to `data/identities/`. Anyone who copies those files
has everything needed to try passphrases offline, at their own speed, with
nothing but the passphrase in the way.

*What you can do:* use a long passphrase, and keep the files on encrypted,
access-controlled storage.

**A leaked master key can't be taken back.** Changing the passphrase or
issuing a new recovery code re-wraps the same master key; it does not replace
it. The encryption migration also keeps the master key. If a master key is
ever exposed, everything sealed under it can be opened, including data written
before the exposure and after a migration.

*What you can do:* if you suspect exposure, create a new vault or keyring and
move your data into it.

**Attempt limits only slow down guessing through these tools.** Failed
unlocks are counted inside the same file they protect (`unlock_attempts`).
Anyone who can edit the file can reset the count, and someone working on a
copy is never limited at all.

*What you can do:* rely on passphrase strength, not on the lockout.

**Two programs writing the same file can lose an update.** Writes are atomic,
so a file is never left half-written, but there is no locking between
processes. If two run at once, the last write wins.

*What you can do:* use one program at a time on any given vault, keyring, or
package.

**Bundles pass through plaintext on disk.** Bundling files, folders, or
drives (`encrypt-paths`, `attach-paths`) first writes an unencrypted ZIP to a
temporary directory, and the whole bundle is held in memory. Restoring writes
the rebuilt ZIP to a temporary directory again before extracting it. The
temporary directory is deleted afterwards, but deletion is not secure erasure,
and an interrupted restore can leave partial output. See KI-003.

*What you can do:* make sure the temporary directory is on storage you trust,
and check restored output if a restore was interrupted.

### Biometrics

**Matching is research-grade.** Similarity scores are measurements, not
probabilities that the right person was identified. The video check detects
motion only: it rejects a still photo, but not a replayed recording, a mask,
or a photo moved in front of the camera. Its threshold has only been checked
against synthetic samples, not real cameras (KI-001). Voice and fingerprint
have no liveness check at all.

*What you can do:* don't use biometric verification as the only gate to
anything.

### Packages and records

**The package demo key is not a real password key.** The CLI and GUI turn
typed text into a key with one fast, unsalted hash. Guessable text gives a
guessable key, and the same text always gives the same key.

*What you can do:* use the demo to see how packages work, not to protect real
data.

**Custody chains and audit files can be rewritten.** The custody chain links
entries with unkeyed hashes, so anyone who can edit a package can rewrite its
whole chain consistently, or cut off its newest entries. Actor labels are free
text that no one verifies. Audit and report files are ordinary files.

*What you can do:* keep copies somewhere the people you're checking can't
write to.

## Integration boundary

Identity Tools contains no encryption of its own. BSR2 comes from
`97_Encryption/Official` in the Brisart Research Archive, which
`crypto/encryption.py` links to as the single point of contact:

```text
BrisartResearchArchive/
├── 95_Identity_Tools/LTS-2028 1.4.x/crypto/encryption.py   ─┐ links to
└── 97_Encryption/Official/brisart_security_*.py            ◄┘
```

The link is resolved once per process, on first use, and links every library
module BSR2 ships: `primitives`, `sponge`, `entropy`, `drbg`,
`envelope`, `aead`, `stream`, `kdf`, `keys`, `recovery`, `archive`, `cli`, and
`version` (each `brisart_security_<name>.py`). It also checks the formats
Identity Tools depends on: the legacy `BSR2-ARX-SPONGE-ETM` v2 envelope (data
written before 1.4.0), sealed format v3 `BSR2-S64-SIV`, stream format 1, and
the `BSR2-MHF-1` KDF.

| BSR2 module | Used for |
| --- | --- |
| `aead` | Every new sealed payload up to 16 MiB |
| `stream` | Sealed payloads above 16 MiB |
| `envelope` | Opening and migrating payloads sealed before 1.4.0 |
| `kdf` | New keyring wrappers |
| `sponge` | New bound factors, keyring check values, typed-text package keys |
| `primitives` | Legacy keyring wrappers and bound factors; hex and constant-time comparison |
| `drbg`, `entropy` | The managed generator, master keys, salts, recovery codes, package content keys |
| `cli`, `keys`, `archive`, `recovery` | Linked and checked, not used by LTS-2028 (Official's `python cli.py encryption`) |

If the directory is missing, a module is missing or fails to import, a module
was already loaded from somewhere else, or a required format differs, the
link is unavailable. The application still starts, and each operation that
needs encryption reports `Encryption not found: <reason>` through the normal
error dialog or CLI error. Every operation that seals, opens, derives, or binds
raises `EncryptionNotFoundError` and the CLIs exit with status 3. Nothing falls
back to weaker or local cryptography, and a missing link is never reported as
a wrong passphrase or a non-matching factor.

Two uses of standard-library hashing remain outside the link, neither of them
encryption: `packages.ciphers.legacy_text_master_key` (SHA-256), kept only so
packages keyed before 1.4.0 can be opened and migrated, and removed with the
previous encryption; `common/hashing.py` SHA-256 fingerprints of plaintext
files and custody-chain entries, which are stored integrity metadata that
existing files and chains are checked against.

The application integration layer handles:

- Payload sealing and opening.
- JSON serialization and padding.
- Master-key wrapping.
- Context construction.
- Factor binding.
- Generator lifecycle management.
- Unlock-attempt limiting.

`crypto/tests/test_encryption_link.py` checks that every module BSR2 ships is
linked and loaded from the linked directory, that the application tree holds no
copy of one, and that data sealed by vendored BSR2 Alpha 3 (0.3.0-alpha), the
release LTS-2028 shipped through 1.3.10, still opens.
`crypto/tests/test_keyring.py` unlocks and migrates a v1 keyring. BSR2's own
known-answer vectors and tests are run by its own suite. Neither establishes
cryptographic security or independent review.

## Encryption migration

Moving data from the previous encryption (BSR2 Alpha 3) to the current one,
which shipped in 1.4.0, has its own document:
[Encryption migration](ENCRYPTION_MIGRATION.md). It is this line's record of
the archive-wide cryptography migration: the previous and replacement
implementations, affected formats, how data is migrated, compatibility,
rollback limits, and tests.

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

New keyring wrappers use the memory-hard BSR2-MHF-1 at 8,192 blocks (1 MiB)
and one pass. Its parameters and salt are stored per wrapper and validated on
load against ceilings of 65,536 blocks and four passes. Legacy wrappers keep
their stored iteration count, validated against 10,000 to 1,000,000.

Rejecting out-of-range counts reduces parameter-abuse opportunities. It does
not establish that every accepted parameter is appropriate for every
deployment.

KDF runtime depends on parameters, hardware, interpreter, and system load.
Earlier development-machine measurements are historical observations, not fixed
latency guarantees.

Separate CLI invocations do not share an unlocked in-memory session.

## Factor protection

Factors are bound under the master key with a BSR2-S64 MAC over the framed
factor name and value. Records written before 1.4.0 use the legacy derived
subkey and keyed MAC and still verify. No password-derived factor hashes are
stored.

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

v3 sealed messages use BSR2's `block` padding (256-byte
buckets) inside the authenticated payload. Stream payloads above 16 MiB are not
padded. Legacy payloads carry the earlier length prefix and padding added by
this layer.

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

The CLI and GUI demonstration prompts turn typed text into a key with one
unsalted BSR2-S64 hash (`packages.ciphers.text_master_key`). This is not a slow
password KDF. Packages written before the encryption migration used one
unsalted SHA-256; that key still opens them until each recipient migrates.

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

Sealing has no per-payload size limit since 1.4.0; bulk chunking bounds the
size of each sealed record, not overall resource use.

Path bundles are materialized as plaintext temporary ZIP files and read
completely into memory. Restore also reassembles complete content.

Bulk workflows are not bounded-memory streaming, sector-level disk imaging,
consistent live-filesystem snapshots, or secure-erasure mechanisms.

Unreadable files can be skipped. Restore can leave partial output if
interrupted.

## Related documentation

- [Encryption migration](ENCRYPTION_MIGRATION.md)
- [Known issues](KNOWN_ISSUES.md)
- [Security policy](SECURITY.md)
- [File and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md)
- [Vault](../vault/README.md)
- [Biometrics](../biometrics/README.md)
- [Packages](../packages/README.md)
