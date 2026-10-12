# Common Utilities

Shared standard-library utilities for application persistence, fingerprints,
and timestamps.

These modules do not implement identity authorization or cryptographic
confidentiality.

## Atomic writes

`atomic_io.py` provides:

- `atomic_write_text()`
- `atomic_write_json()`
- `warn_if_permissive()`
- `SENSITIVE_FILE_MODE`

Writes use a temporary file in the destination directory, flush and fsync that
file, then replace the destination with `os.replace()`.

Directory fsync is attempted where supported.

This reduces exposure to partially written destination files. It does not
guarantee durability under every power failure, filesystem, storage device,
or operating-system condition.

It also does not provide:

- Multi-file transactions.
- Concurrent-writer locking.
- Lost-update prevention.
- Secure temporary-file erasure.

Not every application persistence path uses these helpers. In particular,
the package CLI writes package JSON directly.

## File modes

An optional `file_mode` requests a POSIX permission change after replacement.

`SENSITIVE_FILE_MODE` is `0o600`.

Permission changes are best effort; failures are swallowed. The temporary file
initially uses the process's normal creation permissions, and tightening occurs
after replacement.

Windows POSIX-mode checks do not enforce Windows ACLs.

`warn_if_permissive()` prints an advisory for permissive POSIX modes. It is not
an access-control enforcement mechanism.

## SHA-256 fingerprints

`hashing.py` provides:

- `sha256_bytes()`
- `sha256_file()`

File hashing reads incrementally rather than loading the complete file.

An unkeyed fingerprint can detect a mismatch against a trusted expected value.
It does not authenticate an author or protect a secret.

A plaintext fingerprint can also reveal that data matches a known candidate.
Do not assume fingerprints are always non-sensitive.

## UTC timestamps

`timestamps.py` provides:

- `utc_now()`: ISO-8601 UTC timestamp to second precision.
- `utc_now_iso`: alias of `utc_now`.
- `filename_timestamp()`: filename-safe UTC timestamp to second precision.
- `microsecond_timestamp()`: filename-safe UTC timestamp with microseconds.

Timestamps come from the local system clock. They are not trusted external
time evidence or a guarantee of uniqueness.

## Design boundary

Common utilities remain application-neutral.

Tool-specific validation, authorization, and storage rules belong in the
corresponding application modules rather than being hidden inside shared
helpers.

## Tests

`common/tests/test_common_utils.py` exercises shared utility behavior.

Tests do not establish every filesystem's crash durability or permission
semantics.
