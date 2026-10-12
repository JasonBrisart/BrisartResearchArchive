# Vault

Local JSON record storage with BSR2-sealed payloads.

Vault separates readable record metadata from protected values. It also
supports raw file records and chunked bundles.

## Storage model

The vault JSON contains:

- A keyring with wrapped master-key material.
- Record identifiers and record-shell metadata.
- Sealed record payloads.
- Persisted unlock-attempt state.

A random 32-byte master key protects payloads. The keyring wraps that key under
both a passphrase-derived key and a recovery-code-derived key.

Payload context strings bind sealed data to its record identifier, kind, and
label. Integration-layer padding groups plaintext lengths into 256-byte
buckets; it does not hide all size information.

## Information visible while locked

Record-shell metadata remains readable, including identifiers, kinds, labels,
and timestamps.

File records can additionally expose original filenames, sizes, and plaintext
SHA-256 fingerprints. Such fingerprints can reveal that a stored file matches
a known candidate even when its contents are sealed.

Do not place secrets in labels or assume all metadata is encrypted.

Listing records does not require unlocking. Reading protected payloads does.

## Unlocking and recovery

Unlocking derives a wrapping key and opens the master-key wrapper. Subsequent
operations within the same unlocked service session reuse the master key.

KDF runtime depends on iteration count, hardware, interpreter, and system
load. Earlier documentation contains development-machine measurements, not a
fixed runtime guarantee.

Separate CLI invocations do not share an unlocked in-memory session.

Creating a keyring displays a recovery code once. The recovery code provides
another route to the same master key; it is not a lower-privilege credential.

If neither the passphrase nor recovery code is available, this implementation
provides no additional recovery route.

## Attempt limiting

Passphrase and recovery-code unlocks share persisted attempt state.

The default limiter uses:

- Exponential retry delays starting at one second.
- A maximum retry delay of 300 seconds.
- A 900-second lockout after the fifth failure.

Attempt state is stored in the vault JSON. It is not distributed coordination,
an authenticated counter, or protection against offline guessing after a file
has been copied. A party able to edit the state can reset it.

## File permissions

Vault writes request owner-only `0600` permissions on POSIX platforms through
the shared atomic-write helper.

This is best effort:

- Permissions are tightened after replacement.
- Permission-setting failures are not treated as failed data writes.
- Windows POSIX-mode checks do not enforce Windows ACLs.
- Existing permissive files can produce an advisory warning.

Filesystem access control remains a deployment responsibility.

## CLI usage

Run from the selected application root.

`--vault` is a global option and belongs before the subcommand.

```bash
# Initialize a vault.
python -m vault.app --vault data/vaults/main_vault.json init

# Create a record.
python -m vault.app --vault data/vaults/main_vault.json upsert \
  "Researcher One" --kind identity --payload '{"value": "example"}'

# List readable metadata without unlocking.
python -m vault.app --vault data/vaults/main_vault.json list

# Read a protected payload.
python -m vault.app --vault data/vaults/main_vault.json get RECORD_ID

# Delete a record.
python -m vault.app --vault data/vaults/main_vault.json delete RECORD_ID

# Create or update records from a JSON array.
python -m vault.app --vault data/vaults/main_vault.json batch-upsert items.json
```

Replace `RECORD_ID` with an actual identifier returned by the application.

Supplying `--record-id` to `upsert` targets an existing identifier. Omitting it
creates a new identifier.

The dispatcher provides the same application interface:

```bash
python cli.py vault --vault data/vaults/main_vault.json list
```

## Files and bundles

```bash
python -m vault.app --vault data/vaults/main_vault.json encrypt-file report.pdf

python -m vault.app --vault data/vaults/main_vault.json decrypt-file \
  RECORD_ID restored-report.pdf

python -m vault.app --vault data/vaults/main_vault.json encrypt-paths \
  report.pdf Photos --label research-bundle

python -m vault.app --vault data/vaults/main_vault.json restore-paths \
  RECORD_ID restored-output
```

Chunking bypasses the single-envelope payload limit. It does not provide
unlimited-size processing: the implementation still requires memory, temporary
disk space, storage space, and substantial processing time.

A selected drive root is treated as a directory tree of readable files, not as
a sector-level disk image or complete system backup.

See [file and bundle encryption](../docs/FILE_AND_BUNDLE_ENCRYPTION.md).

## Automation

The CLI uses interactive secret prompts for operations that need unlocking.
It does not provide a dedicated environment-variable credential interface.

The `list` command does not require a passphrase, so piping a passphrase into
`list` is not an unlock example.

For controlled automation, use the application API with an explicitly managed
secret source rather than embedding credentials in shell commands.

## Layout

- `app.py`: CLI.
- `config/`: default storage settings.
- `core/`: identifiers and record timestamps.
- `records/`: record shape and validation.
- `reports/`: local audit files.
- `store/`: vault persistence, service operations, and bulk bundles.
- `tests/`: regression tests.

## Security status

BSR2 is custom, unreviewed research cryptography. A stable release label or
passing regression suite does not establish independent cryptographic
assurance.

Local audit files are not an independently protected evidence store.
Concurrent writers and filesystem-level attackers require controls beyond
these application helpers.

See [BSR2 integration and threat model](../docs/BSR2_INTEGRATION.md).
