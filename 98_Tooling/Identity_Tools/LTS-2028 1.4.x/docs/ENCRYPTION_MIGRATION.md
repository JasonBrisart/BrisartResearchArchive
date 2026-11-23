# Encryption Migration

How Identity Tools moves existing data from the previous encryption, BSR2
Alpha 3, to the current one, BSR2 Alpha 4, and what that changes. The
migration shipped in LTS-2028 1.4.0. How the current encryption is linked,
and what it does and does not protect, is in
[BSR2 integration and threat model](BSR2_INTEGRATION.md).

This document is Identity Tools LTS-2028 1.4.x's record of the archive-wide
cryptography migration (root `CHANGELOG.md`, 2026-10-23), in the order that
entry asks for. LTS-2028 1.3.x does not take part in the migration and keeps
vendored BSR2 Alpha 3 (0.3.0-alpha); see [SECURITY.md](SECURITY.md).

The previous encryption, the `migrate` commands, and the migration pop-up
stay in this line until at least 8 February 2027; see
[Supported release lines](SECURITY.md#supported-release-lines).

## Contents

- [Before you migrate](#before-you-migrate)
- [Migrating each store](#migrating-each-store)
- [Previous implementation](#previous-implementation)
- [Replacement implementation](#replacement-implementation)
- [Affected data and formats](#affected-data-and-formats)
- [How existing data is migrated](#how-existing-data-is-migrated)
- [In place or replacement](#in-place-or-replacement)
- [Remaining compatibility with historical data](#remaining-compatibility-with-historical-data)
- [Recovery and rollback limits](#recovery-and-rollback-limits)
- [Tests](#tests)
- [Related documentation](#related-documentation)

## Before you migrate

- **Keep a copy.** Migration is one-way. Migrated data cannot be opened by
  any LTS-2028 1.3.x release.
- **Nothing changes until you agree.** Data in the previous encryption keeps
  opening. Each tool asks before migrating, and declining asks again next time.
- **Your passphrase stays the same.** A recovery code that used the previous
  encryption is replaced by a new one, shown once. Write it down.

## Migrating each store

| Store | Command line | GUI |
| --- | --- | --- |
| Vault | `python -m vault.app --vault <vault file> migrate` | OK in the Vault tab's prompt |
| Biometrics | `python cli.py biometrics migrate` | OK in the Biometrics tab's prompt |
| Package | `python cli.py package migrate <package> --identity-id <id>`, once per recipient | OK in the Packages tab's prompt |

The `migrate` commands ask first; `--yes` skips the question. What each one
decrypts, re-encrypts, and writes is under
[What each store does, and when it writes](#what-each-store-does-and-when-it-writes).

## Previous implementation

Through 1.3.10, BSR2 Alpha 3 (0.3.0-alpha), vendored as four byte-pinned copies
in `vendor/`. Identity Tools used only its legacy constructions: the
`BSR2-ARX-SPONGE-ETM` v2 JSON envelope with an 8-byte length prefix and
256-byte padding added here; the iterated `derive_password_key` (10,000
iterations) for keyring wrappers; a `derive_subkey` + `keyed_mac` binding for
factors; and an unsalted SHA-256 of typed text for package demonstration keys.

## Replacement implementation

BSR2 Alpha 4 (`97_Encryption/Official`, 0.4.0-alpha at the time of writing),
linked through `crypto/encryption.py` and not copied. New data uses sealed
format v3 `BSR2-S64-SIV` (`block` padding), BSR-STREAM-1 above 16 MiB,
BSR2-MHF-1 keyring wrappers (8,192 blocks, one pass), BSR2-S64 MAC factor
bindings and keyring check values, and a BSR2-S64 hash for typed-text package
keys. Master keys, salts, recovery codes, and package content keys come from
BSR2's entropy module.

## Affected data and formats

| Store | Encrypted parts |
| --- | --- |
| Vault file | keyring (both wrappers and check value), every record payload: JSON records, file records, bundle manifests and chunks |
| Biometrics keyring file | both wrappers and check value |
| Biometrics identity files | templates, attachments (including bulk manifests and chunks), device binding |
| Package file | payload, each recipient's key slot and verifier |

## How existing data is migrated

Migration decrypts each item that still uses the previous encryption, BSR2
Alpha 3, and encrypts the same plaintext again with the current one, BSR2 Alpha
4. It changes the encryption only: the master key, every context string, and
every decrypted byte stay the same.

### How old data is recognized

Every sealed value records its own format. `crypto/envelope.py` recognizes the
previous v2 JSON envelope by its six fields (`algorithm` =
`BSR2-ARX-SPONGE-ETM`, `version`, `salt`, `nonce`, `ciphertext`, `tag`), and
the current formats by `{"format": "BSR2-S64-SIV/3" | "BSR-STREAM-1", "data":
...}`. `open_bytes()` chooses the decryptor from that shape, so no caller has
to know which encryption a value uses. Keyrings record, per wrapper, which KDF
derived it (`BSR2/derive_password_key` or `BSR2-MHF-1`), and which MAC produced
the check value.

### Reading without migrating

A legacy value is decrypted in memory with the legacy envelope module that BSR2
Alpha 4 still ships in `97_Encryption/Official`, and this layer's 8-byte length
prefix and padding are removed. Nothing is written back.

### Re-encrypting one payload: `crypto.envelope.reseal()`

1. A value already in a current format is returned unchanged, so running a
   migration twice does nothing the second time.
2. A legacy value is decrypted with the same master key and the same context it
   was sealed under. If it does not authenticate, reseal raises and produces
   nothing; the caller leaves the value as it is and reports it.
3. The recovered plaintext is sealed again under the same master key and
   context, as sealed format v3 (`BSR2-S64-SIV`) up to 16 MiB or `BSR-STREAM-1`
   above that, with fresh randomness.

### Re-encrypting a keyring: `Keyring.migrate(passphrase)`

1. The keyring is unlocked with the passphrase through the legacy KDF. A wrong
   passphrase raises before anything changes, and counts as a failed attempt.
2. The master key is wrapped again under a BSR2-MHF-1 key derived from the same
   passphrase.
3. The recovery code is never stored, so its legacy wrapper cannot be
   re-derived. A new recovery code is generated, its wrapper is written with
   BSR2-MHF-1, and the code is returned to be shown once.
4. The check value is replaced with a BSR2-S64 MAC.

The master key itself never changes, so every payload sealed under it opens at
every point during and after the migration.

### Device bindings and package verifiers

These are keyed MACs, not sealed payloads, so they cannot be decrypted and
re-encrypted. A legacy biometrics device binding is checked against this
machine's fingerprint and, if it matches, replaced with a BSR2-S64 MAC binding.
A binding recorded on another machine is left as it is and reported. Package
verifiers are rebuilt from each recipient's typed text when that recipient
migrates.

### What each store does, and when it writes

- **Vault** (`vault migrate`, or OK in the Vault tab): checks the attempt
  limit, migrates the keyring in memory, reseals every legacy record payload in
  memory (JSON records, file records, and bundle manifests and chunks), then
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
  atomic replacement. The content key never changes, so recipients who have not
  migrated keep opening the package through their legacy key slots.

### When it runs

After a store is unlocked, the CLI prints a note if any part of it still uses
the previous encryption. The GUI shows `crypto.encryption.MIGRATION_NOTICE`
before unlocking or opening such data: OK migrates, and Cancel opens it with
the previous encryption and asks again next time. The `migrate` commands ask
first; `--yes` skips the question.

## In place or replacement

In place. Each file is rewritten by atomic replacement, and no copy of the
previous files is written. The master key and package content keys do not
change.

## Remaining compatibility with historical data

Full read compatibility with everything LTS-2028 1.3.x and Official 1.9.2 and
earlier write, until a later release removes the previous encryption. That
release comes no earlier than 8 February 2027: the read path and the migration
stay in 1.4.x for at least three months after 1.4.0. Reading does not rewrite:
unlocking a store, or declining the migration, leaves it readable by the
release that wrote it (a v1 keyring is kept as stored until a wrapper is
replaced; only attempt-limiting state is written). Migration is resumable:
legacy and migrated items can coexist in one store, and running the migration
again finishes the rest. What can stay legacy after a migration: a vault record
that fails to authenticate under its stored context (KI-005), a device binding
recorded on another machine, and package recipients who have not migrated yet.
Each is reported.

## Recovery and rollback limits

There is no rollback. Migrated data cannot be read by any LTS-2028 1.3.x
release; keep a copy of the files beforehand if that may matter. A recovery
code that used the previous KDF cannot be re-derived, since it is never stored,
so the migration issues a new one, shown once; the old code no longer opens the
migrated keyring but still opens any earlier copy of it. The passphrase is
unchanged.

## Tests

- `crypto/tests/test_encryption_link.py` -- payloads and a binding sealed by
  Identity Tools 1.9.2 with vendored BSR2 Alpha 3 (0.3.0-alpha), the same
  release LTS-2028 1.3.10 vendored, open, reseal to v3 with identical content,
  and re-bind.
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
  encryption.

## Related documentation

- [BSR2 integration and threat model](BSR2_INTEGRATION.md)
- [Security policy](SECURITY.md): supported lines and the migration window
- [Known issues](KNOWN_ISSUES.md): KI-005 explains records that cannot migrate
- [Vault](../vault/README.md), [Biometrics](../biometrics/README.md),
  [Packages](../packages/README.md), [Crypto](../crypto/README.md)
