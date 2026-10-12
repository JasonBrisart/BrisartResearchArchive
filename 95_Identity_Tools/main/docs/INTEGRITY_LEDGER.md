# Integrity Ledger

An external JSON ledger of periodic file checkpoints.

The ledger records observed file states. It is not continuous monitoring,
authenticated authorship evidence, or an immutable audit service.

## What a checkpoint records

A checkpoint records a target file's SHA-256 fingerprint, size, timestamp,
and associated metadata.

Entries are linked by unkeyed hashes.

The CLI is `tools/integrity_checkpoint.py`; the implementation is
`common/integrity_ledger.py`.

## What it can show

If a checkpoint captures a changed file, its fingerprint can differ from
earlier or later checkpoints.

That difference remains visible in retained history after the target file is
restored, provided the ledger history itself has not been altered.

A difference establishes that observed bytes changed. It does not establish
whether the change was authorized, malicious, accidental, or caused by normal
application activity.

## Observation gaps

A file changed and restored to exactly the same bytes entirely between
checkpoints produces identical before-and-after observations.

Increasing checkpoint frequency reduces the observation gap. It does not
guarantee that every change is captured.

The tool does not schedule itself or run a monitoring daemon.

## Hash-chain limits

`verify` checks the ledger's internal hash consistency.

It does not prove:

- Who wrote an entry.
- That every event was recorded.
- That timestamps came from a trusted clock.
- That the ledger has not been completely rewritten.
- That a valid suffix has not been removed.

A party able to rewrite the ledger can recompute its unkeyed hashes. A valid
prefix can remain internally consistent after later entries are removed.

Use independently protected ledger copies or trusted checkpoints if historical
integrity matters.

## CLI usage

Run from the `main/` application root.

`--ledger` is a global option and belongs before the subcommand.

```bash
# Record an observed file state.
python tools/integrity_checkpoint.py \
  --ledger data/integrity/ledger.json \
  checkpoint data/vaults/main_vault.json --label "manual checkpoint"

# Compare current bytes with the latest retained checkpoint.
python tools/integrity_checkpoint.py \
  --ledger data/integrity/ledger.json \
  status data/vaults/main_vault.json

# Show retained checkpoints for the target.
python tools/integrity_checkpoint.py \
  --ledger data/integrity/ledger.json \
  history data/vaults/main_vault.json

# Check internal ledger consistency.
python tools/integrity_checkpoint.py \
  --ledger data/integrity/ledger.json verify

# List tracked paths.
python tools/integrity_checkpoint.py \
  --ledger data/integrity/ledger.json list-tracked
```

The default ledger path is `data/integrity/ledger.json`.

## Deployment considerations

- Store the ledger outside the writable trust boundary of untrusted parties.
- Keep independently protected copies or checkpoints.
- Coordinate checkpointing with application writes to avoid observing an
  unintended intermediate state.
- Treat actor labels as caller-supplied metadata.
- Treat paths, sizes, and fingerprints as potentially sensitive metadata.
- Do not interpret a matching fingerprint as proof that no activity occurred
  between observations.

## Tests

`common/tests/test_integrity_ledger.py` exercises checkpoint and comparison
behavior, including changes captured during a checkpoint and changes reverted
entirely between checkpoints.

Those tests do not establish immutable storage, authenticated history, or
continuous observation.
