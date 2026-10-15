# Packages

Local, symmetric recipient-bound payload encryption.

A package seals its payload under a content key and stores a separately wrapped
copy of that content key for each recipient.

## Key model

1. A random 32-byte content key seals the payload.
2. Each recipient's master key wraps that content key into a recipient key slot.
3. Opening verifies the recipient material, unwraps the content key, and opens
   the payload.

Creating a package requires the intended recipients' master keys to be
available to the creator. Adding a recipient also requires that recipient's
master key.

This is not public-key encryption. It does not let a creator encrypt to a
recipient while remaining unable to open the content.

Removing a recipient removes that recipient's slot from the current package.
It does not revoke previously copied packages, previously recovered content
keys, or plaintext already obtained by that recipient.

## CLI key prompts

The CLI prompts for text and derives a 32-byte demonstration key using a
single unsalted SHA-256 operation.

The Packages GUI uses the same demonstration approach.

This is not a slow password KDF. Guessable input text produces guessable key
material, and repeated text produces the same key.

Application integrations should supply appropriately generated and managed
master keys rather than treating the demonstration prompt as production
password authentication.

## CLI usage

Run from the selected application root.

```bash
python -m packages.main --help

python -m packages.main create pkg.json --package-id demo-1 \
  --identity-id alice --label "Alice" --payload '{"message": "hello"}'

python -m packages.main add-recipient pkg.json \
  --identity-id bob --label "Bob" --opener-identity-id alice

python -m packages.main remove-recipient pkg.json \
  --identity-id bob --opener-identity-id alice

python -m packages.main open pkg.json --identity-id alice

python -m packages.main list-recipients pkg.json
python -m packages.main verify-custody pkg.json

python -m packages.main demo
```

The dispatcher is also available:

```bash
python cli.py package --help
```

Removing the last recipient is refused.

## Custody chain

`custody.py` stores lifecycle entries inside package state. Entries include
action information, timestamps, caller-supplied actor labels, and hashes linking
them to previous entries.

Verification checks the chain's internal consistency.

This is not a digital signature or proof of authorship:

- Actor labels are caller-supplied strings.
- A party able to rewrite the entire chain can recompute its unkeyed hashes.
- Removing a valid suffix can leave an internally consistent shorter chain.
- A valid chain does not prove that every historical event was recorded.

Stronger historical evidence requires an independently protected checkpoint,
signature, or external record.

## External audit files

`audit.py` writes event records outside the package file.

The application uses append-style event writing, but the filesystem does not
enforce an append-only store. Files can be edited or removed by a party with
sufficient access.

Audit records are not authenticated proof of actor identity. Caller-supplied
labels and package identifiers must not be treated as trusted identities or
safe filesystem paths without additional validation.

## Persistence

The package CLI and the GUI Packages tab save state through the shared
atomic-write helper, so an interrupted save leaves the previous package file
intact rather than a truncated one.

The helper does not lock the file. Two processes saving the same package at
once can still lose one update, so avoid concurrent writers and keep backups
of package state.

## Module map

- `main.py`: CLI and demonstration text-to-key prompts.
- `package.py`: package orchestration and validation.
- `ciphers.py`: content-key generation and key-slot sealing.
- `identity.py`: recipient descriptors.
- `verification.py`: recipient factor verification.
- `custody.py`: internal custody-chain construction and checking.
- `audit.py`: external event files.
- `tests/`: regression tests.

## Security boundaries

Structural validation is performed before some cryptographic operations, but
it is not a guarantee that arbitrary malformed input is harmless.

Digest comparison helpers do not make the entire Python implementation
constant-time.

BSR2 remains unreviewed research cryptography. Recipient binding, custody
records, and passing tests do not remove that limitation.

See [BSR2 integration and threat model](../docs/BSR2_INTEGRATION.md).
