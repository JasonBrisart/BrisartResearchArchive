# AutoExeBuilder

AutoExeBuilder is a lightweight Python utility that automates the process of turning Python projects into distributable Windows executables.

Instead of manually configuring build commands, output folders, executable names, and packaging options, AutoExeBuilder scans a project, identifies likely Python entry points, generates build artifacts, and runs the executable build workflow through a simple GUI or CLI.

Designed for developers, researchers, students, and independent software creators who want a faster and more repeatable way to package Python applications.

## Features

- GUI and CLI support
- Python project scanning
- Likely entry point detection
- One-file or one-folder build modes
- Windowed or console executable modes
- Optional icon support
- Build command logging
- Build notes generation
- JSON build manifest generation
- Local-first workflow
- No third-party dependencies for the AutoExeBuilder interface itself

## Requirements

AutoExeBuilder itself uses only Python's standard library.

To generate executable files, PyInstaller must be available in the active Python environment:

```bash
py -m pip install pyinstaller
```

If PyInstaller is not installed, AutoExeBuilder will detect this and provide the required installation command automatically.

## Typical Workflow

1. Select a Python project folder
2. Scan the project
3. Review detected entry points
4. Configure executable options
5. Build the executable
6. Review generated build notes and manifest files

Generated outputs include:

- EXE_BUILD_COMMAND.txt
- EXE_BUILD_NOTES.md
- EXE_BUILD_MANIFEST.json
- Build artifacts in the output directory

## Why Use AutoExeBuilder?

Building a Python executable is often more than just running a single command.

Developers frequently need to:

- Identify the correct application entry point
- Configure build options
- Manage output folders
- Configure console or windowed modes
- Save the build command for future use
- Keep a record of build settings
- Track build results across project versions

AutoExeBuilder helps automate these repetitive tasks while providing a consistent and repeatable packaging workflow.

## Usage

### GUI

Launch the graphical interface:

```bash
py auto_exe_builder.py
```

### CLI

Build a project using the automatically detected entry point:

```bash
py auto_exe_builder.py "C:\Path\To\Project"
```

### CLI With Explicit Entry Point

```bash
py auto_exe_builder.py "C:\Path\To\Project" --entrypoint main.py
```

### Custom Executable Name

```bash
py auto_exe_builder.py "C:\Path\To\Project" --name MyApplication
```

### Console Application Build

```bash
py auto_exe_builder.py "C:\Path\To\Project" --console
```

### One-Folder Build

```bash
py auto_exe_builder.py "C:\Path\To\Project" --onedir
```

### Scan Project Only

```bash
py auto_exe_builder.py "C:\Path\To\Project" --scan-only
```

## Generated Files

AutoExeBuilder creates documentation and metadata for each build.

Typical outputs include:

```text
auto_exe_output/
│
├── EXE_BUILD_COMMAND.txt
├── EXE_BUILD_NOTES.md
├── EXE_BUILD_MANIFEST.json
│
├── build/
├── dist/
└── spec/
```

### EXE_BUILD_COMMAND.txt

Stores the exact executable build command that was used.

### EXE_BUILD_NOTES.md

Stores human-readable build information including:

- Build configuration
- Selected entry point
- Build status
- Output locations
- Error details if applicable

### EXE_BUILD_MANIFEST.json

Stores machine-readable build metadata including:

- Project information
- Build configuration
- Scan results
- Build results
- Generated output paths

## Project Goals

AutoExeBuilder follows the same design philosophy as other BrisartDevTools utilities:

- Minimal dependencies
- Reproducible workflows
- Clear implementation
- Practical utility
- Local-first operation
- Straightforward documentation

The goal is to simplify software packaging without requiring developers to repeatedly configure the same build process for every project.

## Notes

- AutoExeBuilder itself uses only the Python standard library.
- PyInstaller is required to generate executable files.
- Executable creation occurs entirely on the local machine.
- No internet access is required during normal operation.
- Newly generated unsigned executables may trigger Windows SmartScreen warnings.

## Related Tools

Part of the BrisartDevTools ecosystem:

- Project Context Helper
- ReadmeBuilder
- ReleaseNoteBuilder
- AutoExeBuilder

Together these utilities support project packaging, documentation, release management, and software distribution workflows.

---

Created by Jason Brisart

Part of BrisartDevTools