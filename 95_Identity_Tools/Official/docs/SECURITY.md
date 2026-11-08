# Security Policy

BrisartIdentityTools is a solo-maintained research project.

Its security policy describes reporting and maintenance expectations. It does
not establish independent cryptographic review or production-security
certification.

## Reporting

Security reports should use a private reporting channel.

Where GitHub Private Vulnerability Reporting is enabled, the repository's
Security tab provides a private advisory route. Availability depends on the
repository's configuration.

If that route is unavailable, use a private contact channel published by the
maintainer.

Useful report information includes:

- Affected release line and version.
- Affected component.
- Operating system and Python version.
- Reproduction steps or a minimal example.
- Observed and expected behavior.
- Potential impact.
- Whether the issue appears to involve application integration or BSR2 itself.

Avoid including live credentials, recovery codes, private biometric samples,
or unrelated personal information.

## Response expectations

The existing project policy describes best-effort acknowledgement within a few
days and an initial assessment within roughly two weeks.

These are maintenance targets, not guaranteed service levels.

A confirmed issue's mitigation or fix plan is communicated through the private
reporting channel.

The documented policy does not provide a bug bounty.

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
| LTS-2028 1.3.x | `LTS-2028 1.3.x/` | The original LTS-2028 line | BSR2 0.3.0-alpha, vendored in its own `vendor/` | 31 December 2028 |
| LTS-2028 1.4.x | `LTS-2028 1.4.x/` | The original LTS-2028 line; its only change is the new encryption | Brisart Encryption (`97_Encryption/Official`) | 31 December 2028 |
| Official | `Official/` | Active development line: the 1.4.x architecture plus non-security extras | Brisart Encryption (`97_Encryption/Official`) | None designated while it is the development line |
| Pre-1.3.0 and superseded releases | | | | Ended |

**Security updates for every line.** All three lines are covered. Each one
receives security updates until its designated end of life. A fix ships on
every supported line the defect affects:

- **Application code** that the lines share is fixed on the oldest affected
  line first and carried forward: LTS-2028 1.3.x, then LTS-2028 1.4.x, then
  Official.
- **Brisart Encryption** is fixed once, in `97_Encryption/Official`.
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
  resistant, and randomness without Brisart Encryption 0.4.0's fork and copy
  protections. They are KI-008, KI-009, and KI-010 in LTS-2028 1.3.x's
  `docs/KNOWN_ISSUES.md`. The remedy for each is LTS-2028 1.4.x.
- **LTS-2028 1.4.x is 1.3.x plus the new encryption, and nothing else.** It
  takes its encryption from Brisart Encryption inside the Brisart Research
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
- `python cli.py encryption`, Brisart Encryption's own toolkit.

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
- Physical-device validation requirements.

See KNOWN_ISSUES.md and
[file and bundle encryption](FILE_AND_BUNDLE_ENCRYPTION.md).
