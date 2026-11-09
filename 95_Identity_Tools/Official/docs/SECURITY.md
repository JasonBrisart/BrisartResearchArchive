# Security Policy

BrisartIdentityTools is a solo-maintained research project.

Its security policy describes reporting and maintenance expectations. It does
not establish independent cryptographic review or production-security
certification.

## Reporting

### Where to report

Use either channel. Both are private and both are handled the same way.

**1. GitHub Private Vulnerability Reporting (preferred).** Open the
BrisartIdentityTools repository's **Security** tab and choose **Report a
vulnerability**. This creates a private advisory that only the reporter and the
maintainer can see. Put the full report there, including any reproduction
material, using [What to send](#what-to-send).

**2. Email.** Send the full report to **Jason@brisartresearcharchive.com**
instead, if you would rather not use GitHub or can't. Use a subject line in
this form:

```text
[SECURITY] Identity Tools <line> <version>: <short title>
```

For example: `[SECURITY] Identity Tools LTS-2028 1.4.1: keyring check value
accepts a truncated MAC`. The body follows [What to send](#what-to-send).

These are the only reporting channels. Do not report a suspected vulnerability
in a public issue, a pull request, a discussion forum, or
`docs/KNOWN_ISSUES.md` until it has been disclosed under
[Disclosure](#disclosure).

### What is a security issue

Report it here if a defect lets someone do any of the following through the
tools, beyond what
[What these tools do not protect against](BSR2_INTEGRATION.md#what-these-tools-do-not-protect-against)
already states:

- read sealed data, a master key, a recovery code, a passphrase, or a
  biometric template without the required secret;
- change sealed data, a keyring, a package, or a custody chain without the
  change being detected where the tools say it is detected;
- unlock a store, match an identity, or open a package that should have been
  refused;
- get around attempt limiting;
- make the tools write secret material, unencrypted, somewhere the
  documentation does not say it goes;
- make the tools fall back to weaker or local cryptography, or accept data from
  a BSR2 copy other than the linked one;
- corrupt or destroy stored data through ordinary use of a documented command,
  including migration.

A flaw in a BSR2 construction itself is also in scope. It is fixed in
`97_Encryption/Official`, not in Identity Tools (see
[Supported release lines](#supported-release-lines)).

### Not handled as security reports

These go to `docs/KNOWN_ISSUES.md` as ordinary issues, or are already
recorded:

- the limits listed in
  [What these tools do not protect against](BSR2_INTEGRATION.md#what-these-tools-do-not-protect-against),
  unless the report shows the tools do worse than that section states;
- issues already open in [Known issues](KNOWN_ISSUES.md), unless the report
  shows a new way to reach them or a higher impact than recorded;
- LTS-2028 1.3.x's KI-008, KI-009, and KI-010, which that line will not fix
  by design (the remedy is LTS-2028 1.4.x);
- releases whose support has ended (see
  [Supported release lines](#supported-release-lines));
- attacks that need an attacker who already controls the machine while a store
  is unlocked;
- crashes, wrong output, and performance problems with no effect listed under
  [What is a security issue](#what-is-a-security-issue).

### What to send

Use the same fields as the [Known issues](KNOWN_ISSUES.md#template) template,
plus impact:

- **Title:** one line, naming the line, version, and fault.
- **Reported date:** YYYY-MM-DD.
- **Severity:** your assessment, using [Severity](#severity).
- **Environment:** the output of `python cli.py version` and
  `python tools/envinfo.py`, run in the affected line's folder.
- **Component:** the file(s) or module(s), and whether the fault is in Identity
  Tools or in BSR2 itself, if known.
- **Steps to Reproduce:** numbered, from a fresh store where possible, using
  test data only.
- **Expected behavior** and **Actual behavior.**
- **Impact:** what an attacker gains, and what access they need first.
- **Tried / Ruled out:** anything that narrows the cause.
- **Disclosure:** any date by which you intend to publish.

Never send live credentials, real passphrases, real recovery codes, real
biometric samples, or personal information about anyone. Reproduce with
throwaway stores and synthetic or demo data. A report that contains real
secrets is deleted after the reproduction is rebuilt, and the reporter is
asked to rotate those secrets.

### Testing

Test only against stores, files, and machines you own or are authorized to
use. Do not test against anyone else's data.

## Severity

Severity is assessed against the protections these tools claim, not against
the limits they already document.

| Severity | Meaning |
| --- | --- |
| **Critical** | Recovers plaintext, a master key, a passphrase, or a recovery code from stored data without the secret, or forges data the tools accept as authentic, with no prior access beyond a copy of the files. |
| **High** | The same outcome under a realistic precondition (a specific input, a specific command, local access while the tools are closed), or bypasses attempt limiting, or destroys stored data through a documented command. |
| **Medium** | Weakens a protection without defeating it: leaks information the documentation says is protected, makes guessing measurably cheaper, or causes recoverable corruption. |
| **Low** | Hard to exploit, or exploitable only with access that already exposes the same data. |

The maintainer's assessment sets the final severity and is explained to the
reporter when it differs from theirs.

## Response expectations

BrisartIdentityTools has one maintainer. The targets below are commitments to
aim for, not guaranteed service levels. When one will be missed, the reporter
is told before it passes, with a new date.

| Stage | Target |
| --- | --- |
| Acknowledgement | Within 3 days of receipt |
| Triage: reproduced or not, severity, affected lines | Within 14 days of receipt |
| Status updates | At least every 14 days until the report is closed |
| Fix shipped, Critical | Within 14 days of triage |
| Fix shipped, High | Within 30 days of triage |
| Fix shipped, Medium | Within 90 days of triage |
| Fix shipped, Low | In the next scheduled release of each affected line |

"Fix shipped" means released on every supported line the defect affects, in
the order given under [Supported release lines](#supported-release-lines).
If a defect can't be fixed within a line's contract, the reporter is told
which line carries the remedy (see [Lifecycle](#lifecycle)).

A report is closed as one of: **fixed** (with the release on each line),
**won't fix** (with the reason, recorded in `docs/KNOWN_ISSUES.md`),
**not reproduced**, **duplicate**, or **not a security issue** (with where it
was moved). The reporter is told which, and why.

There is no bug bounty.

## Disclosure

Disclosure is coordinated. The reporter is asked not to publish details until
the fix has shipped on every affected supported line, or 90 days after triage,
whichever comes first. The maintainer can agree an earlier or later date with
the reporter, for example when a fix is ready sooner or needs a BSR2 change.

When the fix ships, each affected line's `docs/CHANGELOG.md` records it in a
**Security** entry with an identifier (for example `LTS-2028-SEC-4`),
severity, affected versions, the files changed, and the gap it closes. An
issue that will not be fixed on a line is recorded in that line's
`docs/KNOWN_ISSUES.md` instead.

Reporters are credited by name in the changelog entry if they want to be, and
not otherwise.

## Scope

Application components include:

- `crypto/`
- `vault/`
- `biometrics/`
- `packages/`
- `gui/`
- Root application and CLI entry points.
- File and bundle handling.
- Official-only integrity checkpoints and optional hardware integration.

BSR2 primitive issues can also be reported, but application-level fixes do not
independently resolve flaws in the underlying construction.

## Cryptographic caveat

BSR2 is custom, unreviewed research cryptography.

The project does not claim independent cryptanalysis, formal verification, or
production-security review of BSR2.

It must not be the sole protection for high-value or irreplaceable credentials,
identity records, recovery secrets, or comparable material.

See [BSR2 integration and threat model](BSR2_INTEGRATION.md).

## Supported release lines

BrisartIdentityTools maintains three supported lines. LTS-2028 is held as two
separate lines, and Official is the development line:

| Line | Folder | What it is | Encryption | End of life |
| --- | --- | --- | --- | --- |
| LTS-2028 1.3.x | `LTS-2028 1.3.x/` | The original LTS-2028 line | BSR2 Alpha 3 (0.3.0-alpha), vendored in its own `vendor/` | 31 December 2028 |
| LTS-2028 1.4.x | `LTS-2028 1.4.x/` | The original LTS-2028 line; its only change is the new encryption | BSR2 (`97_Encryption/Official`) | 31 December 2028 |
| Official | `Official/` | Active development line: the 1.4.x architecture plus non-security extras | BSR2 (`97_Encryption/Official`) | None designated while it is the development line |
| Pre-1.3.0 and superseded releases | | | | Ended |

**Security updates for every line.** All three lines are covered. Each one
receives security updates until its designated end of life. A fix ships on
every supported line the defect affects:

- **Application code** that the lines share is fixed on the oldest affected
  line first and carried forward: LTS-2028 1.3.x, then LTS-2028 1.4.x, then
  Official.
- **BSR2** is fixed once, in `97_Encryption/Official`.
  LTS-2028 1.4.x and Official both link to it, so both receive the fix
  together.
- **1.3.x's vendored BSR2** is fixed within 1.3.x only. If a defect can't be
  fixed within 1.3.x's original contract, the remedy is to move to
  LTS-2028 1.4.x (see Lifecycle).

**Why LTS-2028 is two lines.** The LTS-2028 contract promised a
dependency-free line with vendored BSR2 and no stored-format changes. The
archive-wide cryptography migration (root `CHANGELOG.md`, 2026-10-23) can't be
adopted inside that promise, and the archive policy says such a migration
belongs outside the established LTS line. LTS-2028 is therefore held twice:

- **LTS-2028 1.3.x keeps the original contract unchanged.** It has no
  dependency outside its own folder, and makes no changes to cryptographic
  primitives, stored formats, authentication policy, hardware or device
  integration, or external dependencies. It does not adopt the new encryption.
  Its encryption therefore has known vulnerabilities that 1.3.x will not fix:
  a keyring KDF that is not memory-hard, an envelope that is not nonce-misuse
  resistant, and randomness without BSR2 Alpha 4's fork and copy
  protections. They are KI-008, KI-009, and KI-010 in LTS-2028 1.3.x's
  `docs/KNOWN_ISSUES.md`. The remedy for each is LTS-2028 1.4.x.
- **LTS-2028 1.4.x is 1.3.x plus the new encryption, and nothing else.** It
  takes its encryption from BSR2 inside the Brisart Research
  Archive, through `crypto/encryption.py`, and adds the opt-in migration that
  moves existing data to it. It shares Official's architecture, and any new
  encryption is always taken from `97_Encryption/Official`.

**No new features on LTS-2028.** Both LTS-2028 lines receive security and
correctness changes only, until they reach end of life on 31 December 2028 and
the next LTS line (2029) takes over from the then-current Official. New
features go to Official only. Official's extras today:

- optional hardware integration (`hardware/`);
- the Integrity Ledger and `tools/integrity_checkpoint.py`;
- the package demo's save-to-disk option;
- the encryption status line and Help > About entry in the GUI, and the
  start-up warning pop-up when encryption is not found;
- the encryption line in `python cli.py version`;
- `python cli.py encryption`, BSR2's own toolkit.

**Data between lines.** LTS-2028 1.4.x and Official write and read the same
formats. Both read everything LTS-2028 1.3.x writes, and offer to migrate it.
Migration is one-way: data migrated or newly written by LTS-2028 1.4.0,
Official 1.10.0, or later can't be read by any LTS-2028 1.3.x release or by
Official 1.9.2 and earlier. An operator who needs 1.3.x to keep reading a store
should not migrate it.

**Migration stays in 1.4.x for at least three months.** LTS-2028 1.4.x keeps
reading the previous encryption and keeps its migration commands and pop-up
until at least 8 February 2027. No 1.4.x release before that date removes them.

**Testing.** Each line has its own GitHub Actions workflow in the archive's
`.github/workflows/`: `test-95-identity-tools-lts2028-1.3.yml`,
`test-95-identity-tools-lts2028-1.4.yml`, and
`test-95-identity-tools-official.yml`. Passing a line's suite is not a security
certification.

The same release-line text appears in all three lines' `docs/SECURITY.md`.

A published maintenance policy is not evidence that a particular fix has
already shipped. Check the selected release's source and release history.

## Lifecycle

Each line's maintenance is limited to its published support window.

Where a defect cannot safely be corrected within a line's architecture,
moving to another supported line may be necessary. For LTS-2028 1.3.x, that
line is normally LTS-2028 1.4.x.

After end of support, historical availability does not imply continuing
maintenance or security updates.

## Assurance boundaries

Support status does not change:

- BSR2's research-cryptography caveat.
- Biometric calibration and anti-spoofing limitations.
- Demonstration package text-to-key derivation.
- Editable local attempt state.
- Unauthenticated local audit history.
- Bulk-processing resource and temporary-file limitations.
- Physical-device validation requirements (Official only).

Each of these is explained, with what you can do about it, in
[What these tools do not protect against](BSR2_INTEGRATION.md#what-these-tools-do-not-protect-against).
Open defects are in [Known issues](KNOWN_ISSUES.md).
