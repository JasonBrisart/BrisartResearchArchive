# Crypto Integration Layer

Application integration between BSR2 and Vault, Biometrics, and Packages.

This directory composes the supplied BSR2 primitives into application
operations. It does not independently validate the security of those
primitives.

## Module map

| Module | Responsibility |
| --- | --- |
| `vendor.py` | Makes the supplied flat-import BSR2 modules available and re-exports their interfaces |
| `errors.py` | Application-facing integration exception types |
| `context.py` | Context strings for records, templates, packages, key slots, and keyring wrappers |
| `envelope.py` | Byte and JSON sealing/opening, including length-prefix padding |
| `keyring.py` | Master-key creation, passphrase and recovery wrapping, unlocking, and rewrapping |
| `factors.py` | Slow password-derived factors and fast master-key-bound factors |
| `rng.py` | OS-entropy-seeded generator management and lifecycle handling |
| `throttle.py` | Retry delays and lockout decisions |
| `attempt_store.py` | Persisted attempt-state integration for Vault and Biometrics |

## Context binding

Context strings identify the application object a payload belongs to.

Opening uses the expected context. Moving an envelope into a different
identity, modality, record, or key-slot context should fail authentication.

This is object binding, not proof of the caller's identity or authorization.

## Padding

The integration layer prefixes the original length and pads plaintext into
256-byte buckets before sealing.

Ciphertext length still reveals a bucket and other surrounding metadata.
Padding is not complete traffic or size concealment.

## Keyring model

A random master key protects application payloads.

Passphrase-derived and recovery-code-derived keys wrap that master key.
Unlocking derives a wrapping key; subsequent operations in the same session
reuse the unwrapped master key.

Separate processes do not automatically share an unlocked session.

KDF runtime depends on parameters and the execution environment. Historical
timings are not fixed performance guarantees.

## Factor handling

`hash_factor()` and `verify_factor()` use the password-KDF path.

`bind_factor()` and `verify_bound_factor()` use master-key-derived keyed
binding.

The fast binding path relies on protection of the master key. Device names,
device identifiers, template digests, and similar values must not automatically
be described as secret or high-entropy simply because they use this path.

A keyed binding can prevent verification without the key; it does not make
predictable input unpredictable.

## Generator management

`rng.py` seeds the BSR2 generator from operating-system entropy and manages
request and byte lifecycle limits.

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
