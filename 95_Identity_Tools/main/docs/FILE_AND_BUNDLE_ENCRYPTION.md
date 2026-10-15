# File and Bundle Encryption

Vault and Biometrics can seal arbitrary file bytes. Bulk workflows combine
selected files and directory trees into a ZIP bundle, then seal that bundle
as chunks plus a manifest.

File extensions do not determine whether bytes can be sealed. Successful
processing still depends on readable inputs, valid parameters, available
resources, and the cryptographic integration's limits.

## Single-envelope limit

A BSR2 envelope accepts at most 16 MiB of plaintext.

The integration layer's length prefix and padding reduce the usable
application payload below that raw envelope limit.

Bulk workflows use multiple envelopes to store content larger than one
envelope can hold. The default chunk size is 8 MiB.

## Chunk and manifest model

The bulk representation records chunk order, total content size, and a
whole-content SHA-256 fingerprint.

Restore opens the chunks, reassembles the content, and checks the recorded
size and fingerprint.

This detects missing or inconsistent content relative to the stored manifest.
It is not an independently authenticated historical record or proof that the
original source files were trustworthy.

## Memory and temporary storage

The current implementation is not a bounded-memory streaming archive system.

For path bundles:

1. A plaintext ZIP is created in a temporary directory.
2. The complete ZIP is read into memory.
3. Its bytes are divided into chunks for sealing.

Restore reassembles the complete bundle in memory and writes a temporary ZIP
before extraction.

Consequences:

- Large bundles can exhaust memory.
- Temporary disk space is required.
- The stored JSON representation adds overhead.
- Plaintext exists in temporary storage during bundling and restore.
- Temporary-file cleanup is not secure erasure.
- Chunking does not establish an unlimited-size guarantee.

## Files, folders, and drive roots

Drive roots are traversed as directory trees. This is not sector-level disk
imaging or a complete system-backup mechanism.

Unreadable files can be skipped. A completed operation must be checked for its
reported skipped-file information.

The workflow does not promise a consistent snapshot of files changing during
collection, preservation of every filesystem attribute, or complete recovery
of a running operating system.

## Throughput

Earlier development documentation reports approximately:

- 1,376 bytes per second for sealing a small sample.
- 1,479 bytes per second for restoring a small sample.

Those are historical sample measurements, not current-machine benchmarks or
guaranteed sustained rates.

Measure representative data on the intended deployment before selecting a
bundle size. Whole-drive processing should not be described as practical
merely because chunking can represent multiple envelopes.

## Vault CLI

Run from the selected application root.

```bash
python -m vault.app --vault v.json encrypt-file report.pdf

python -m vault.app --vault v.json decrypt-file \
  RECORD_ID restored-report.pdf

python -m vault.app --vault v.json encrypt-paths \
  report.pdf Photos --label research-bundle

python -m vault.app --vault v.json restore-paths \
  RECORD_ID restored-output
```

Replace `RECORD_ID` with the actual identifier returned by the application.

## Biometrics CLI

An enrolled identity is required.

```bash
python cli.py biometrics attach alice report.pdf --name report.pdf

python cli.py biometrics extract-attachment \
  alice report.pdf restored-report.pdf

python cli.py biometrics attach-paths \
  alice research-bundle report.pdf Photos

python cli.py biometrics restore-paths \
  alice research-bundle restored-output

python cli.py biometrics remove-attachment alice research-bundle
```

## GUI

```bash
python app.py
```

Use the Vault file/bundle controls or the Biometrics attachment controls.

The shared path-selection panel uses Tkinter file and directory pickers.
Native drag-and-drop is not part of this layout.

## Restore safety

Restore writes files into the selected destination. Use a dedicated output
directory and check the result before replacing original data.

The implementation delegates archive extraction to `zipfile`; it is not a
complete hostile-archive sandbox, resource quota system, or transactional
restore engine.

An interrupted operation can leave partial output or stored chunks. Keep
independent backups until a restore has been checked.

## Implementation map

- `vault/store/vault_service.py`: standalone file records.
- `vault/store/bulk_file_service.py`: Vault chunks and path bundles.
- `biometrics/engine/attachments.py`: standalone identity attachments.
- `biometrics/engine/bulk_attachments.py`: attachment chunks and path bundles.
- `gui/widgets/path_panel.py`: shared path selection.

## Tests

Relevant regression tests include:

- `vault/tests/test_file_records.py`
- `vault/tests/test_bulk_file_service.py`
- `biometrics/tests/test_attachments.py`
- `biometrics/tests/test_bulk_attachments.py`

These tests are not a certification of unlimited-size processing, full-drive
backup correctness, crash recovery, or every platform's filesystem behavior.

## Cryptographic caveat

BSR2 is unreviewed research cryptography. Chunking and successful round trips
do not establish independent security assurance.

See [BSR2 integration and threat model](BSR2_INTEGRATION.md).

### Direct API chunk-size limitation

CLI validation is not a substitute for API validation. Direct bulk-service
callers must provide a positive integer chunk size below the envelope payload
limit. Zero and negative sizes are not safely rejected by a dedicated
validator; nonempty input can raise ValueError or yield no chunks. See KI-006.
