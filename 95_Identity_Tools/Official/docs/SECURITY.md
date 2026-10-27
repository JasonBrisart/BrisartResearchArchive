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
- Current-line integrity and optional hardware integration.

BSR2 primitive issues can also be reported, but application-level fixes do not
independently resolve flaws in the underlying construction.

## Cryptographic caveat

BSR2 is custom, unreviewed research cryptography.

The project does not claim independent cryptanalysis, formal verification, or
production-security review of BSR2.

It must not be the sole protection for high-value or irreplaceable credentials,
identity records, recovery secrets, or comparable material.

See [BSR2 integration and threat model](BSR2_INTEGRATION.md).

## Documented release-line policy

The project documents two maintenance lines:

| Line | Documented policy |
| --- | --- |
| LTS-2028 | Feature-frozen long-term-support line, with support through 31 December 2028 |
| Current `main` | Active development line |
| Pre-1.3.0 and superseded releases | End of support under the documented policy |

The LTS policy preserves its dependency-free architecture and limits changes
to security and correctness maintenance within that architecture.

The Current line can introduce optional hardware integrations and deployment
requirements outside the LTS guarantee.

A published maintenance policy is not evidence that a particular fix has
already shipped. Check the selected release's source and release history.

## Lifecycle

LTS maintenance is limited to its published support window.

Where a defect cannot safely be corrected within the frozen architecture,
migration to a supported release may be necessary.

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
