# BrisartIdentityTools

Local identity tooling within Brisart Research Archive, organized into three
application areas:

- **Vault:** local JSON records with sealed payloads, plus file and bundle storage.
- **Biometrics:** research-grade voice, fingerprint, and video matching with
  sealed templates and file attachments.
- **Packages:** symmetric, recipient-bound payload encryption with custody
  records and external audit files.

The supplied application code uses Python's standard library and does not
require a cloud service.

BSR2 is custom, unreviewed research cryptography. These tools must not be
treated as independently audited security products or as the sole protection
for high-value or irreplaceable secrets.

## Application roots

The archive contains separate application trees:

- `main/`: the current development line.
- `LTS-2028/`: the long-term-support line.

Commands in this documentation assume the working directory is the selected
application root: the directory containing `app.py`, `cli.py`, `version.py`,
and the application packages.

For example, from the Identity Tools archive directory:

```bash
cd main
```

Or, for the LTS application:

```bash
cd LTS-2028
```

Do not combine modules from the two application trees.

## Requirements

The documented Python minimum is 3.10.

The desktop interface additionally requires a working Tkinter installation
and a graphical display. No third-party Python GUI framework is used.

The supplied hardware layer in `main/` contains optional integration contracts
and driver logic. Real device access requires caller-supplied bindings or
transports; it is not automatically provided by installing the application.

## Launch the desktop interface

From the selected application root:

```bash
python app.py
```

The GUI entry point is the root-level `app.py`.

The supplied CLI dispatcher still tries to import `gui.app` for its `gui`
command, but no `gui/app.py` exists in this tree. Consequently,
`python cli.py gui` and `python -m gui.app` are not supported launch commands
for this snapshot. Use `python app.py`.

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
vendor/
```

The `main/` application additionally contains `hardware/` and the integrity
checkpoint tooling.

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
- Chunking bypasses the single-envelope size cap, but does not provide
  unlimited memory, disk space, throughput, or full-drive backup guarantees.
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
- [File and bundle encryption](FULL_FILE_ENCRYPTION.md)
- KNOWN_ISSUES.md
- [Security policy](SECURITY.md)
- [Release history](CHANGELOG.md)

Release-history entries describe their named releases. Old command examples,
measurements, layouts, and test totals are not current usage instructions.
