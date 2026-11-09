# BSR2 Integration and Threat Model

This document describes the application integration with BSR2 and the limits
of the protections implemented by BrisartIdentityTools.

It is not an independent cryptographic assessment.

## Primary caveat

BSR2 is custom, unreviewed research cryptography.

Application validation, context binding, and regression tests do not establish
the security of its original constructions.

BSR2 must not be treated as the sole protection for high-value or irreplaceable
credentials, identity records, recovery secrets, or comparable material.

## Integration boundary

Identity Tools contains no encryption of its own. BSR2 comes from BSR2,
`97_Encryption/Official` in the Brisart Research Archive, which
`crypto/encryption.py` links to as the single point of contact:

```text
BrisartResearchArchive/
├── 95_Identity_Tools/Official/crypto/encryption.py   ─┐ links to
└── 97_Encryption/Official/brisart_security_*.py      ◄┘
```

The link is resolved once per process, on first use, and links every library
module BSR2 ships: `primitives`, `sponge`, `entropy`, `drbg`,
`envelope`, `aead`, `stream`, `kdf`, `keys`, `recovery`, `archive`, `cli`, and
`version` (each `brisart_security_<name>.py`). It also checks the formats
Identity Tools depends on: the legacy `BSR2-ARX-SPONGE-ETM` v2 envelope (data
written before 1.10.0), sealed format v3 `BSR2-S64-SIV`, stream format 1, and
the `BSR2-MHF-1` KDF.

| BSR2 module | Used for |
| --- | --- |
| `aead` | Every new sealed payload up to 16 MiB |
| `stream` | Sealed payloads above 16 MiB |
| `envelope` | Opening and migrating payloads sealed before 1.10.0 |
| `kdf` | New keyring wrappers |
| `sponge` | New bound factors, keyring check values, typed-text package keys |
| `primitives` | Legacy keyring wrappers and bound factors; hex and constant-time comparison |
| `drbg`, `entropy` | The managed generator, master keys, salts, recovery codes, package content keys |
| `cli` (with `keys`, `archive`, `recovery`) | `python cli.py encryption` |

If the directory is missing, a module is missing or fails to import, a module
was already loaded from somewhere else, or a required format differs, the
link is unavailable. The application still starts and shows
`Encryption not found: <reason>` in the GUI status line, Help > About, and
`python cli.py version`. Every operation that seals, opens, derives, or binds
raises `EncryptionNotFoundError` and the CLIs exit with status 3. Nothing falls
back to weaker or local cryptography, and a missing link is never reported as
a wrong passphrase or a non-matching factor.

Three uses of standard-library hashing remain outside the link, none of them
encryption: `packages.ciphers.legacy_text_master_key` (SHA-256), kept only so
packages keyed before 1.10.0 can be opened and migrated, and removed with the
previous encryption; `common/hashing.py` SHA-256 fingerprints of plaintext
files and custody-chain entries, which are stored integrity metadata that
existing files and chains are checked against; and the SHA-1 WS-Security
password digest in `hardware/cameras/onvif_camera.py`, which the ONVIF
protocol prescribes.

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
copy of one, that `cli.py encryption` runs the linked toolkit, and that data
sealed by 1.9.2's vendored BSR2 Alpha 3 (0.3.0-alpha) still opens.
`crypto/tests/test_keyring.py` unlocks and migrates a v1 keyring. BSR2's own
known-answer vectors and tests are run by its own suite. Neither establishes
cryptographic security or independent review.

## Encryption migration

This section is Identity Tools Official's record of the archive-wide
cryptography migration (root `CHANGELOG.md`, 2026-10-23), in the order that
entry asks for.

**Previous implementation.** Through 1.9.2, BSR2 Alpha 3 (0.3.0-alpha),
vendored as four byte-pinned copies in `vendor/`. Identity Tools used only its
legacy constructions: the `BSR2-ARX-SPONGE-ETM` v2 JSON envelope with an 8-byte
length prefix and 256-byte padding added here; the iterated
`derive_password_key` (10,000 iterations) for keyring wrappers; a
`derive_subkey` + `keyed_mac` binding for factors; and an unsalted SHA-256 of
typed text for package demonstration keys.

**Replacement implementation.** BSR2 Alpha 4 (`97_Encryption/Official`,
0.4.0-alpha at the time of writing), linked through `crypto/encryption.py` and
not copied. New data uses sealed format v3 `BSR2-S64-SIV` (`block` padding),
BSR-STREAM-1 above 16 MiB, BSR2-MHF-1 keyring wrappers (8,192 blocks, one
pass), BSR2-S64 MAC factor bindings and keyring check values, and a BSR2-S64
hash for typed-text package keys. Master keys, salts, recovery codes, and
package content keys come from BSR2's entropy module.

**Affected data and formats.**

| Store | Encrypted parts |
| --- | --- |
| Vault file | keyring (both wrappers and check value), every record payload: JSON records, file records, bundle manifests and chunks |
| Biometrics keyring file | both wrappers and check value |
| Biometrics identity files | templates, attachments (including bulk manifests and chunks), device binding |
| Package file | payload, each recipient's key slot and verifier |

**How existing data is migrated.** Migration decrypts each item that still
uses the previous encryption, BSR2 Alpha 3, and encrypts the same plaintext
again with the current one, BSR2 Alpha 4. It changes the encryption only: the
master key, every context string, and every decrypted byte stay the same.

*How old data is recognized.* Every sealed value records its own format.
`crypto/envelope.py` recognizes the previous v2 JSON envelope by its six
fields (`algorithm` = `BSR2-ARX-SPONGE-ETM`, `version`, `salt`, `nonce`,
`ciphertext`, `tag`), and the current formats by
`{"format": "BSR2-S64-SIV/3" | "BSR-STREAM-1", "data": ...}`. `open_bytes()`
chooses the decryptor from that shape, so no caller has to know which
encryption a value uses. Keyrings record, per wrapper, which KDF derived it
(`BSR2/derive_password_key` or `BSR2-MHF-1`), and which MAC produced the check
value.

*Reading without migrating.* A legacy value is decrypted in memory with the
legacy envelope module that BSR2 Alpha 4 still ships in
`97_Encryption/Official`, and this layer's 8-byte length prefix and padding are
removed. Nothing is written back.

*Re-encrypting one payload: `crypto.envelope.reseal()`.*
1. A value already in a current format is returned unchanged, so running a
   migration twice does nothing the second time.
2. A legacy value is decrypted with the same master key and the same context
   it was sealed under. If it does not authenticate, reseal raises and
   produces nothing; the caller leaves the value as it is and reports it.
3. The recovered plaintext is sealed again under the same master key and
   context, as sealed format v3 (`BSR2-S64-SIV`) up to 16 MiB or
   `BSR-STREAM-1` above that, with fresh randomness.

*Re-encrypting a keyring: `Keyring.migrate(passphrase)`.*
1. The keyring is unlocked with the passphrase through the legacy KDF. A
   wrong passphrase raises before anything changes, and counts as a failed
   attempt.
2. The master key is wrapped again under a BSR2-MHF-1 key derived from the
   same passphrase.
3. The recovery code is never stored, so its legacy wrapper cannot be
   re-derived. A new recovery code is generated, its wrapper is written with
   BSR2-MHF-1, and the code is returned to be shown once.
4. The check value is replaced with a BSR2-S64 MAC.

The master key itself never changes, so every payload sealed under it opens at
every point during and after the migration.

*Device bindings and package verifiers.* These are keyed MACs, not sealed
payloads, so they cannot be decrypted and re-encrypted. A legacy biometrics
device binding is checked against this machine's fingerprint and, if it
matches, replaced with a BSR2-S64 MAC binding. A binding recorded on another
machine is left as it is and reported. Package verifiers are rebuilt from each
recipient's typed text when that recipient migrates.

*What each store does, and when it writes.*
- **Vault** (`vault migrate`, or OK in the Vault tab): checks the attempt
  limit, migrates the keyring in memory, reseals every legacy record payload
  in memory (JSON records, file records, and bundle manifests and chunks), then
  writes the whole vault file once by atomic replacement. Any failure before
  that write leaves the file exactly as it was.
- **Biometrics** (`biometrics migrate`, or OK in the Biometrics tab): migrates
  the keyring and writes the keyring file first, then goes through each
  identity file. It reseals the file's templates and attachments, re-binds a
  legacy device binding that matches this machine, and writes that file by
  atomic replacement only if something changed. If the run is interrupted,
  migrated and legacy identity files coexist and all of them still open;
  running the migration again finishes the rest.
- **Packages** (`package migrate --identity-id <id>`, or OK in the Packages
  tab): one recipient at a time, from that recipient's typed text. Both text
  keys are derived, the legacy SHA-256 one and the current BSR2-S64 one, and
  whichever the recipient's verifier accepts is used to open that recipient's
  key slot and recover the package content key. The payload is resealed under
  the content key if it is still legacy. The content key is then wrapped in a
  new key slot under the current text key, the verifier is rebuilt, and a
  `payload_rewrapped` custody entry is added. The package file is written by
  atomic replacement. The content key never changes, so recipients who have
  not migrated keep opening the package through their legacy key slots.

*When it runs.* After a store is unlocked, the CLI prints a note if any part
of it still uses the previous encryption. The GUI shows
`crypto.encryption.MIGRATION_NOTICE` before unlocking or opening such data: OK
migrates, and Cancel opens it with the previous encryption and asks again next
time. The `migrate` commands ask first; `--yes` skips the question.

**In place or replacement.** In place. Each file is rewritten by atomic
replacement, and no copy of the previous files is written. The master key and
package content keys do not change.

**Remaining compatibility with historical data.** Full read compatibility with
everything Official 1.9.2 and earlier and LTS-2028 1.3.x write, until a
later release removes the
previous encryption. Reading does not rewrite: unlocking a store, or declining
the migration, leaves it readable by the release that wrote it (a v1 keyring is
kept as stored until a wrapper is replaced; only attempt-limiting state is
written). Migration is resumable: legacy and migrated items can
coexist in one store, and running the migration again finishes the rest. What
can stay legacy after a migration: a vault record that fails to authenticate
under its stored context (KI-005), a device binding recorded on another
machine, and package recipients who have not migrated yet. Each is reported.

**Recovery and rollback limits.** There is no rollback. Migrated data cannot be
read by Official 1.9.2 and earlier or any LTS-2028 1.3.x release (LTS-2028
1.4.x reads it);
keep a copy of the files beforehand if that may
matter. A recovery code that used the previous KDF cannot be re-derived, since
it is never stored, so the migration issues a new one, shown once; the old
code no longer opens the migrated keyring but still opens any earlier copy of
it. The passphrase is unchanged.

**Tests.**
- `crypto/tests/test_encryption_link.py` -- payloads and a binding sealed by
  1.9.2 itself open, reseal to v3 with identical content, and re-bind.
- `crypto/tests/test_envelope.py` -- current formats round trip and reject
  tampering; legacy envelopes reseal; a wrong key or context never reseals.
- `crypto/tests/test_keyring.py` -- current keyrings; `migrate()` on a legacy
  check value, with a wrong passphrase, and (slow) on a real v1 keyring,
  including the new recovery code.
- `vault/tests/test_vault_migration.py` -- a legacy vault reads, migrates
  completely, survives a wrong passphrase, reports an unauthenticated record,
  migrates nothing the second time, and (slow) migrates on a real v1 keyring.
- `biometrics/tests/test_encryption_migration.py` -- a legacy data directory
  reads, migrates templates, attachments, and this machine's device binding,
  keeps other machines' bindings and the attempt state, and survives a wrong
  passphrase.
- `packages/tests/test_package_migration.py` -- a legacy package opens from
  typed text, migrates one recipient without locking out the other, migrates
  completely, and survives wrong text.
- `packages/tests/test_demo.py` -- the demo runs a full cycle on the new
  encryption, and a saved demo package opens from its saved passphrase.

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
factor name and value. Records written before 1.10.0 use the legacy derived
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

Sealing has no per-payload size limit since 1.10.0; bulk chunking bounds the
size of each sealed record, not overall resource use.

Path bundles are materialized as plaintext temporary ZIP files and read
completely into memory. Restore also reassembles complete content.

Bulk workflows are not bounded-memory streaming, sector-level disk imaging,
consistent live-filesystem snapshots, or secure-erasure mechanisms.

Unreadable files can be skipped. Restore can leave partial output if
interrupted.

## Protection limits

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
