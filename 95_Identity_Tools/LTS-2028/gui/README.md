# GUI

Tkinter desktop interface for Vault, Biometrics, and Packages.

The GUI uses the application services for storage, matching, and cryptographic
operations. It is not a separate implementation of those services.

## Launch

From the selected application root:

```bash
python app.py
```

The executable shell is the root-level `app.py`, not `gui/app.py`.

The supplied dispatcher imports `gui.app` for its `gui` command, but that
module is absent. Do not use `python cli.py gui` or `python -m gui.app` for
this snapshot.

A working Tkinter installation and graphical display are required.

## Layout

```text
app.py
gui/
├── core/
│   ├── constants.py
│   └── busy.py
├── widgets/
│   ├── dialogs.py
│   └── path_panel.py
├── tabs/
│   ├── tab_vault.py
│   ├── tab_biometrics.py
│   └── tab_packages.py
└── tests/
```

### Application shell

`app.py` creates the main window, assembles the tabs, creates the menus, and
starts the Tkinter event loop.

### Shared core

`gui/core/constants.py` provides shared constants, file-type filters, and the
application-root import bootstrap.

`gui/core/busy.py` provides the busy dialog and background-operation runner.

### Shared widgets

`gui/widgets/dialogs.py` contains reusable dialogs.

`gui/widgets/path_panel.py` contains the file, folder, and drive-root selection
panel.

### Application tabs

- `tab_vault.py`: record and file/bundle workflows.
- `tab_biometrics.py`: enrollment, verification, and attachments.
- `tab_packages.py`: recipient-bound package workflows.

## Background operations

The shared runner executes supplied work in a background thread and delivers
completion handling through the GUI's polling mechanism.

Worker functions must not access Tkinter widgets. Widget values should be
captured on the main thread before starting work, and widget updates should
occur in completion callbacks.

The existence of a background runner does not establish that every GUI action
is non-blocking or that every call site is thread-safe.

## File selection

The path panel uses Tkinter file and directory pickers. It supports selecting
files, folders, and drive roots for the relevant bundle workflows.

Native drag-and-drop is not supplied by this layout.

Selecting a drive root means selecting its readable directory contents. It
does not create a sector-level image or preserve every filesystem attribute.

## Security and usability boundaries

- The GUI inherits BSR2's research-cryptography limitations.
- Biometric results are research matching results, not validated identity
  probabilities.
- Video motion checks are not general anti-spoofing.
- Package text-to-key prompts use demonstration SHA-256 key derivation, not a
  slow password KDF.
- Bulk operations remain constrained by memory, temporary disk space, storage
  space, and throughput.
- Closing or interrupting a workflow is not a guarantee of transactional
  rollback or secure removal of temporary data.

## Testing

`gui/tests/` contains regression tests for shared GUI helpers and tab behavior.

The presence of these tests does not establish full visual, platform,
accessibility, hardware, or end-to-end GUI validation.

See ../docs/KNOWN_ISSUES.md and
[file and bundle encryption](../docs/FULL_FILE_ENCRYPTION.md).
