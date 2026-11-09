# BrisartIdentityTools

> This copy documents **Official**, the development line. LTS-2028 1.4.x and
> 1.3.x have their own copies in their own folders.

Local identity tooling within Brisart Research Archive, organized into four
application areas:

- **Vault:** local JSON records with sealed payloads, plus file and bundle
  storage.
- **Biometrics:** research-grade voice, fingerprint, and video matching with
  sealed templates and file attachments.
- **Packages:** symmetric, recipient-bound payload encryption with custody
  records and external audit files.
- **Encryption toolkit:** BSR2's own key files, file
  encryption, sealed messages, and Brisart Secure Archives with recovery
  records, run as `python cli.py encryption`.

The application code uses Python's standard library and does not require a
cloud service. All encryption comes from BSR2
(`97_Encryption/Official`). The only requirement is that the
`95_Identity_Tools` and `97_Encryption` folders sit together in the same
folder; where that folder is (a desktop folder, a drive, OneDrive) does not
matter. Kept apart, the tools start and report `Encryption not found`, nothing
can be sealed or opened, and the desktop interface shows a warning pop-up at
start-up.

BSR2 is custom, unreviewed research cryptography. These tools must not be
treated as independently audited security products or as the sole protection
for high-value or irreplaceable secrets.

## Application roots

The archive contains three separate application trees, one per supported line
(see [SECURITY.md](SECURITY.md)):

- `Official/`: the current development line.
- `LTS-2028 1.4.x/`: the LTS-2028 line with the new encryption, BSR2 Alpha 4,
  linked from `97_Encryption/Official`.
- `LTS-2028 1.3.x/`: the original LTS-2028 line, with BSR2 Alpha 3 vendored
  in its own `vendor/`.

Commands in this documentation assume the working directory is the selected
application root: the directory containing `app.py`, `cli.py`, `version.py`,
and the application packages.

For example, from the Identity Tools archive directory:

```bash
cd Official
```

Or, for an LTS-2028 application, `cd "LTS-2028 1.4.x"` or
`cd "LTS-2028 1.3.x"`. The folder names contain a space, so quote them.

Do not combine modules from different application trees.

## Quick start

A first vault, from the Identity Tools archive directory:

```bash
cd Official
python cli.py version      # tools version and the BSR2 release it links

python cli.py vault init
python cli.py vault upsert "Lab door code" --kind credential --payload '{"value": "4512"}'
python cli.py vault list
python cli.py vault get RECORD_ID
```

- `init` asks for a new passphrase twice and prints a recovery code once. Store
  the recovery code somewhere separate; it cannot be shown again. `init`
  derives two keys with BSR2-MHF-1, so it takes a few seconds.
- `upsert` and `get` ask for the passphrase. `list` does not: record labels and
  kinds are readable while the vault is locked, and only payloads are sealed.
- Replace `RECORD_ID` with the id `upsert` or `list` printed.
- Without `--vault`, the vault is `data/vault/vault.json` and audit events go
  to `data/vault/audit/`, both relative to the application root.

Biometrics and Packages work the same way. Start from
`python cli.py biometrics --help` and `python cli.py package --help`, or see
their READMEs under Documentation. `python cli.py package demo` runs a
complete package cycle without any setup.

## Requirements

The documented Python minimum is 3.10.

The desktop interface additionally requires a working Tkinter installation and
a graphical display. No third-party Python GUI framework is used.

The supplied hardware layer in `Official/` contains optional integration
contracts and driver logic. Real device access requires caller-supplied
bindings or transports; it is not automatically provided by installing the
application.

## Launch the desktop interface

From the selected application root:

```bash
python app.py
```

Or through the dispatcher:

```bash
python cli.py gui
```

Both run the same shell: the root-level `app.py`. There is no `gui/app.py`,
so `python -m gui.app` is not a launch command.

## Command-line interfaces

```bash
python cli.py --help
python cli.py version      # also prints the encryption link or "Encryption not found"

python cli.py vault --help
python cli.py biometrics --help
python cli.py package --help
python cli.py encryption --help   # BSR2's toolkit, unchanged
```

The application-specific module entry points are also available:

```bash
python -m vault.app --help
python -m biometrics.app --help
python -m packages.main --help
```

Commands that create or open protected data can prompt for secret material.
Help commands do not demonstrate that an enrollment, encryption, or restore
operation has completed successfully.

## Layout

```text
app.py        desktop shell (Tkinter)
cli.py        command dispatcher: vault, biometrics, package, encryption, gui
version.py    release version of this tree
biometrics/   enrollment, verification, templates, attachments
common/       atomic writes, file modes, SHA-256 fingerprints, timestamps,
              integrity ledger
crypto/       the link to BSR2 and everything built on it: keyrings,
              sealing, contexts, factors, attempt limiting
docs/         this documentation
gui/          desktop tabs and shared widgets
hardware/     optional device contracts and drivers (Official only)
packages/     recipient-bound packages, custody chain, audit files
tests/        dispatcher tests and the test runner (tests/run_tests.py)
tools/        envinfo.py (environment report for bug reports) and
              integrity_checkpoint.py (Official only)
vault/        record store, file records, bundles
```

`hardware/`, the integrity checkpoint tooling, and the other Official-only
features (listed in [SECURITY.md](SECURITY.md)) exist only in `Official/`.
Encryption is not part of this tree: `crypto/encryption.py` links every BSR2
library module from `../../97_Encryption/Official`.

The GUI is split into:

```text
gui/
├── core/
│   ├── constants.py
│   └── busy.py
├── widgets/
│   ├── dialogs.py
│   └── path_panel.py
└── tabs/
    ├── tab_vault.py
    ├── tab_biometrics.py
    └── tab_packages.py
```

The GUI calls application services rather than providing a separate
cryptographic implementation.

## Important boundaries

- Vault record labels and other record-shell metadata remain readable while
  locked.
- Biometric identity metadata remains readable; template payloads are sealed.
- Biometric similarity scores are research measurements, not probabilities
  that a person has been correctly identified.
- Video motion checks are not general anti-spoofing.
- Package CLI and GUI text-to-key prompts are demonstration interfaces, not
  slow password-KDF authentication.
- Data written by Official 1.9.2 and earlier, or by any LTS-2028 1.3.x release,
  uses the previous encryption. It still opens, and each tool offers to migrate
  it (`vault migrate`, `biometrics migrate`, `package migrate`, or a prompt in
  the GUI); migrated data cannot be opened by Official 1.9.2 and earlier or any
  LTS-2028 1.3.x release (LTS-2028 1.4.x reads it). See [BSR2
  integration](BSR2_INTEGRATION.md#encryption-migration).
- Sealing has no payload size cap and bulk workflows chunk large content,
  but neither provides unlimited memory, disk space, throughput, or full-drive
  backup guarantees.
- Local reports and audit files are not independently protected,
  cryptographically authenticated evidence merely because the application
  writes a new file for each event.

## Documentation

Start here:

- [Security policy](SECURITY.md): supported lines, end-of-life dates, how to
  report a problem.
- [Known issues](KNOWN_ISSUES.md): open problems, with severity and status.
- [BSR2 integration and threat model](BSR2_INTEGRATION.md): what is protected,
  what is not, and how the encryption migration works.

Each tool:

- [Vault](../vault/README.md)
- [Biometrics](../biometrics/README.md)
- [Packages](../packages/README.md)
- [GUI](../gui/README.md)
- [Hardware](../hardware/README.md): optional device contracts and drivers.

Shared code and deeper topics:

- [Crypto integration layer](../crypto/README.md)
- [Common utilities](../common/README.md)
- [File and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md): large files,
  folders, and drive roots.
- [Integrity ledger](INTEGRITY_LEDGER.md): Official-only checkpoints of
  file hashes.

History:

- [Release history](CHANGELOG.md)

Release-history entries describe their named releases. Old command examples,
measurements, layouts, and test totals are not current usage instructions.
