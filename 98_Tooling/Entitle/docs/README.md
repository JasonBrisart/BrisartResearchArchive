# Entitle

**Software Rights Management for Independent and Offline Environments**

Entitle is software that helps developers and organizations define, distribute, document, and manage software rights in environments where privacy, independence, ownership, and long-term accessibility matter.

Built for developers, research organizations, archives, government environments, and air-gapped systems, Entitle provides practical tools for managing software entitlements, deployment records, software provenance, ownership documentation, and distribution governance without relying on cloud infrastructure, online activation, telemetry, or vendor-controlled services.

Entitle is **pure Python**, uses **no external packages**, takes its encryption from the archive's own `97_Encryption` (BSR2) rather than carrying a copy, and is designed to be **local-first, offline, and auditable**.

---

# Why Entitle?

Most software licensing systems depend on:

- Cloud-hosted platforms
- Online activation services
- Vendor-controlled infrastructure
- Internet connectivity
- User tracking and telemetry

For many developers and organizations, these requirements introduce additional complexity, operational risk, privacy concerns, and long-term dependency on external systems.

Entitle takes a different approach.

Your software rights records remain within your environment and under your control.

No cloud requirements.
No activation servers.
No account dependencies.
No telemetry.
No vendor lock-in.

---

# Key Features

## Software Entitlements

Create and manage entitlement records that define what organizations, customers, or internal teams are authorized to do with software.

Examples include:

- Internal deployment rights
- Private modification rights
- Internal fork permissions
- Upgrade eligibility
- Distribution authorizations

---

## Deployment Tracking

Document where software has been deployed across:

- Workstations
- Servers
- Research environments
- Archive systems
- Government infrastructure
- Air-gapped networks

Deployments are governed: a deployment is only recorded when a valid entitlement grants the right to run, the entitlement has not been revoked, and its deployment limit has not been reached.

---

## Internal Fork Management

Track software forks and custom distributions.

Record:

- Source versions
- Fork dates
- Internal maintainers
- Custom modifications
- Environment-specific variants

Entitle helps organizations understand software lineage and internal development history.

---

## Provenance & Ownership Records

Track:

- Software origin
- Distribution history
- Ownership records
- Version lineage
- Verification information

Maintain clear documentation showing where software originated and how it has evolved over time.

---

## Revocation & Reinstatement

Revoke an issued entitlement without any online service. Revocations (and optional reinstatements) are recorded in the same tamper-evident local store, so a revoked entitlement is refused for new deployments while the full history is preserved.

---

## Audit & Reporting

Generate reports covering:

- Entitlements
- Deployments
- Forks
- Ownership records
- Revocation status
- Chain integrity

Export records for internal review, governance processes, and long-term retention.

---

## Tamper-Evident Record Store

Deployment, fork, provenance, and revocation records are written to a single append-only log. Each entry is linked to the previous one through a SHA-256 hash chain, so any edit, deletion, or reordering of earlier records can be detected during verification. Writers take an operating-system lock on a `.lock` file beside the store, so the command line and the window can record at the same time without forking the chain or exceeding a deployment limit. The operating system releases the lock if a writer is killed, so a crash never leaves the store locked. Records can never be edited or removed, so a record with a blank required field (an entitlement ID, host, fork name, and so on) is refused before it is written. A log damaged by a crash or a stray edit, even down to a character cut in half, is still audited: the report shows which record is damaged and keeps counting the rest.

---

## Offline Operation

Entitle operates without requiring:

- Cloud services
- Online activation
- License servers
- Telemetry
- User tracking
- Vendor-operated infrastructure

Organizations retain complete control over their records.

---

## Archival Support

Preserve software ownership and entitlement information alongside software assets.

Designed for:

- Archives
- Museums
- Libraries
- Research institutions
- Long-term preservation projects

Ensure software rights records remain accessible long after deployment.

---

# Requirements

- Python 3.10 or newer
- The Python standard library only: no external packages. tkinter is needed only for the desktop window; every command-line command runs without it.
- `97_Encryption/Official` beside `98_Tooling` in the same archive folder. This is where all of Entitle's encryption comes from; Entitle keeps no copy of it.

Entitle's one connection to BSR2 is `entitle/encryption.py`, which finds `97_Encryption/Official` relative to itself (no configuration, no absolute path) and refuses to run against any other copy. If the folder is missing or incompatible, Entitle still starts, `report`, `revoke` and the `track` record commands still work, and every command that seals or opens an entitlement says `Encryption not found` and why, instead of falling back to anything weaker. `python run.py --version` shows which encryption is linked. Because Entitle needs its sibling folder, copy the whole archive, or both `97_Encryption` and `98_Tooling`, when moving it between machines. BSR2 is experimental research software and should be treated as controlled-environment protection unless independently reviewed.

New entitlement files are BSR2 sealed messages (BSR2-S64-SIV), stored as armored text. Files written by Entitle before 0.5.0 (BSR2 Alpha 3) still verify, and `migrate` re-seals them in the current format.

---

# Project Layout

```
BrisartResearchArchive/
├── 97_Encryption/
│   └── Official/           # BSR2: the encryption Entitle links to (not part of Entitle)
└── 98_Tooling/
    └── Entitle/
```

```
Entitle/
├── run.py                  # Entry point: python run.py opens the window, python run.py <command> runs one
├── cli.py                  # The command line (issue, verify, migrate, track, revoke, report, gui)
├── version.py              # The one place the version lives
├── entitle/                # Everything Entitle knows; no command-line or window code, no __init__.py
│   ├── common.py           #   EntitleError and the helpers every module shares
│   ├── rights.py           #   What an entitlement says and how its rights are judged
│   ├── entitlements.py     #   The .entitle file: issue, verify, migrate
│   ├── encryption.py       #   The only link to 97_Encryption
│   ├── records.py          #   Tamper-evident record log and its writer lock
│   ├── tracking.py         #   Deployments (governed), forks and provenance
│   ├── revoke.py           #   Revoke, reinstate, check
│   └── report.py           #   Audit report
├── gui/                    # The desktop window
│   ├── window.py           #   Window, output pane, error handling
│   └── tabs.py             #   The six workflow tabs and their form layout
├── examples/               # protected_app_example.py
├── tests/                  # pytest suite; test_<name>.py covers <name>.py (test_gui.py covers gui/)
├── docs/                   # README.md and CHANGELOG.md
├── entitlements/           # Issued .entitle files (created on use, git-ignored)
├── records/                # Record logs (created on use, git-ignored)
└── reports/                # Saved reports (git-ignored)
```

The command line and the window both call the same functions in `entitle/`, so they cannot disagree about what an operation does. Dependencies point one way: `common.py` sits at the bottom; `entitlements.py` builds on `rights.py` and `encryption.py`; `tracking.py`, `revoke.py` and `report.py` build on `records.py`; and only `tracking.py` joins the two, because a deployment needs a verified entitlement. The record log never touches encryption, which is why it keeps working without `97_Encryption`.

None of Entitle's folders has an `__init__.py`: `entitle/` and `gui/` are implicit namespace packages, the same convention the rest of the Brisart tooling uses.

---

# Tools

Run `python run.py` to open the window, or `python run.py <command>` to use the command line. `python run.py --help` lists the commands and `python run.py <command> --help` lists each command's options. Windows examples use `^` for line continuation; on Linux and macOS use `\` instead.

Every record command needs an explicit `--store`: there is deliberately no default location, so records never land somewhere you did not choose.

## Issue an entitlement

Create a protected, offline entitlement container. The master key must be 32 to 1024 bytes and is used directly as the BSR2 key, so make it long and random.

```
python run.py issue ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --entitlement-id lab-a-demo-001 ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --deployment-limit 3 ^
    --output entitlements/lab_a.entitle
```

Rights flags `--enterprise`, `--modify`, `--fork`, `--export-source` and `--redistribute` grant the matching rights. `--expires` takes an ISO timestamp and is checked before anything is written; a date alone (`2026-12-31`) means 00:00 UTC at the start of that day, so give a time (`2026-12-31T23:59:59Z`) to include the whole day. `--deployment-limit` is 0 or more; 0 gives an entitlement that verifies (for example to unlock features) but permits no tracked deployment. `--drbg-seed` (64 bytes or more) and `--drbg-personalization` (16 or more) are optional: they add a generator of your choosing on top of the fresh system entropy BSR2 always uses, and nothing needs them.

## Verify an entitlement

```
python run.py verify ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --file entitlements/lab_a.entitle
```

Exits 0 and prints `VERIFIED` when the entitlement is valid; exits 1 and prints `DENIED: <reason>` otherwise. When the file still uses the previous encryption, `VERIFIED` is followed by a note pointing at `migrate`. A missing `97_Encryption` is an error (exit 1), never `DENIED`.

## Migrate an entitlement to the current encryption

Files written by Entitle before 0.5.0 use the previous encryption (BSR2 Alpha 3). They keep verifying, and `migrate` re-seals one in place with the current encryption while keeping the entitlement exactly as issued (ID, rights, limit, issue time and expiry):

```
python run.py migrate ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --file entitlements/older_lab.entitle
```

It prints `MIGRATED`, or `UNCHANGED` for a file that already uses the current encryption. The new file is checked to open to the identical entitlement before it replaces the old one in a single step, and a file that does not open with the given issuer, subject, product and key is left untouched with an error. Entitle versions before 0.5.0 cannot open a migrated file, so keep a copy first if one of them must still read it. The window does the same with the Migrate to Current Encryption button on the Verify tab.

## Record a governed deployment

Only recorded if the entitlement verifies, grants `can_run`, is not revoked, and the deployment limit has not been reached. A refused deployment is not an error: the command exits 0 and prints `"recorded": false` with the reason.

```
python run.py track deploy ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --entitlement entitlements/lab_a.entitle ^
    --host lab-a-node-01 ^
    --environment air-gapped ^
    --store records/entitle_records.log
```

## Record a fork or provenance

```
python run.py track fork ^
    --product EntitleDemo ^
    --source-version 1.4.0 ^
    --fork-name lab-a-custom ^
    --maintainer ResearchLabA ^
    --store records/entitle_records.log

python run.py track provenance ^
    --product EntitleDemo ^
    --origin JasonBrisart ^
    --version 1.4.0 ^
    --custodian ResearchLabA ^
    --store records/entitle_records.log
```

## List records

```
python run.py track list --type deployment --store records/entitle_records.log
```

`--type` is one of `deployment`, `fork`, `provenance`, `revocation` or `reinstatement`; omit it to list everything.

## Revoke, reinstate, or check an entitlement

```
python run.py revoke revoke ^
    --entitlement-id lab-a-demo-001 ^
    --issuer JasonBrisart ^
    --product EntitleDemo ^
    --reason "key compromise" ^
    --store records/entitle_records.log

python run.py revoke reinstate ^
    --entitlement-id lab-a-demo-001 ^
    --reason "cleared" ^
    --store records/entitle_records.log

python run.py revoke check ^
    --entitlement-id lab-a-demo-001 ^
    --store records/entitle_records.log
```

An entitlement ID is matched exactly as typed, so a revocation recorded for ` lab-a-demo-001` (with a leading space) or `Lab-a-demo-001` does not revoke `lab-a-demo-001`; run `revoke check` to confirm.

## Generate an audit report

```
python run.py report --store records/entitle_records.log

python run.py report ^
    --store records/entitle_records.log ^
    --format json ^
    --output reports/entitle_audit.json
```

The report summarizes records by type and deployments by product, and verifies the tamper-evident hash chain across the whole store. A damaged record is reported as `BROKEN` with its index rather than stopping the report; the readable records are still counted and the report says how many lines could not be read. A store file that does not exist is reported as having no records, not as a verified log. The report command exits 0 either way; read the chain line (or `chain.valid` in the JSON) for the result.

## Open the window

```
python run.py
```

With no arguments `run.py` opens the window; `python run.py gui` does the same. On Windows you can also double-click `run.py`, as long as `.py` files are associated with Python.

The window opens at 880x640, or larger when its tallest tab needs more room, and never larger than your screen. It has six tabs: Issue, Verify, Deploy, Fork / Provenance, Revoke / Reinstate and Audit Report. Results and errors appear in the pane at the bottom. The issuer, subject, product, master key, entitlement file and record store are shared across tabs, so you type each once: issue an entitlement, switch to Verify, then Deploy, with nothing to retype. The window needs tkinter, which ships with the standard Python installers on Windows and macOS and with most Linux distributions.

If the window does not open, start `python run.py` from a terminal to read why: it prints the usage and then one error line, and exits 1. The usual causes are that this Python has no tkinter, or that there is no display (for example over SSH without a desktop). The command-line commands need neither. Double-clicking `run.py` closes its console as soon as the program ends, which hides that message.

## Errors

Expected problems (a key or seed that is too short, `Encryption not found`, a blank required field, an expiry that is not an ISO timestamp, a negative deployment limit, an entitlement too large to ever verify, a missing or unusable file, a damaged or busy record store) print a single `Error: ...` line on stderr and exit 1, with the reason BSR2, the store or the check gave. Nothing is written when an input is refused. A mistyped command or option exits 2 with usage help.

An entitlement file must be UTF-8 text. A byte-order mark and Windows line endings are accepted, so a file that passed through a Windows editor still verifies. A file written by Windows PowerShell's `>` or `Out-File` is UTF-16, and Entitle says so; copy the original file instead (`Copy-Item`, or Explorer). Files over 1 MiB are refused by name.

Names that the console or a redirected file cannot encode (Chinese or Cyrillic text on a Windows code page, for example) are printed as backslash escapes instead of failing, so a record that was written is never reported as an error. The record itself stores the text exactly as typed.

`--master-key` and the optional DRBG options are ordinary command-line arguments, so they are visible in the process list and in shell history. Use a throwaway key for testing and a controlled shell for real keys.

## Protect an application

`examples/protected_app_example.py` shows a program whose base features always run and whose governed features unlock only with the matching right. Issue `entitlements/lab_a.entitle` with the command above, then run:

```
python examples/protected_app_example.py
```

If the entitlement cannot be checked for any reason (missing, damaged, wrong key, `97_Encryption` not found) the base program still starts and every governed feature stays locked.

## Run the tests

```
python -m pip install pytest
python -m pytest tests
```

The tests use pytest and run from `98_Tooling/Entitle` with `97_Encryption` beside `98_Tooling`; the application itself needs nothing beyond the standard library and that folder.

`python -m pytest tests/test_end_to_end.py -v` is the check that everything works with your encryption from start to finish: it installs a copy of Entitle and of the linked `97_Encryption/Official` into a fresh archive layout and runs the whole workflow through real `run.py` processes (issue, verify, migrate, deploy past the limit, revoke, audit, tamper detection, the example application), then races several processes against a deployment limit. It takes a minute or two because BSR2 is pure Python.

---

# Designed For

- Independent Software Developers
- Software Vendors
- Research Organizations
- Universities
- Archives
- Museums
- Government Environments
- Air-Gapped Networks
- Restricted Infrastructure
- Self-Hosted Environments

---

# Core Principles

## Ownership

Organizations should control their software rights records, deployment history, and entitlement documentation.

## Independence

Software governance should not depend on the availability of third-party servers.

## Transparency

Rights and entitlement records should remain readable, portable, and understandable.

## Privacy

Software rights management should not require telemetry, tracking, or unnecessary data collection.

## Longevity

Software ownership and entitlement information should remain accessible years into the future.

---

# What Entitle Is Not

Entitle is not:

- An advertising platform
- A telemetry service
- A user tracking system
- A cloud licensing dependency
- An always-online activation platform

Entitle focuses on ownership records, software rights management, provenance tracking, deployment documentation, and governance workflows while preserving organizational control.

---

# Vision

Software rights management should not require surrendering control of operational records to external services.

Organizations should own their software governance data.

Developers should have alternatives to cloud-dependent licensing systems.

Entitle exists to provide a practical, offline-first approach to software rights management, entitlement tracking, deployment documentation, and software governance.

---

# One-Line Summary

**Entitle helps developers and organizations manage software rights, entitlements, deployments, provenance, revocation, and governance while preserving privacy, independence, and long-term control.**
