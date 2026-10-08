# Entitle

**Software Rights Management for Independent and Offline Environments**

Entitle is software that helps developers and organizations define, distribute, document, and manage software rights in environments where privacy, independence, ownership, and long-term accessibility matter.

Built for developers, research organizations, archives, government environments, and air-gapped systems, Entitle provides practical tools for managing software entitlements, deployment records, software provenance, ownership documentation, and distribution governance without relying on cloud infrastructure, online activation, telemetry, or vendor-controlled services.

Entitle is **pure Python**, uses **no external dependencies**, and is designed to be **local-first, offline, and auditable**.

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

Deployment, fork, provenance, and revocation records are written to a single append-only log. Each entry is linked to the previous one through a SHA-256 hash chain, so any edit, deletion, or reordering of earlier records can be detected during verification.

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
- No external dependencies (Python standard library only)

Entitlement protection is handled by the BrisartSecurityResearch (BSR) modules through `entitle_bsr_adapter.py`. Place the BSR files in `bsr/` beside the Entitle source, or adjust the imports in the adapter. BSR is currently experimental research software and should be treated as controlled-environment protection unless independently reviewed.

---

# Project Layout

```
Entitle/
├── bsr/                       # BrisartSecurityResearch modules (DRBG + envelope)
├── entitlements/              # Issued protected .entitle containers
├── entitle_core.py            # Entitlement payloads and rights evaluation
├── entitle_bsr_adapter.py     # Bridge between Entitle and BSR protection
├── entitle_issue.py           # Issue a protected entitlement
├── entitle_verify.py          # Verify a protected entitlement
├── entitle_records.py         # Append-only, hash-chained record store
├── entitle_track.py           # Record deployments, forks, provenance
├── entitle_revoke.py          # Revoke / reinstate / check entitlements
├── entitle_report.py          # Audit and reporting
├── protected_app_example.py   # Example of guarding features with Entitle
└── README.md
```

---

# Tools

All tools are standard-library Python scripts. Windows examples use `^` for line
continuation; on Linux/macOS use `\` instead.

## Issue an entitlement

Create a protected, offline entitlement container.

```
python entitle_issue.py ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --entitlement-id lab-a-demo-001 ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --drbg-seed "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" ^
    --drbg-personalization "EntitleDemoPersonalization" ^
    --deployment-limit 3 ^
    --output entitlements/lab_a.entitle
```

Rights flags such as `--enterprise`, `--modify`, `--fork`, `--export-source`,
and `--redistribute` grant the corresponding governed rights.

## Verify an entitlement

```
python entitle_verify.py ^
    --issuer JasonBrisart ^
    --subject ResearchLabA ^
    --product EntitleDemo ^
    --master-key "change-this-master-key-change-this-master-key" ^
    --file entitlements/lab_a.entitle
```

## Record a governed deployment

Only recorded if the entitlement verifies, grants `can_run`, is not revoked,
and the deployment limit has not been reached.

```
python entitle_track.py deploy ^
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
python entitle_track.py fork ^
    --product EntitleDemo ^
    --source-version 1.4.0 ^
    --fork-name lab-a-custom ^
    --maintainer ResearchLabA ^
    --store records/entitle_records.log

python entitle_track.py provenance ^
    --product EntitleDemo ^
    --origin JasonBrisart ^
    --version 1.4.0 ^
    --custodian ResearchLabA ^
    --store records/entitle_records.log
```

## List records

```
python entitle_track.py list --type deployment --store records/entitle_records.log
```

## Revoke, reinstate, or check an entitlement

```
python entitle_revoke.py revoke ^
    --entitlement-id lab-a-demo-001 ^
    --issuer JasonBrisart ^
    --product EntitleDemo ^
    --reason "key compromise" ^
    --store records/entitle_records.log

python entitle_revoke.py reinstate ^
    --entitlement-id lab-a-demo-001 ^
    --reason "cleared" ^
    --store records/entitle_records.log

python entitle_revoke.py check ^
    --entitlement-id lab-a-demo-001 ^
    --store records/entitle_records.log
```

## Generate an audit report

```
python entitle_report.py --store records/entitle_records.log

python entitle_report.py ^
    --store records/entitle_records.log ^
    --format json ^
    --output reports/entitle_audit.json
```

The report summarizes records by type, deployments by product, and verifies the
tamper-evident hash chain across the whole store.

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
