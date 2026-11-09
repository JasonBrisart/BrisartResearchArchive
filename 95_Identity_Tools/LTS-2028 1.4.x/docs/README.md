# BrisartIdentityTools

Local identity tooling within Brisart Research Archive, organized into three
application areas:

- **Vault:** local JSON records with sealed payloads, plus file and bundle
  storage.
- **Biometrics:** research-grade voice, fingerprint, and video matching with
  sealed templates and file attachments.
- **Packages:** symmetric, recipient-bound payload encryption with custody
  records and external audit files.
The application code uses Python's standard library and does not require a
cloud service. All encryption comes from BSR2
(`97_Encryption/Official`). The only requirement is that the
`95_Identity_Tools` and `97_Encryption` folders sit together in the same
folder; where that folder is (a desktop folder, a drive, OneDrive) does not
matter. Kept apart, the tools start, any operation that needs encryption
reports `Encryption not found`, and nothing can be sealed or opened.

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

## Requirements

The documented Python minimum is 3.10.

The desktop interface additionally requires a working Tkinter installation
and a graphical display. No third-party Python GUI framework is used.

The supplied hardware layer in `Official/` contains optional integration contracts
and driver logic. Real device access requires caller-supplied bindings or
transports; it is not automatically provided by installing the application.

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
python cli.py version

python cli.py vault --help
python cli.py biometrics --help
python cli.py package --help
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
app.py
cli.py
version.py
biometrics/
common/
crypto/
docs/
gui/
packages/
tests/
vault/
```

LTS-2028 has the same architecture as `Official/`, without its features: it
receives security changes only, with no new features until it reaches end of
life (see [SECURITY.md](SECURITY.md)). Official's extras (`hardware/`, the
Integrity Ledger, the demo's save-to-disk option, the encryption status line
and start-up warning, the version line, and `python cli.py encryption`) are not
here. Encryption is not part of this tree; `crypto/encryption.py`
links every BSR2 library module from
`../../97_Encryption/Official`, exactly as in `Official/`.

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
- Data written by LTS-2028 1.3.x uses the previous encryption. It still opens,
  and each tool offers to migrate it (`vault migrate`, `biometrics migrate`,
  `package migrate`, or a prompt in the GUI); migrated data cannot be opened by
  any LTS-2028 1.3.x release, or by Official 1.9.2 and earlier. See [BSR2
  integration](BSR2_INTEGRATION.md#encryption-migration).
- Sealing has no payload size cap and bulk workflows chunk large content,
  but neither provides unlimited memory, disk space, throughput, or full-drive
  backup guarantees.
- Local reports and audit files are not independently protected,
  cryptographically authenticated evidence merely because the application
  writes a new file for each event.

## Documentation

- ../vault/README.md
- ../biometrics/README.md
- ../packages/README.md
- ../gui/README.md
- ../common/README.md
- ../crypto/README.md
- [BSR2 integration and threat model](BSR2_INTEGRATION.md)
- [File and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md)
- KNOWN_ISSUES.md
- [Security policy](SECURITY.md)
- [Release history](CHANGELOG.md)

Release-history entries describe their named releases. Old command examples,
measurements, layouts, and test totals are not current usage instructions.
