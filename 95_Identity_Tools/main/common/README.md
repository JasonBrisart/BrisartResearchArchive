# Common Utilities

Shared standard-library utilities for persistence, fingerprints, timestamps,
and integrity checkpoints.

These modules do not implement identity authorization or cryptographic
confidentiality.

## Atomic writes

`atomic_io.py` provides text and JSON writes through a temporary file followed
by `os.replace()`.

The temporary file is flushed and fsynced. Directory fsync is attempted where
supported.

This reduces exposure to partially written destination files. It does not
guarantee durability under every power failure, filesystem, storage device,
or operating-system condition.

It does not provide multi-file transactions, concurrent-writer locking,
lost-update prevention, or secure temporary-file erasure.

Not every persistence path uses these helpers. The package CLI writes package
JSON directly.

## File modes

`SENSITIVE_FILE_MODE` is `0o600`.

An optional `file_mode` requests a POSIX permission change after replacement.
Permission-setting failures are swallowed.

The temporary file initially uses normal process creation permissions.
Windows POSIX-mode checks do not enforce Windows ACLs.

`warn_if_permissive()` is advisory, not access-control enforcement.

## SHA-256 fingerprints

`hashing.py` provides `sha256_bytes()` and incrementally read `sha256_file()`.

An unkeyed fingerprint detects differences relative to a trusted expected
value. It does not authenticate an author or protect a secret.

A plaintext fingerprint can reveal that data matches a known candidate.

## Integrity ledger

`integrity_ledger.py` records file checkpoints in an external JSON ledger.

Each checkpoint records a file fingerprint, size, timestamp, and associated
metadata. Entries are linked by unkeyed hashes.

The ledger can show a changed file state if a checkpoint captures that state.
It cannot observe a change and exact reversion entirely between checkpoints.

Chain verification checks internal consistency. It does not prove authorship,
completeness, or resistance to a party able to rewrite the ledger and recompute
its hashes. A valid-prefix truncation can remain internally consistent.

Store trusted checkpoints or ledger copies outside the same writable trust
boundary as the monitored files.

The module does not schedule itself. The standalone interface is
`tools/integrity_checkpoint.py`.

See ../docs/INTEGRITY_LEDGER.md.

## UTC timestamps

`timestamps.py` provides:

- `utc_now()`: ISO-8601 UTC timestamp to second precision.
- `utc_now_iso`: alias of `utc_now`.
- `filename_timestamp()`: filename-safe UTC timestamp to second precision.
- `microsecond_timestamp()`: filename-safe UTC timestamp with microseconds.

These use the local system clock. They are not trusted external time evidence
or a uniqueness guarantee.

## Design boundary

Shared utilities remain application-neutral.

Tool-specific validation, authorization, and storage rules belong in the
corresponding application modules.

## Tests

- `common/tests/test_common_utils.py`
- `common/tests/test_integrity_ledger.py`

Regression tests do not establish every filesystem's durability or turn an
unkeyed ledger into authenticated historical evidence.
