# BrisartOS

**A pure-Python, dependency-free, fully custom operating system research project.**

BrisartOS is an experimental operating system research project focused on building a fully custom computing environment using Python as the primary development language.

The project emphasizes local-first operation, offline capability, auditability, modular architecture, long-term maintainability, and complete ownership of the software stack.

BrisartOS is not a Linux distribution, Windows derivative, macOS clone, desktop environment, or wrapper around an existing operating system.

The long-term goal is to develop a fully custom operating environment designed for research, preservation, archive management, identity infrastructure, air-gapped deployments, and long-term digital stewardship.

---

# Philosophy

BrisartOS follows several core principles:

- Pure Python development
- No external dependencies
- Local-first architecture
- Offline-first operation
- Air-gapped environment compatibility
- Long-term maintainability
- Source transparency
- Full stack ownership
- Modular design
- Future-oriented architecture

The project prioritizes understanding and control over complexity and abstraction.

---

# Current Status

BrisartOS does not hardcode a version number in this README, so this file never
goes stale as releases ship. The canonical version is defined once in
`version.py` and imported by the runtime and build tooling. All other
references should follow that source.

To check the current version, either open `version.py` directly or run:

```bash
python -c "from brisartos.version import version_text; print(version_text())"
```

Or from the running shell:

```text
BrisartOS> version
```

BrisartOS currently includes:

- Boot image generation research
- Binary image tooling
- Experimental boot infrastructure
- Runtime architecture
- Modular shell environment
- Service framework
- System API framework
- Built-in application structure
- Pure-Python module loading
- 128-bit internal object identifiers
- Single-source-of-truth versioning
- Dependency-free development model

The project remains in an active research and experimentation stage.

---

# Architecture

BrisartOS is organized into multiple layers.

## Boot Layer

Responsible for:

- Boot image generation
- Image inspection
- Startup experimentation
- Bare-metal research

---

## Runtime Layer

Responsible for:

- Runtime initialization
- Module loading
- Internal coordination
- System API management

---

## Service Layer

Responsible for:

- Archive services
- Filesystem services
- Settings services
- Update services

Services provide stable interfaces for applications and modules without requiring modifications to operating system internals.

---

## Application Layer

Built-in BrisartOS applications live here.

Examples include:

- Browser
- Archive tools
- Settings tools
- Future research utilities

Applications are considered part of the operating environment itself.

---

## Module Layer

Modules allow laboratories, archivists, researchers, and users to extend BrisartOS without modifying the operating system core.

Example:

```text
modules/
└── hello_lab/
    └── module.py
```

Modules are pure Python and communicate through the BrisartOS system APIs.

---

## Object Model

BrisartOS uses 128-bit internal identifiers.

These identifiers can be used for:

- Archive records
- Research datasets
- Services
- Modules
- Identity records
- Long-term digital references

Example: `2dff55f9dad6a6fa8c88a67f57db8ae8`

This object model is intended to provide durable identifiers for future operating system and research platform development.

---

## Repository Structure

```text
BrisartOS/
├── brisartos/
│   ├── apps/
│   │   ├── __init__.py
│   │   └── browser.py
│   ├── boot/
│   │   ├── inspect_image.py
│   │   ├── make_boot_image.py
│   │   └── make_floppy_image.py
│   ├── runtime/
│   │   ├── brisart_platform.py
│   │   ├── module_api.py
│   │   ├── module_loader.py
│   │   ├── runtime.py
│   │   └── system_api.py
│   ├── services/
│   │   ├── archive_service.py
│   │   ├── filesystem_service.py
│   │   ├── service_registry.py
│   │   ├── settings_service.py
│   │   └── update_service.py
│   ├── shell/
│   │   └── shell.py
│   ├── build.py
│   ├── emitter.py
│   ├── labels.py
│   └── platform.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CHANGELOG.md
│   ├── DEPENDENCY_POLICY.md
│   └── SAFETY.md
├── modules/
│   └── hello_lab/
│       └── module.py
├── .gitignore
├── LICENSE.txt
├── README.md
└── version.py
```

---

## Development Principles

### Pure Python

BrisartOS is authored using Python.

Python is used for:

- Runtime development
- Module development
- Operating system tooling
- Binary image generation
- Services
- Applications

Python standard library components are preferred whenever practical.

### No Dependencies

BrisartOS follows a strict dependency-free policy.

The project should not require:

- Third-party Python packages
- External frameworks
- Cloud infrastructure
- Online services
- Package managers

The Python standard library is preferred whenever possible.

### Fully Custom

BrisartOS is intended to be custom-built rather than layered on top of existing software ecosystems.

The project favors understanding how systems work internally rather than relying on hidden abstractions.

---

## Intended Environments

BrisartOS is being researched for environments such as:

- Research laboratories
- Digital preservation projects
- Archive environments
- Offline workstations
- Air-gapped systems
- Identity infrastructure
- Long-term knowledge repositories
- Preservation-focused computing environments

---

## Roadmap

_Status current as of v0.9.1-alpha (2026-08-25). Update this line whenever
status markers below are revised, so this table can never silently go stale.
Completed items are moved to the section below as they land; see
`docs/CHANGELOG.md` for full details on each release._

### Completed

- Filesystem experimentation (sandboxed FilesystemService) — ✅ v0.8.0-alpha
- Wire ServiceRegistry through to modules via `get_service()` — ✅ v0.7.0-alpha
- Improve module APIs (permission-aware ModuleAPI wrapper) — ✅ v0.6.0-alpha
- Wire the service framework into the runtime — ✅ v0.5.0-alpha
- Single-source-of-truth versioning — ✅ v0.4.1-alpha

### Currently In Development

- Hardware-installable operating system — ⚙️ In development
- Add an automated test suite covering runtime boot, module loading, and permission enforcement — ⚙️ In development

### Short-Term Goals

- Expand service architecture — 🟡 Partial
- Improve shell capabilities — 🟡 Partial
- Expand runtime functionality — 🟡 Partial / open-ended
- Build archive service infrastructure — ❌ Not started
- Implement persistent logic for SettingsService (key/value config storage) — ❌ Not started

### Mid-Term Goals

- Runtime initialization research — 🟡 Partial
- Modular workflow development — 🟡 Partial
- Settings management — ❌ Not started
- Update infrastructure — ❌ Not started
- Research application framework — ❌ Not started
- Implement real logic for ArchiveService (versioned snapshots, object-ID linked records) — ❌ Not started
- Implement real logic for UpdateService (auto-download, manual-install update flow) — ❌ Not started
- Add CI pipeline (lint + automated tests) via GitHub Actions — ❌ Not started
- Stress-test the module loader and permission model with multiple concurrent modules — ❌ Not started

### Long-Term Goals

- Research-focused runtime environment — ❌ Not started
- Preservation tooling integration — ❌ Not started
- Identity management integration — ❌ Not started
- Offline documentation infrastructure — ❌ Not started
- Archive management capabilities — ❌ Not started
- Air-gapped workstation profile — ❌ Not started
- Long-term software stewardship platform — ❌ Not started
- Module signing / trust verification for shared or third-party modules — ❌ Not started
- Integration hooks with BrisartIdentityTools and BrisartPreservationTools — ❌ Not started

---

## Experimental Notice

BrisartOS is an experimental research project.

Boot artifacts, runtimes, modules, services, applications, and operating system components should not be considered production-ready.

All development should be treated as research and experimentation.

---

## Vision

The long-term vision of BrisartOS is to create a fully custom, local-first, dependency-free operating environment designed for research, digital preservation, identity infrastructure, archive management, and long-term ownership of information.

BrisartOS aims to provide:

- A fully custom runtime environment
- Modular research tooling
- Offline-first operation
- Air-gapped deployment capability
- Long-term maintainability
- Full source transparency
- Complete control over the software stack

---

## BrisartOS

_Pure Python. No Dependencies. Fully Custom. Modular by Design._
