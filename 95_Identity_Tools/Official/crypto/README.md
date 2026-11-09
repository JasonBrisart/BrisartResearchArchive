# Crypto Integration Layer

Application integration between BSR2 and Vault, Biometrics, and Packages.

This directory composes BSR2 primitives from the linked BSR2
(`97_Encryption/Official`) into application operations. It does not independently validate the security of those
primitives.

## Module map

| Module | Responsibility |
| --- | --- |
| `encryption.py` | The one link to BSR2: locates `97_Encryption/Official`, links every library module, reports `Encryption not found` when it is absent or incompatible, and hands out the library per call |
| `errors.py` | Application-facing integration exception types |
| `context.py` | Context strings for records, templates, packages, key slots, and keyring wrappers |
| `envelope.py` | Byte and JSON sealing/opening: v3 sealed messages, BSR-STREAM-1 above 16 MiB, legacy v2 envelopes read-only |
| `keyring.py` | Master-key creation, BSR2-MHF-1 passphrase and recovery wrapping, unlocking, rewrapping, legacy v1 keyrings |
| `factors.py` | Master-key-bound factor records (BSR2-S64 MAC; legacy keyed MAC read-only) |
| `rng.py` | BSR2 DRBG seeded from its health-checked entropy, with lifecycle handling |
| `throttle.py` | Retry delays and lockout decisions |
| `attempt_store.py` | Persisted attempt-state integration for Vault and Biometrics |

## Encryption link

Every module here calls `encryption.require()` when an operation runs, never
at import time. Without BSR2 the whole application still
imports and starts; each operation that needs encryption raises
`EncryptionNotFoundError` instead. See
[BSR2 integration](../docs/BSR2_INTEGRATION.md#integration-boundary).

## Context binding

Context strings identify the application object a payload belongs to.

Opening uses the expected context. Moving an envelope into a different
identity, modality, record, or key-slot context should fail authentication.

This is object binding, not proof of the caller's identity or authorization.

## Formats

The encryption migration shipped in Official 1.10.0 and LTS-2028 1.4.0; both
lines write and read the same formats.

| Data | Written since the migration | Still read |
| --- | --- | --- |
| Sealed payloads up to 16 MiB | `BSR2-S64-SIV/3` (`aead`) | `BSR2-ARX-SPONGE-ETM` v2 |
| Sealed payloads above 16 MiB | `BSR-STREAM-1` (`stream`) | — |
| Keyring wrappers | `BSR2-MHF-1` (`kdf`) | `BSR2/derive_password_key` |
| Bound factors | `bsr2$mac64$…` (`sponge`) | `bsr2$keyed_mac$…` |
| Package typed-text keys | BSR2-S64 hash (`sponge`) | SHA-256 |

Nothing rewrites legacy data on read. Legacy data moves to the current formats
through each store's migration (`vault migrate`, `biometrics migrate`,
`package migrate`, or the GUI prompt), all built on `envelope.reseal()` and
`Keyring.migrate()`. The legacy readers stay until a later release removes the
previous encryption; see
[BSR2 integration](../docs/BSR2_INTEGRATION.md#encryption-migration).

## Padding

v3 sealed messages use BSR2's `block` padding, 256-byte buckets,
inside the authenticated payload. Stream payloads are not padded.

Ciphertext length still reveals a bucket and other surrounding metadata.
Padding is not complete traffic or size concealment.

## Keyring model

A random master key protects application payloads.

Passphrase-derived and recovery-code-derived keys wrap that master key. New
wrappers derive their key with the memory-hard BSR2-MHF-1 (1 MiB, one pass by
default), with parameters stored per wrapper.
Unlocking derives a wrapping key; subsequent operations in the same session
reuse the unwrapped master key.

Separate processes do not automatically share an unlocked session.

KDF runtime depends on parameters and the execution environment. Historical
timings are not fixed performance guarantees.

## Factor handling

`bind_factor()` and `verify_bound_factor()` use a keyed binding under the
master key. Identity Tools stores no password-derived factor hashes; the
unused `hash_factor()` path was removed in the encryption migration.

The fast binding path relies on protection of the master key. Device names,
device identifiers, template digests, and similar values must not automatically
be described as secret or high-entropy simply because they use this path.

A keyed binding can prevent verification without the key; it does not make
predictable input unpredictable.

## Generator management

`rng.py` seeds the BSR2 DRBG from its health-checked
operating-system entropy and manages request and byte lifecycle limits. v3 and
stream seals XOR its output with fresh system entropy.

The generator expands supplied entropy. It does not create entropy or
establish independent cryptographic assurance.

## Attempt limiting

Vault and Biometrics persist attempt state in their JSON containers.

The default limiter uses exponential delays and a lockout after repeated
failures.

This is not distributed coordination or an authenticated, tamper-resistant
counter. It does not prevent offline guessing against copied files, and a
party able to edit the stored state can reset it.

## Error handling

Application callers use the exception family in `errors.py`.

Authentication errors and malformed-data errors are not universally
interchangeable. Callers should handle the documented exception types rather
than assuming every invalid input produces one uniform message.

## Tests and trust

Regression tests exercise integration behavior. They do not prove BSR2's
cryptographic security or constant-time behavior throughout Python execution.

BSR2 is custom, unreviewed research cryptography and must not be the sole
protection for high-value or irreplaceable secrets.

See [BSR2 integration and threat model](../docs/BSR2_INTEGRATION.md).
