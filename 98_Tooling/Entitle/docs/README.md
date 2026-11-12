# Entitle

**Software Rights Management for Independent and Offline Environments**

Entitle is software that helps developers and organizations define, distribute, document, and manage software rights in environments where privacy, independence, ownership, and long-term accessibility matter.

Built for developers, research organizations, archives, government environments, and air-gapped systems, Entitle provides practical tools for managing software entitlements, deployment records, software provenance, ownership documentation, and distribution governance without relying on cloud infrastructure, online activation, telemetry, or vendor-controlled services.

Entitle is **pure Python**, uses **no external packages**, takes its cryptography from the archive's own `97_Encryption` rather than carrying a copy, and is designed to be **local-first, offline, and auditable**. Entitlements are **signed with Ed25519**: a lab or a protected program holds only the issuer's public key, so it can verify an entitlement but can never forge one.

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

Deployments are governed seats: a deployment is only recorded when a valid entitlement grants the right to run, the entitlement has not been revoked, the host does not already hold a seat, and a seat is free under the deployment limit. Releasing a host gives its seat back.

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

Revoke an issued entitlement without any online service. Revocations (and optional reinstatements) are recorded in the same tamper-evident local store, so a revoked entitlement is refused for new deployments while the full history is preserved. A signed revocation list carries revocation to machines that never see the store, on a USB stick if need be.

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

Deployment, fork, provenance, and revocation records are written to a single append-only log. Each entry is linked to the previous one through a SHA-256 hash chain, so any edit, deletion, or reordering of earlier records can be detected during verification. Writers take an operating-system lock on a `.lock` file beside the store, so the command line and the window can record at the same time without forking the chain or exceeding a deployment limit. The operating system releases the lock if a writer is killed, so a crash never leaves the store locked. Records can never be edited or removed, so a record with a blank required field (an entitlement ID, host, fork name, and so on) is refused before it is written. A log damaged by a crash or a stray edit, even down to a character cut in half, is still audited: the report shows which record is damaged and keeps counting the rest. Signed checkpoints catch what a hash chain alone cannot: records cut off the end, or a log rewritten with recomputed hashes.

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

# Security Model

Entitle is security software: it makes claims about who issued a right and whether a record has been changed, and programs make access decisions on those claims. This section states exactly what those claims are.

## What Entitle guarantees

- **Nobody without the issuer's signing key can create or alter a signed entitlement that verifies.** Signed entitlements use Ed25519 (RFC 8032), a standard, widely reviewed signature algorithm. A verifier, including a protected program on a lab's machine, holds only the public key, so it can check entitlements but can never issue one.
- **An entitlement opens only for the identity it names.** Verification requires the exact issuer, subject (lab) and product; a file issued to one lab is denied for another.
- **A revoked entitlement is refused offline**, by any program given the issuer's signed revocation list, which a lab can read but cannot edit, and (with a host state file) cannot swap for an older list.
- **Records cannot be edited, deleted or reordered without detection.** The record log is a SHA-256 hash chain, and a signed checkpoint additionally proves that records were not cut off the end or rewritten with recomputed hashes.
- **Seat limits hold under concurrency.** The revocation check, seat count and append run under one operating-system lock.
- **Nothing is ever half-written**, and a refused input writes nothing to a log that can never be corrected.

## What Entitle does not guarantee

- **It is not copy protection.** A check that runs on a machine the user controls can be patched out by someone willing to edit the program. Entitle makes forging an entitlement infeasible; it does not make the program that checks it tamper-proof. No offline licensing system does.
- **Machine binding and clock checks are deterrents.** A fingerprint can be copied, and a host state file deleted, by an administrator of that machine.
- **Deployment records are as honest as whoever writes them.** The host name is what the operator typed.
- **Revocation reaches a machine only when that machine is given a newer revocation list.**
- **Shared-key entitlements** (the format before 0.7.0, kept for compatibility) need the same master key to issue and to verify, so anyone who can verify one can issue one. Convert them to signed entitlements.
- **BSR2 is experimental research cryptography** without independent review. Signed entitlements, revocation lists and checkpoints do not depend on it; it protects shared-key entitlements and the signing key file at rest.

## Keys

The issuer's **signing key** is the one secret that matters. It is stored sealed under a passphrase (stretched with scrypt) and is owner-readable only. Entitle refuses to create it inside a Git working tree, because there it is one `git add` away from being published; keep it in your home folder or on removable media, and back it up. The **public key** is not secret: ship it with every protected program and give it to every lab. If a signing key is lost, issue a new key pair and re-issue; if it is leaked, stop trusting its public key.

---

# Requirements

- Python 3.10 or newer
- The Python standard library only: no external packages. tkinter is needed only for the desktop window; every command-line command runs without it.
- `97_Encryption/Official` beside `98_Tooling` in the same archive folder, including `brisart_security_signature.py` (Ed25519). This is where all of Entitle's cryptography comes from; Entitle keeps no copy of it.

Entitle's one connection to it is `entitle/encryption.py`, which finds `97_Encryption/Official` relative to itself (no configuration, no absolute path) and refuses to run against any other copy. The Ed25519 module must reproduce the RFC 8032 test vector before it is trusted. If the folder or a module is missing, Entitle still starts; the record commands still work, and every command that needs the missing piece says `Encryption not found` or `Signatures not found` and why, instead of falling back to anything weaker. A `97_Encryption` without the signature module still serves shared-key entitlements. `python run.py --version` shows what is linked. Copy the whole archive, or both `97_Encryption` and `98_Tooling`, when moving Entitle between machines.

---

# Project Layout

```
BrisartResearchArchive/
├── 97_Encryption/
│   └── Official/           # BSR2 and Ed25519: the cryptography Entitle links to (not part of Entitle)
└── 98_Tooling/
    └── Entitle/
```

```
Entitle/
├── run.py                  # Entry point: python run.py opens the window, python run.py <command> runs one
├── cli.py                  # The command line
├── version.py              # The one place the version lives
├── entitle/                # Everything Entitle knows; no command-line or window code, no __init__.py
│   ├── common.py           #   EntitleError, canonical JSON, the clock, input checks, atomic writes
│   ├── rights.py           #   What an entitlement says and how its rights are judged
│   ├── encryption.py       #   The only link to 97_Encryption (BSR2 and Ed25519)
│   ├── signing.py          #   Issuer key pairs, key files, and the signed document format
│   ├── host.py             #   Machine fingerprint and the host state (clock and list rollback)
│   ├── entitlements.py     #   The .entitle file: issue, verify, inspect, migrate
│   ├── records.py          #   Tamper-evident record log and its writer lock
│   ├── tracking.py         #   Deployments and releases (governed seats), forks and provenance
│   ├── revoke.py           #   Revoke, reinstate, check
│   ├── revocation_list.py  #   Signed revocation lists for machines that never see the log
│   ├── checkpoints.py      #   Signed checkpoints that catch a log cut short or rewritten
│   └── report.py           #   Audit report
├── gui/                    # The desktop window
│   ├── window.py           #   Window, output pane, error handling
│   └── tabs.py             #   The seven workflow tabs and their form layout
├── examples/               # protected_app_example.py: a program that holds only the public key
├── tests/                  # pytest suite; test_<name>.py covers <name>.py (test_gui.py covers gui/)
├── docs/                   # README.md and CHANGELOG.md
├── keys/                   # Public keys only (created on use); signing keys belong outside the repository
├── entitlements/           # Issued .entitle files and revocation lists (created on use, git-ignored)
├── records/                # Record logs (created on use, git-ignored)
└── reports/                # Saved reports and checkpoints (git-ignored)
```

The command line and the window both call the same functions in `entitle/`, so they cannot disagree about what an operation does. Dependencies point one way: `common.py` is at the bottom; `encryption.py` links the cryptography; `signing.py` builds on it; `records.py` never touches cryptography, and `revoke.py` and `report.py` build on it; `revocation_list.py` and `checkpoints.py` join signing to the log; `entitlements.py` brings authentication, rights, the host checks and revocation together for verification; and `tracking.py` builds on `entitlements.py` because a deployment needs a verified entitlement. The record log never touches cryptography, which is why it keeps working without `97_Encryption`.

---

# Tools

Run `python run.py` to open the window, or `python run.py <command>` to use the command line. `python run.py --help` lists the commands and `python run.py <command> --help` each command's options. Examples use Windows `^` line continuation; on Linux and macOS use `\`.

Every record command needs an explicit `--store`: there is deliberately no default location, so records never land somewhere you did not choose.

## Quick start (signed entitlements)

**1. Create the issuer key pair, once.** You are asked for a passphrase twice (at least 12 characters). Keep the signing key outside the repository.

```
python run.py keys generate --name JasonBrisart ^
    --signing-key %USERPROFILE%\EntitleKeys\issuer.signing-key ^
    --public-key keys/issuer.public-key
```

**2. Issue an entitlement to a lab.**

```
python run.py issue ^
    --issuer JasonBrisart --subject ResearchLabA --product EntitleDemo ^
    --entitlement-id lab-a-demo-001 ^
    --signing-key %USERPROFILE%\EntitleKeys\issuer.signing-key ^
    --modify --fork --deployment-limit 3 ^
    --output entitlements/lab_a.entitle
```

**3. Give the lab the `.entitle` file and the public key.** Anyone with the public key can verify; nobody can issue:

```
python run.py verify ^
    --issuer JasonBrisart --subject ResearchLabA --product EntitleDemo ^
    --public-key keys/issuer.public-key ^
    --file entitlements/lab_a.entitle
```

## Secrets

Secrets never have to appear on the command line, where the process list and shell history would show them. A signing key's passphrase is read from `--passphrase-file`, the `ENTITLE_PASSPHRASE` environment variable, or a prompt; there is deliberately no `--passphrase` option. A shared master key is read from `--master-key-file`, `ENTITLE_MASTER_KEY`, or `--master-key` (kept for compatibility; avoid it for real keys). Abbreviated options are not accepted, so a mistyped option is an error rather than a different option.

## Keys

```
python run.py keys generate --name <issuer> --signing-key <file> --public-key <file> [--force]
python run.py keys show --key keys/issuer.public-key
```

`keys show` prints a key's name and key ID (the ID that every signed file names in its `Key-Id:` line). Existing key files are never replaced without `--force`. A signing key inside a Git working tree is refused unless you pass `--allow-in-repository`.

## Issue an entitlement

`--signing-key` issues a signed entitlement (recommended). Without it, `--master-key-file` (or `ENTITLE_MASTER_KEY`) issues a shared-key entitlement, as before 0.7.0, and the output says so.

Rights: `--enterprise`, `--modify`, `--fork`, `--export-source` and `--redistribute`. `--deployment-limit N` (0 or more; 0 verifies but permits no tracked deployment) or `--unlimited`. `--support-tier` is a free label. `--expires` takes an ISO timestamp; a date alone (`2026-12-31`) means 00:00 UTC at the start of that day, so give a time (`2026-12-31T23:59:59Z`) to include the whole day.

Signed entitlements can also carry:

- `--not-before <timestamp>`: not valid before then (it must be earlier than `--expires`).
- `--machine <fingerprint>`, repeatable: valid only on those machines. Run `python run.py fingerprint` on each machine to get its fingerprint.

An existing output file is never replaced without `--force`. Everything is checked before anything is written.

## Verify an entitlement

```
python run.py verify --issuer ... --subject ... --product ... --file entitlements/lab_a.entitle ^
    --public-key keys/issuer.public-key ^
    [--revocation-list entitlements/revoked.entitle-crl] [--store records/entitle_records.log] ^
    [--state entitlements/host-state.json] [--machine <fingerprint>]
```

A signed file needs `--public-key` (repeat it to trust several issuer keys); a shared-key file needs the master key; the error says which is missing. Exits 0 with `VERIFIED`, or 1 with `DENIED: <reason>`. Reasons include `signature_invalid`, `unknown_signing_key`, `wrong_issuer`, `wrong_subject`, `wrong_product`, `entitlement_not_yet_valid`, `entitlement_expired`, `clock_before_issue_time`, `machine_not_authorized`, `entitlement_revoked`, `revocation_list_invalid`, `revocation_list_rollback`, `clock_rollback_detected` and, for shared-key files, `bsr_verification_failed`.

- `--revocation-list` refuses an entitlement the issuer has revoked. A list that does not verify, or names another issuer, fails closed.
- `--store` refuses an entitlement revoked in that record log.
- `--state` keeps a small file of the latest time and the newest revocation list this machine has seen, and refuses a clock wound backwards or an older list.
- `--machine` checks against another machine's fingerprint instead of this one's.

## Inspect an entitlement

```
python run.py inspect --file entitlements/lab_a.entitle
```

Shows the format, the signing key ID and, for a signed file, what it claims, marked `UNVERIFIED`; only `verify` proves who issued it. A shared-key file is encrypted, so inspect shows nothing of its contents.

## Migrate or convert an entitlement

```
python run.py migrate --issuer ... --subject ... --product ... --master-key-file master.key ^
    --file entitlements/older_lab.entitle [--signing-key %USERPROFILE%\EntitleKeys\issuer.signing-key]
```

Without `--signing-key`, a file written before 0.5.0 is re-sealed in the current shared-key format (`UNCHANGED` if it already is). With `--signing-key`, any shared-key file is converted to a signed entitlement, keeping its ID, rights, limit, issue time and expiry. The new file is checked to open to the same entitlement before it replaces the old one in a single step; a file that does not open with the given values is left untouched. Keep a copy if an older Entitle must still read it. The Verify tab has the same two buttons.

## Deployments and seats

A deployment is recorded only if the entitlement verifies, grants `can_run`, is not revoked, the host does not already hold a seat, and a seat is free under the limit. Releasing a host gives its seat back.

```
python run.py track deploy --issuer JasonBrisart --subject ResearchLabA --product EntitleDemo ^
    --public-key keys/issuer.public-key --entitlement entitlements/lab_a.entitle ^
    --host lab-a-node-01 --environment air-gapped --store records/entitle_records.log

python run.py track release --product EntitleDemo --subject ResearchLabA ^
    --entitlement-id lab-a-demo-001 --host lab-a-node-01 --reason decommissioned ^
    --store records/entitle_records.log
```

A refused deployment is not an error: the command exits 0 and prints `"recorded": false` with the reason (`deployment_limit_reached`, `already_deployed_on_host`, `entitlement_revoked`, ...). Add `--strict` to exit 3 instead, for scripts.

## Record a fork or provenance

```
python run.py track fork --product EntitleDemo --source-version 1.4.0 ^
    --fork-name lab-a-custom --maintainer ResearchLabA --store records/entitle_records.log

python run.py track provenance --product EntitleDemo --origin JasonBrisart ^
    --version 1.4.0 --custodian ResearchLabA --store records/entitle_records.log
```

## List records

```
python run.py track list --type deployment --store records/entitle_records.log
```

`--type` is one of `deployment`, `fork`, `provenance`, `revocation`, `reinstatement` or `release`; omit it to list everything.

## Revoke, reinstate, check, and publish a revocation list

```
python run.py revoke revoke --entitlement-id lab-a-demo-001 --issuer JasonBrisart ^
    --reason "key compromise" --store records/entitle_records.log
python run.py revoke reinstate --entitlement-id lab-a-demo-001 --reason cleared ^
    --store records/entitle_records.log
python run.py revoke check --entitlement-id lab-a-demo-001 --store records/entitle_records.log

python run.py revoke publish --issuer JasonBrisart ^
    --signing-key %USERPROFILE%\EntitleKeys\issuer.signing-key ^
    --store records/entitle_records.log --output entitlements/revoked.entitle-crl
```

An entitlement ID is matched exactly, so `Lab-a-demo-001` does not revoke `lab-a-demo-001`; IDs with spaces at either end are refused. `revoke publish` writes a signed list of every entitlement currently revoked for that issuer (and those revoked with no issuer recorded), numbered so a later list always has a higher sequence. Send it to labs the way you sent the entitlement; programs that check it refuse revoked entitlements without ever seeing your log.

## Checkpoints

```
python run.py checkpoint create --signing-key %USERPROFILE%\EntitleKeys\issuer.signing-key ^
    --store records/entitle_records.log --output reports/checkpoint-2026-11-11.entitle-checkpoint

python run.py checkpoint verify --public-key keys/issuer.public-key ^
    --store records/entitle_records.log --checkpoint reports/checkpoint-2026-11-11.entitle-checkpoint
```

A hash chain cannot show that records were cut off the end, or that the log was rewritten from some record onward with every later hash recomputed. A checkpoint is a signed statement of the log's length and last hash. Keep it where the log's operator cannot change it (with an auditor, on removable media). `checkpoint verify` exits 0 when the checkpointed records are exactly as they were (records added since are fine) and 1 with `log_truncated`, `log_rewritten`, `chain_broken` or a signature reason otherwise.

## Generate an audit report

```
python run.py report --store records/entitle_records.log
python run.py report --store records/entitle_records.log --format json --output reports/entitle_audit.json
```

The report summarizes records by type and deployments by product, verifies the hash chain, and prints the head hash. A damaged record is reported as `BROKEN` with its index rather than stopping the report, and a store file that does not exist is reported as having no records, not as a verified log. The command exits 0 either way; add `--strict` to exit 3 on a broken chain.

## Open the window

```
python run.py
```

With no arguments `run.py` opens the window; `python run.py gui` does the same. On Windows you can also double-click `run.py`, as long as `.py` files are associated with Python.

The window has seven tabs: Keys, Issue, Verify, Deploy, Fork / Provenance, Revoke / Reinstate and Audit Report. Results and errors appear in the pane at the bottom. The identity, keys, passphrase, entitlement file and record store are shared across tabs, so you type each once. The window asks before it replaces an existing file. It opens at 880x640, or larger when its tallest tab needs more room, never larger than your screen, and needs tkinter, which ships with the standard Python installers on Windows and macOS and with most Linux distributions.

If the window does not open, start `python run.py` from a terminal to read why: it prints the usage and then one error line, and exits 1. The usual causes are no tkinter or no display (for example over SSH). The command-line commands need neither.

## Errors

Expected problems (a missing key or passphrase, a wrong passphrase, `Encryption not found` or `Signatures not found`, a blank or badly spaced identifier, an expiry that is not an ISO timestamp, a negative deployment limit, a file that already exists, a missing or unusable file, a damaged or busy record store) print a single `Error: ...` line on stderr and exit 1. Nothing is written when an input is refused. A mistyped command or option exits 2 with usage help.

An entitlement file must be UTF-8 text. A byte-order mark and Windows line endings are accepted. A file written by Windows PowerShell's `>` or `Out-File` is UTF-16, and Entitle says so; copy the original file instead. Files over 1 MiB are refused by name. Characters the console cannot encode are printed as backslash escapes instead of failing; the stored records keep the text exactly as typed.

## Protect an application

`examples/protected_app_example.py` is a program whose base features always run and whose governed features unlock only with the matching right. It holds the issuer's public key and no secret, checks the revocation list in `entitlements/` when there is one, and keeps a host state file to notice a clock wound back. Create the keys and issue `entitlements/lab_a.entitle` with the Quick start commands, then run:

```
python examples/protected_app_example.py
```

If the entitlement cannot be checked for any reason (missing, damaged, signed by another key, a shared-key file, revoked, `97_Encryption` not found) the base program still starts and every governed feature stays locked.

## Run the tests

```
python -m pip install pytest
python -m pytest tests
```

The tests use pytest and run from `98_Tooling/Entitle` with `97_Encryption` beside `98_Tooling`; the application itself needs nothing beyond the standard library and that folder. `python -m pytest tests/test_end_to_end.py -v` is the check that everything works with your cryptography from start to finish: it installs a copy of Entitle and of the linked `97_Encryption/Official` into a fresh archive and runs the shared-key and signed workflows through real `run.py` processes, then races several processes against a deployment limit. The Ed25519 module's own tests, including the RFC 8032 vectors, are in `97_Encryption/Official/tests/test_brisart_security_signature.py`.

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
- Copy protection: it makes entitlements unforgeable and records tamper-evident, but a check running on a machine someone controls can be patched out by that someone (see Security Model)

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
